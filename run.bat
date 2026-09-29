@echo off
setlocal
cd /d "%~dp0"

:verificar_instalacao
if not exist ".venv\Scripts\activate.bat" goto precisa_instalar
if not exist ".venv\Scripts\parallel-ytdlp.exe" goto precisa_instalar
if exist "tools\deno\deno.exe" goto executar
where deno.exe >nul 2>&1
if not errorlevel 1 goto executar

:precisa_instalar

echo O ambiente do projeto ainda nao foi configurado completamente.
choice /C SN /N /M "Deseja executar a instalacao agora? [S/N]: "
if errorlevel 2 exit /b 1

:instalar
echo.
echo Aguarde enquanto o projeto e suas dependencias sao instalados...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if not errorlevel 1 goto verificar_resultado

echo.
echo A instalacao falhou.
choice /C SN /N /M "Deseja tentar novamente? [S/N]: "
if errorlevel 2 exit /b 1
goto instalar

:verificar_resultado
if not exist ".venv\Scripts\activate.bat" goto instalacao_incompleta
if not exist ".venv\Scripts\parallel-ytdlp.exe" goto instalacao_incompleta
goto executar

:instalacao_incompleta
    echo.
    echo A instalacao terminou, mas o ambiente ou o comando do programa nao foi encontrado.
    choice /C SN /N /M "Deseja tentar novamente? [S/N]: "
    if errorlevel 2 exit /b 1
    goto instalar

:executar
call ".venv\Scripts\activate.bat"
parallel-ytdlp %*

