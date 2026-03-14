@echo off
title LG Precision Forge Launcher
echo --- LG Precision Forge Launcher ---
echo.

echo [1/2] Verification et installation des dependances...
pip install --upgrade -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Impossible d'installer les dependances. Verifiez votre installation Python.
    pause
    exit /b
)

echo.
echo [2/2] Lancement de l'application...
streamlit run zone_manager.py