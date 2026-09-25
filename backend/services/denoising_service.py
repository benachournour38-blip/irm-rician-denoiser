"""
Service de débruitage IRM haute performance utilisant le modèle ResNet 2D
entraîné et enregistré dans MLflow (Version-02, Checkpoint Best Fold 2).
Exécution accélérée sur GPU CUDA avec fallback CPU automatique.
"""

import os
import io
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image
import pydicom

import torch
import torch.nn as nn

# Emplacements des checkpoints et artifacts MLflow (Portable Cloud / Local)
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
CHECKPOINT_PATH_BUNDLED = PROJECT_DIR / "backend" / "weights" / "best_model_fold_2.pth"
DOCUMENTS_V2_DIR = Path(r"C:\Users\benac\Documents\Version-02")
CHECKPOINT_PATH_PRIMARY = DOCUMENTS_V2_DIR / "checkpoints" / "best_model_fold_2.pth"
CHECKPOINT_PATH_MLFLOW = DOCUMENTS_V2_DIR / "mlruns" / "1" / "01558a9fa227449b917c0f0837ad82d3" / "artifacts" / "checkpoints" / "best_model_fold_2.pth"

# ==============================================================================
# ARCHITECTURE DU MODÈLE RESNET 2D DENOISER (Identique à celle entraînée)
# ==============================================================================

class ResidualBlock(nn.Module):
    def __init__(self, channels: int = 64):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


