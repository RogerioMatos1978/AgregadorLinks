@echo off
REM NOVO: atalho de duplo clique para subir o app em modo rede (Waitress).
REM
REM Antes de usar pela primeira vez:
REM   1) copie .env.example para .env e ajuste HOST=0.0.0.0, SECRET_KEY,
REM      ADMIN_PASSWORD, VIEWER_PASSWORD (veja PLANO-REDE.md e NOVIDADES.md).
REM   2) crie o ambiente virtual, se ainda nao tiver:
REM        python -m venv .venv
REM   3) instale as dependencias:
REM        .venv\Scripts\pip install -r linkaggreg\requirements.txt
REM
REM Este atalho espera o ambiente virtual em ".venv" na mesma pasta deste
REM arquivo. Se o seu venv tiver outro nome/local, ajuste o caminho abaixo.

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo Ambiente virtual nao encontrado em .venv\
    echo Crie um com:      python -m venv .venv
    echo Depois instale:   .venv\Scripts\pip install -r linkaggreg\requirements.txt
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
cd linkaggreg
python serve.py

pause
