@echo off
setlocal EnableExtensions
title PIPI IA - Venure
cd /d "%~dp0"
set "ROOT=%~dp0"
if not defined PIPI_PORT set "PIPI_PORT=7300"

echo ============================================================
echo                       PIPI IA
echo            Modal . L40S . FLUX.1-schnell
echo ============================================================
echo.

rem ---------------------------------------------------------------------
rem O QUE ESTE ARQUIVO DEIXOU DE FAZER                        (17/09)
rem
rem   Ele subia um ComfyUI local, esperava 120 segundos por ele, e SAIA
rem   COM ERRO sem nunca abrir a Pipi -- porque nesta maquina o ComfyUI
rem   nao sobe (o PyTorch instalado e a compilacao +cpu). Tambem tentava
rem   um "motor remoto" do Colab, que caducava a cada 12 horas.
rem
rem   Agora o desenho acontece na Modal, num endereco fixo. Nao ha motor
rem   para subir aqui: este arquivo escolhe o Python, confere se a Modal
rem   esta configurada, e abre a tela.
rem ---------------------------------------------------------------------

rem ---------------------------------------------------------------------
rem QUAL PYTHON USAR, E EM QUE ORDEM                          (13/09)
rem
rem   O Python do pendrive vinha ANTES do Python do sistema. Ele e a
rem   versao embarcada: nao tem pip, nao tem pacote instalado, e traz um
rem   python312._pth que fecha o caminho de busca de modulos. A Pipi abria
rem   com ele e morria em ModuleNotFoundError.
rem
rem   O Python do sistema passa na frente. O do pendrive fica como ultimo
rem   recurso, para a Pipi ainda abrir numa maquina sem Python.
rem ---------------------------------------------------------------------
set "PY="
if exist "%ROOT%python\python.exe" set "PY=%ROOT%python\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY if exist "G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe" set "PY=G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe"
if not defined PY (
  echo [ERRO] Python nao encontrado.
  echo        Instale em https://python.org e abra este arquivo de novo.
  pause & exit /b 1
)

rem ---------------------------------------------------------------------
rem A MODAL ESTA CONFIGURADA?
rem
rem   Quem responde e o proprio modal_cliente, para nao haver duas
rem   verdades sobre isso -- uma no .bat e outra no servidor.
rem
rem   Faltar configuracao NAO impede a Pipi de abrir: a tela explica o que
rem   fazer melhor do que uma janela preta que fecha.
rem ---------------------------------------------------------------------
"%PY%" -c "import sys; sys.path.insert(0, r'%ROOT%'); import modal_cliente; sys.exit(0 if modal_cliente.configurado() else 1)" >nul 2>&1
if errorlevel 1 (
  echo [AVISO] A Modal ainda nao esta configurada.
  echo.
  echo         Feche esta janela e rode:   python usar_modal.py
  echo         Depois abra o pipi.bat de novo.
  echo.
  echo         Vou abrir a tela mesmo assim -- ela mostra o mesmo recado.
  echo.
) else (
  echo Motor: Modal, endereco fixo na nuvem.
  echo.
)

echo Abrindo em http://127.0.0.1:%PIPI_PORT% ...
start "" "http://127.0.0.1:%PIPI_PORT%"
"%PY%" "%ROOT%pipi_server.py"

echo.
echo Pipi encerrada.
pause
endlocal
