@echo off
setlocal EnableExtensions EnableDelayedExpansion
title PIPI IA - Venure
cd /d "%~dp0"
set "ROOT=%~dp0"
if not defined PIPI_PORT set "PIPI_PORT=7300"
if not defined PIPI_COMFYUI_PORT set "PIPI_COMFYUI_PORT=8188"
if not defined PIPI_MODELS_DIR set "PIPI_MODELS_DIR=G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem"
set "COMFY_ROOT=G:\Outros computadores\USB e dispositivos externos\Pen IA\ComfyUI"
set "COMFY_PY=%COMFY_ROOT%\.venv\Scripts\python.exe"
set "COMFY_LOG=%ROOT%comfyui.log"

echo ============================================================
echo                 PIPI IA - VENURE
echo          Maestro de motores de criacao de imagens
echo ============================================================
echo.

rem ---------------------------------------------------------------------
rem QUAL PYTHON USAR, E EM QUE ORDEM                          (13/09)
rem
rem   O Python do pendrive vinha ANTES do Python do sistema. Ele e a
rem   versao embarcada: nao tem pip, nao tem pacote instalado, e traz um
rem   python312._pth que fecha o caminho de busca de modulos. Resultado:
rem   a Pipi abria com ele e morria em
rem
rem       ModuleNotFoundError: No module named 'huggingface_cliente'
rem
rem   O Python do sistema passa na frente. O do pendrive continua como
rem   ultimo recurso, para a Pipi ainda abrir numa maquina sem Python --
rem   que e para isso que ele foi posto ali.
rem ---------------------------------------------------------------------
set "PY="
if exist "%ROOT%python\python.exe" set "PY=%ROOT%python\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY if exist "G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe" set "PY=G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe"
if not defined PY (
  echo [ERRO] Python nao encontrado.
  pause & exit /b 1
)
if not exist "%COMFY_PY%" (
  set "COMFY_PY="
  for /f "delims=" %%P in ('where python 2^>nul') do if not defined COMFY_PY set "COMFY_PY=%%P"
)
if not defined COMFY_PY set "COMFY_PY=%PY%"

if not exist "%ROOT%workflow.json" (
  echo [ERRO] workflow.json nao encontrado em %ROOT%.
  pause & exit /b 1
)
if not exist "%PIPI_MODELS_DIR%" echo [AVISO] Pasta de modelos nao encontrada: %PIPI_MODELS_DIR%

rem ---------------------------------------------------------------------
rem MOTOR REMOTO PRIMEIRO   (13/09)
rem
rem   Se o usar_desenhista_do_colab.py gravou um endereco e ele responde,
rem   nao ha por que subir um ComfyUI local -- que nesta maquina nem sobe,
rem   porque falta CUDA. Sem este desvio, o .bat gastava minutos tentando
rem   levantar um servidor condenado antes de chegar na Pipi.
rem ---------------------------------------------------------------------
set "REMOTO="
if exist "%ROOT%motor_remoto.txt" set /p REMOTO=<"%ROOT%motor_remoto.txt"
if defined REMOTO (
  echo Motor remoto gravado: %REMOTO%
  powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%REMOTO%/system_stats' -UseBasicParsing -TimeoutSec 20; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 (
    set "PIPI_COMFYUI_URL=%REMOTO%"
    echo ComfyUI remoto verificado.
    goto PIPI_START
  )
  echo [AVISO] O motor remoto nao respondeu. O Colab ainda esta ligado?
  echo         Rode: python usar_desenhista_do_colab.py
  echo         Tentando o ComfyUI desta maquina...
)

rem Instala o suporte GGUF do ComfyUI apenas quando ainda nao existe.
if exist "%COMFY_ROOT%\main.py" if not exist "%COMFY_ROOT%\custom_nodes\ComfyUI-GGUF\nodes.py" (
  echo Instalando suporte ComfyUI-GGUF...
  git clone https://github.com/city96/ComfyUI-GGUF "%COMFY_ROOT%\custom_nodes\ComfyUI-GGUF"
  "%PY%" -m pip install -q gguf
)

rem Inicia ComfyUI automaticamente quando o Python do ambiente existir.
powershell -NoProfile -Command "if (Test-NetConnection 127.0.0.1 -Port %PIPI_COMFYUI_PORT% -InformationLevel Quiet) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
  if exist "%COMFY_ROOT%\main.py" (
    if exist "%COMFY_PY%" (
      echo Iniciando ComfyUI em http://127.0.0.1:%PIPI_COMFYUI_PORT% ...
      pushd "%COMFY_ROOT%"
      start "ComfyUI - Pipi" /min cmd /c ""%COMFY_PY%" main.py --cpu --listen 127.0.0.1 --port %PIPI_COMFYUI_PORT% > "%COMFY_LOG%" 2>&1"
      popd
      echo Aguardando o ComfyUI; se falhar, o log sera mostrado.
    ) else (
      echo [ERRO] Python do ComfyUI nao encontrado: %COMFY_PY%
      pause & exit /b 1
    )
  ) else (
    echo [ERRO] ComfyUI nao encontrado em %COMFY_ROOT%.
    echo Instale-o nessa pasta ou defina PIPI_COMFYUI_URL para um servidor remoto.
    pause & exit /b 1
  )
) else echo ComfyUI ja esta respondendo na porta %PIPI_COMFYUI_PORT%.

for /l %%N in (1,1,120) do (
  powershell -NoProfile -Command "if (Test-NetConnection 127.0.0.1 -Port %PIPI_COMFYUI_PORT% -InformationLevel Quiet) { exit 0 } else { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto COMFY_OK
  if %%N==15 echo Ainda aguardando o ComfyUI na porta %PIPI_COMFYUI_PORT%...
  if %%N==30 if exist "%COMFY_LOG%" (
    echo --- ultimas linhas do comfyui.log ---
    powershell -NoProfile -Command "Get-Content -LiteralPath '%COMFY_LOG%' -Tail 25"
    echo --- fim do log; continuando a espera ---
  )
  timeout /t 1 /nobreak >nul
)
echo [ERRO] ComfyUI nao respondeu. Consulte %COMFY_LOG%.
pause & exit /b 1

:COMFY_OK
set "PIPI_COMFYUI_URL=http://127.0.0.1:%PIPI_COMFYUI_PORT%"
echo ComfyUI verificado.

:PIPI_START
echo Motor: %PIPI_COMFYUI_URL%
echo Iniciando Pipi em http://127.0.0.1:%PIPI_PORT% ...
"%PY%" "%ROOT%pipi_server.py"
echo.
echo Pipi encerrada. Consulte /api/logs e %COMFY_LOG%.
pause
endlocal
