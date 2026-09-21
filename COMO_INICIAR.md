# Como iniciar a Pipi IA

A Pipi é o maestro de motores de imagem. Ela não usa o `llamafile` do Bigode. O motor local é o ComfyUI, que deve responder em `http://127.0.0.1:8188`.

## Inicialização simples

1. Confirme que `workflow.json` está nesta pasta.
2. Confirme que o ComfyUI está em `G:\Outros computadores\USB e dispositivos externos\Pen IA\ComfyUI`.
3. Dê duplo clique em `pipi.bat`.
4. Aguarde o ComfyUI responder e abra `http://127.0.0.1:7300`.

O `pipi.bat` inicia o ComfyUI em CPU quando ele ainda não está ligado. Se houver uma GPU NVIDIA configurada, o comando deve ser ajustado para retirar `--cpu` e usar CUDA.

## Modelos atuais

- `flux1-dev-Q5_1.gguf`: geração de imagens; requer ComfyUI-GGUF, T5, CLIP e VAE.
- `qwen-image-edit-2511-Q5_K_M.gguf`: edição de imagens; requer workflow próprio com imagem de entrada.

## Diagnóstico

- `GET /api/health`
- `GET /api/imagens`
- `GET /api/logs`
- `POST /api/imagens/job`
- `GET /api/imagens/job/<id>`

Se o job retornar erro de nó, instale o custom node ou corrija o workflow. Se retornar erro de modelo, confira o nome exato do arquivo no diretório do ComfyUI. Não copie um GGUF de texto para a Pipi e não use FLUX no llamafile.
