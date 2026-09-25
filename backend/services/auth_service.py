import hmac
import hashlib
import base64
import json
import time
from typing import Optional, Dict, Any
from backend.config import AUTH_PASSWORD, AUTH_ADMIN_PASSWORD, AUTH_SECRET_KEY, AUTH_TOKEN_EXPIRY_HOURS

class AuthService:
    """Service de gestion d'authentification et de jetons sécurisés pour l'application médicale."""

    @staticmethod
    def verify_password(password: str) -> Optional[Dict[str, Any]]:
        """
        Vérifie le mot de passe fourni.
        Retourne le profil de l'utilisateur ('doctor' ou 'admin') si valide, None sinon.
        """
        if not password:
            return None
            
        cleaned = password.strip()
        if cleaned == AUTH_ADMIN_PASSWORD:
            return {
                "role": "admin",
                "username": "Administrateur",
                "label": "Superviseur IA"
            }
        elif cleaned == AUTH_PASSWORD:
            return {
                "role": "doctor",
                "username": "Dr. Radiologue",
                "label": "Médecin Référent"
            }
        return None

    @staticmethod
    def create_token(user_info: Dict[str, Any]) -> str:
        """Génère un jeton HMAC sécurisé avec expiration."""
        payload = {
            "role": user_info.get("role", "doctor"),
            "username": user_info.get("username", "Dr. Radiologue"),
            "label": user_info.get("label", "Médecin"),
            "exp": int(time.time()) + (AUTH_TOKEN_EXPIRY_HOURS * 3600),
            "iat": int(time.time())
        }
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        sig = hmac.new(AUTH_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        return f"{payload_b64}.{sig}"

    @staticmethod
    def validate_token(token: str) -> Optional[Dict[str, Any]]:
        """Valide la signature et l'expiration d'un jeton de session."""
        if not token or "." not in token:
            return None
        try:
            payload_b64, sig = token.split(".", 1)
            expected_sig = hmac.new(AUTH_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            
            payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
            payload = json.loads(payload_json)
            
            if payload.get("exp", 0) < int(time.time()):
                return None  # Expiré
                
            return payload
        except Exception:
            return None
