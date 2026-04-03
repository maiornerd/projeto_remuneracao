@echo off
title Servidor de Indicacoes
echo Iniciando o Sistema de Indicacoes...

:: Verifica se o Python esta instalado
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python nao encontrado no sistema! 
    echo Por favor, instale o Python marcando a caixa "Add Python to PATH" durante a instalacao.
    pause
    exit /b
)

:: Verifica se o ambiente virtual (venv) existe, se nao, cria
IF NOT EXIST "venv\" (
    echo Configurando o ambiente pela primeira vez... Isso pode demorar alguns segundos.
    python -m venv venv
)

:: Ativa o ambiente virtual local e instala os requerimentos 
call venv\Scripts\activate.bat
echo Verificando dependencias (isso pode ocultar relatorios longos, aguarde)...
pip install -r requirements.txt -q

:: Inicia o servidor Flask
echo.
echo ========================================================
echo                SERVIDOR INICIADO! 
echo.
echo [ACESSO LOCAL]
echo Acesse neste computador: http://localhost:5000
echo.
echo [ACESSO PARA OUTROS FUNCIONARIOS NA REDE DA EMPRESA]
FOR /F "tokens=4 delims= " %%i in ('route print ^| find " 0.0.0.0"') do (
    echo Acesse o link: http://%%i:5000
    goto :found_ip
)
:found_ip
echo.
echo ATENCAO: Mantenha esta janela aberta enquanto utiliza.
echo ========================================================
echo.
python app.py
pause