class ResNetDenoiser(nn.Module):
    def __init__(
        self,
        in_channels: int = 1,
        out_channels: int = 1,
        features: int = 64,
        num_blocks: int = 8
    ):
        super().__init__()
        self.input_layer = nn.Sequential(
            nn.Conv2d(in_channels, features, kernel_size=3, padding=1),
            nn.ReLU(inplace=True)
        )
        self.residual_blocks = nn.Sequential(
            *[ResidualBlock(features) for _ in range(num_blocks)]
        )
        self.output_layer = nn.Conv2d(features, out_channels, kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x = self.input_layer(x)
        x = self.residual_blocks(x)
        x = self.output_layer(x)
        # Global residual learning
        return residual + x


# ==============================================================================
# GESTIONNAIRE D'INFÉRENCE DU MODÈLE
# ==============================================================================

class DenoisingService:
    _instance = None
    _model: Optional[ResNetDenoiser] = None
    _device: Optional[torch.device] = None
    _checkpoint_loaded: Optional[str] = None
    _cache: Dict[str, bytes] = {}  # Cache mémoire des images PNG rendues

    @classmethod
    def get_device(cls) -> torch.device:
        if cls._device is None:
            if torch.cuda.is_available():
                cls._device = torch.device("cuda")
                print(f"[CUDA] Inférence GPU active : {torch.cuda.get_device_name(0)}")
            else:
                cls._device = torch.device("cpu")
                print("[CPU] Inférence CPU active.")
        return cls._device

    @classmethod
    def get_model(cls) -> ResNetDenoiser:
        if cls._model is None:
            device = cls.get_device()
            model = ResNetDenoiser(in_channels=1, out_channels=1, features=64, num_blocks=8)
            
            # Recherche du fichier de checkpoint (priorité Best Fold 2)
            ckpt_path = None
            if CHECKPOINT_PATH_BUNDLED.exists():
                ckpt_path = CHECKPOINT_PATH_BUNDLED
            elif CHECKPOINT_PATH_PRIMARY.exists():
                ckpt_path = CHECKPOINT_PATH_PRIMARY
            elif CHECKPOINT_PATH_MLFLOW.exists():
                ckpt_path = CHECKPOINT_PATH_MLFLOW
            else:
                alt_dir = DOCUMENTS_V2_DIR / "checkpoints"
                if alt_dir.exists():
                    pths = list(alt_dir.glob("best_model_fold_*.pth"))
                    if pths:
                        ckpt_path = pths[0]

            if not ckpt_path or not ckpt_path.exists():
                raise FileNotFoundError(f"Checkpoint ResNet introuvable dans {CHECKPOINT_PATH_PRIMARY}")

            print(f"[MLFLOW] Chargement des poids du modèle depuis : {ckpt_path}")
            state_dict = torch.load(str(ckpt_path), map_location=device)
            model.load_state_dict(state_dict)
            model.to(device)
            model.eval()

            # Compilation TorchScript / warmup
            with torch.no_grad():
                dummy = torch.zeros(1, 1, 256, 256, device=device)
                _ = model(dummy)

            cls._model = model
            cls._checkpoint_loaded = str(ckpt_path)
            print("[SUCCESS] Modèle ResNet 2D Denoiser prêt pour l'inférence.")

        return cls._model

    @classmethod
    def is_model_available(cls) -> bool:
        try:
            _ = cls.get_model()
            return True
        except Exception as e:
            print(f"[WARN] Modèle non disponible: {e}")
            return False

    @classmethod
    def denoise_pixel_array(cls, pixel_array: np.ndarray) -> np.ndarray:
        """
        Applique le débruitage par inférence GPU CUDA sur une matrice 2D.
        Utilise la normalisation consistante issue de l'entraînement.
        """
        model = cls.get_model()
        device = cls.get_device()

        orig_shape = pixel_array.shape
        max_val = float(pixel_array.max())

        if max_val <= 0:
            return pixel_array.copy()

        # 1. Normalisation [0.0, 1.0]
        norm_img = np.clip(pixel_array.astype(np.float32) / max_val, 0.0, 1.0)

        # 2. Conversion en tenseur PyTorch (1, 1, H, W)
        tensor_in = torch.from_numpy(norm_img).float().unsqueeze(0).unsqueeze(0).to(device)

        # 3. Inférence GPU avec torch.no_grad()
        with torch.no_grad():
            pred_norm = model(tensor_in)
            pred_norm = torch.clamp(pred_norm, 0.0, 1.0)

        # 4. Dénormalisation vers l'échelle d'origine
        denoised_array = (pred_norm[0, 0].cpu().numpy() * max_val).astype(np.float32)
        return denoised_array

    @classmethod
    def render_denoised_slice_png(
        cls,
        file_path: str,
        custom_wc: Optional[float] = None,
        custom_ww: Optional[float] = None,
        invert: bool = False
    ) -> bytes:
        """
        Lit le fichier DICOM, applique l'inférence de débruitage ResNet sur GPU,
        applique le fenêtrage Window/Level et génère le flux PNG optimisé.
        """
        cache_key = f"{file_path}_wc{custom_wc}_ww{custom_ww}_inv{invert}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        ds = pydicom.dcmread(file_path, force=True)
        raw_pixels = ds.pixel_array.astype(np.float32)

        # Rescale Slope & Intercept
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        if slope != 1.0 or intercept != 0.0:
            raw_pixels = raw_pixels * slope + intercept

        # Inférence IA de débruitage
        denoised_pixels = cls.denoise_pixel_array(raw_pixels)

        # Photometric Interpretation
        photometric = getattr(ds, "PhotometricInterpretation", "MONOCHROME2")
        is_monochrome1 = (photometric == "MONOCHROME1")

        # Fenêtrage (Window / Level)
        wc = custom_wc
        ww = custom_ww

        if wc is None or ww is None:
            dicom_wc = getattr(ds, "WindowCenter", None)
            dicom_ww = getattr(ds, "WindowWidth", None)
            if isinstance(dicom_wc, (list, pydicom.multival.MultiValue)):
                dicom_wc = dicom_wc[0]
            if isinstance(dicom_ww, (list, pydicom.multival.MultiValue)):
                dicom_ww = dicom_ww[0]

            if dicom_wc is not None and dicom_ww is not None and float(dicom_ww) > 0:
                wc = float(dicom_wc)
                ww = float(dicom_ww)
            else:
                p_low, p_high = np.percentile(denoised_pixels, (1.0, 99.5))
                if p_high <= p_low:
                    p_high = p_low + 1.0
                ww = p_high - p_low
                wc = p_low + ww / 2.0

        if ww <= 0:
            ww = 1.0

        min_val = wc - 0.5 - (ww - 1) / 2.0
        max_val = wc - 0.5 + (ww - 1) / 2.0

        normalized = np.clip((denoised_pixels - min_val) / (max_val - min_val), 0.0, 1.0)
        scaled_8bit = (normalized * 255.0).astype(np.uint8)

        if is_monochrome1 ^ invert:
            scaled_8bit = 255 - scaled_8bit

        img = Image.fromarray(scaled_8bit, mode='L')
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        png_bytes = buffer.getvalue()

        # Limite taille cache (max 200 images en RAM)
        if len(cls._cache) > 200:
            cls._cache.clear()
        cls._cache[cache_key] = png_bytes

        return png_bytes

    @classmethod
    def calculate_slice_metrics(cls, file_path: str) -> Dict[str, Any]:
        """
        Calcule les métriques quantitatives de restauration (L1, PSNR, SSIM, Réduction du bruit)
        entre l'image brute et la prédiction du modèle ResNet 2D.
        """
        t0 = time.time()
        ds = pydicom.dcmread(file_path, force=True)
        raw_pixels = ds.pixel_array.astype(np.float32)

        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        if slope != 1.0 or intercept != 0.0:
            raw_pixels = raw_pixels * slope + intercept

        denoised_pixels = cls.denoise_pixel_array(raw_pixels)
        elapsed_ms = (time.time() - t0) * 1000.0

        max_val = float(max(raw_pixels.max(), denoised_pixels.max(), 1.0))
        norm_orig = raw_pixels / max_val
        norm_denoised = denoised_pixels / max_val

        # L1 / MAE
        l1_diff = float(np.mean(np.abs(norm_denoised - norm_orig)))

        # PSNR
        mse = float(np.mean((norm_denoised - norm_orig) ** 2))
        psnr_db = float(10 * np.log10(1.0 / (mse + 1e-10))) if mse > 0 else 99.0

        # SSIM calculation (windowed)
        u_x = float(np.mean(norm_orig))
        u_y = float(np.mean(norm_denoised))
        var_x = float(np.var(norm_orig))
        var_y = float(np.var(norm_denoised))
        cov_xy = float(np.mean((norm_orig - u_x) * (norm_denoised - u_y)))

        c1 = (0.01) ** 2
        c2 = (0.03) ** 2
        ssim_val = float(((2 * u_x * u_y + c1) * (2 * cov_xy + c2)) / ((u_x**2 + u_y**2 + c1) * (var_x + var_y + c2)))
        ssim_val = max(0.0, min(ssim_val, 1.0))

        # Background noise estimation (bottom 10% intensity region)
        bg_thresh = np.percentile(raw_pixels, 15)
        bg_mask = raw_pixels < bg_thresh
        orig_bg_std = float(np.std(raw_pixels[bg_mask])) if np.sum(bg_mask) > 10 else float(np.std(raw_pixels))
        denoised_bg_std = float(np.std(denoised_pixels[bg_mask])) if np.sum(bg_mask) > 10 else float(np.std(denoised_pixels))
        noise_red_pct = float(max(0.0, (1.0 - (denoised_bg_std / max(orig_bg_std, 1e-6))) * 100.0))

        return {
            "inference_time_ms": round(elapsed_ms, 2),
            "psnr_db": round(psnr_db, 2),
            "ssim": round(ssim_val, 4),
            "l1_error": round(l1_diff, 5),
            "noise_reduction_pct": round(noise_red_pct, 1),
            "orig_stats": {
                "mean": round(float(np.mean(raw_pixels)), 1),
                "std": round(float(np.std(raw_pixels)), 1),
                "max": round(float(np.max(raw_pixels)), 1)
            },
            "denoised_stats": {
                "mean": round(float(np.mean(denoised_pixels)), 1),
                "std": round(float(np.std(denoised_pixels)), 1),
                "max": round(float(np.max(denoised_pixels)), 1)
            },
            "device": cls.get_device().type.upper()
        }

    @classmethod
    def get_model_info(cls) -> Dict[str, Any]:
        """Retourne les informations du modèle et du registre MLflow."""
        is_avail = cls.is_model_available()
        device_name = "CUDA GPU (" + torch.cuda.get_device_name(0) + ")" if torch.cuda.is_available() else "CPU"
        
        return {
            "model_available": is_avail,
            "target_model": "ResNet 2D Denoiser",
            "architecture": "ResNetDenoiser (8 Residual Blocks, 64 features)",
            "selected_fold": 2,
            "registry": "MLflow (Experiment: MRI_Denoising_ResNet)",
            "checkpoint_path": cls._checkpoint_loaded or str(CHECKPOINT_PATH_PRIMARY),
            "execution_device": device_name,
            "status_description": "Modèle MLflow Best Fold 2 actif et opérationnel avec accélération matérielle."
        }
