# IRM Denoising Viewer - Application Radiologue DICOM

Application Web médicale professionnelle destinée aux radiologues pour visualiser, organiser et comparer des séquences d'**IRM Lombaire** (T1 Sagittal, T2 Sagittal, T2 Axial, STIR FatSat) au format DICOM.

---

## 🌟 Fonctionnalités

### 1. Organisation Médicale Patient → Examen → Série
- **Arborescence dynamique** : Exploration rapide de chaque patient, examen daté et série d'acquisition.
- **Recherche instantanée** : Filtrage en temps réel par nom ou identifiant patient.
- **Anonymisation** : Bascule en un clic pour masquer les identités réelles lors des présentations cliniques.

### 2. Visualiseur Médical Haute Fidélité
- **Fenêtrage Window / Level (W/L)** : Réglage en direct du contraste et de la luminosité à la souris ou via presets optimisés pour le rachis lombaire (Rachis T2, Rachis T1, STIR/Œdème, Os/Corticale, Tissus mous).
- **Navigation des coupes** : Défilement ultra-fluide à la molette, au curseur de défilement ou lecture Cine automatique.
- **Outils radiologiques** : Pan (déplacement), Zoom avec centrage, Inversion des niveaux de gris, Réinitialisation, Mode Plein Écran.
- **HUD Médical** : Affichage télémétrique aux 4 coins (Identité, Description d'examen, Paramètres physiques TR/TE/Champ 3.0T, Épaisseur de coupe, Matrice, Index de coupe, Valeurs W/L et Zoom).

### 3. Comparaison Original / Emplacement IA
- **Mode Original** : Visualisation plein écran de la série native.
- **Mode Débruité (Futur IA)** : Zone réservée avec statut clair et explicite *« En attente du modèle IA »*.
- **Mode Comparaison Côte-à-Côte** : Deux fenêtres synchronisées en continu (zoom, déplacement, niveau de contraste et coupe).
- **Mode Curseur Scindé (Split Curtain)** : Comparaison interactive par rideau vertical déplaçable.

### 4. Importation DICOM Universelle
- Glisser-déposer (Drag & Drop) de fichiers unitaires `.dcm`, de dossiers complets ou d'archives `.zip`.
- Analyse automatique des tags DICOM et indexation immédiate dans l'arborescence.

### 5. Inspection des Métadonnées DICOM
- Volet latéral synthétique des paramètres cliniques et physiques.
- Fenêtre modale avec dictionnaire complet et moteur de recherche de tous les éléments DICOM (Tag, VR, Nom, Valeur).

---

## 🏗 Architecture Backend & Préparation IA

```text
backend/
├── main.py                  # Point d'entrée FastAPI & montage du frontend
├── config.py                # Gestion des dossiers de stockage et chemins
├── sample_generator.py      # Générateur d'études IRM lombaire de démonstration
├── models/
│   └── schemas.py           # Schémas Pydantic (Patient, Study, Series, Metadata, Upload)
├── services/
│   ├── dicom_service.py     # Parsing pydicom, extraction de tags et rendu dynamique PNG
│   ├── storage_service.py   # Gestionnaire de fichiers hiérarchiques et index SQLite
│   └── denoising_service.py # Interface abstraite prête pour MLflow / ResNet 2D Denoiser
└── routers/
    ├── patients.py          # Routes API Patients (/api/patients)
    ├── studies.py           # Routes API Examens (/api/studies)
    ├── series.py            # Routes API Séries (/api/series)
    ├── instances.py         # Routes Coupes, Rendu d'image W/L et Métadonnées (/api/instances)
    ├── upload.py            # Route d'importation multi-fichiers et ZIP (/api/dicom/upload)
    └── denoising.py         # Route préparée pour le déclenchement IA (/api/series/{id}/denoise)
```

### Intégration future du modèle ResNet 2D Denoiser via MLflow :
Dans `backend/services/denoising_service.py`, l'interface `DenoisingService.process_series(series_uid)` est prête à recevoir le chargement du modèle PyTorch via l'URI de registre MLflow (`models:/resnet2d_denoiser/Production`), la normalisation des tranches DICOM 2D et la génération de la série débruitée.

---

## 🚀 Démarrage Rapide

### 1. Installation des dépendances
```bash
pip install -r requirements.txt
```

### 2. Lancement de l'application
```bash
python run.py
```
ou double-cliquer sur `start_viewer.bat`.

### 3. Accès dans le navigateur
- **Interface Radiologue** : [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Documentation API Swagger** : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
