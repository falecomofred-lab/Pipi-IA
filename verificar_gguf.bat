@echo off
setlocal EnableExtensions
title Verificador GGUF - Bigode e Pipi
cd /d "%~dp0"
set "SCRIPT=%~dp0verificar_gguf.py"
set "ROOT1=G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem"
set "ROOT2=G:\Outros computadores\USB e dispositivos externos\Pen IA"
set "OUT=%~dp0relatorio_gguf.json"

if not exist "%SCRIPT%" (
  echo [ERRO] verificar_gguf.py nao encontrado em %~dp0
  pause & exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado no PATH.
  pause & exit /b 1
)

echo Verificando os GGUF destas pastas:
echo   %ROOT1%
echo   %ROOT2%
echo.
python "%SCRIPT%" "%ROOT1%" "%ROOT2%" --out "%OUT%"
set "RC=%ERRORLEVEL%"
echo.
echo Relatorio JSON: %OUT%
echo Relatorio CSV : %~dp0relatorio_gguf.csv
if not "%GGUF_LLAMA_EXE%"=="" (
  echo.
  echo Para teste de carga, execute manualmente:
  echo python "%SCRIPT%" "%ROOT1%" "%ROOT2%" --load-test "%GGUF_LLAMA_EXE%" --out "%~dp0relatorio_gguf_com_carga.json"
)
pause
exit /b %RC%
