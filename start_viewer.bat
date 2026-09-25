@echo off
title IRM Denoising Viewer - Station Radiologue
cd /d "%~dp0"

echo ======================================================================
echo    IRM DENOISING VIEWER - Station de Radiologie IRM Lombaire DICOM
echo ======================================================================
echo.
echo [1/2] Verification de l'environnement Python...
python --version
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'a pas ete detecte sur ce systeme.
    pause
    exit /b
)

echo.
echo [2/2] Lancement de la station et generation du lien public securise...
echo.
python launch_public.py
pause
