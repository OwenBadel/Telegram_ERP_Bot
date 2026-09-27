@echo off
chcp 65001 > nul
title Agente ERP Telegram - Industrias Badel ^& Asociados
echo ======================================================================
echo    🏢 AGENTE ERP TELEGRAM - CONTROL DE INVENTARIO Y OPERACIONES
echo    👨‍💻 Autor y Titular: Ingeniero Owen Badel Hooker
echo ======================================================================
echo.

if not exist ".env" (
    echo [INFO] Creando archivo .env local a partir de .env.example...
    copy .env.example .env > nul
)

echo [1/2] Verificando dependencias de Python...
python -c "import telegram, reportlab, pydantic" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Instalando dependencias de requirements.txt...
    pip install -r requirements.txt
)

echo [2/2] Iniciando Agente ERP...
echo.
python main.py

pause
