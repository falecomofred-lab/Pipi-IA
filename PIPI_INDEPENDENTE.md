# Pipi IA independente

A Pipi agora pode rodar sem o processo do Bigode. Ela tem seu próprio servidor, catálogo de motores, pasta de modelos, pasta de produção e interface.

## Iniciar

```powershell
$env:PIPI_PORT=7300
python .\pipi_server.py
```

Abra `http://127.0.0.1:7300`. O servidor funciona sem ComfyUI para catálogo, saúde e preparação de jobs. Por padrão, ele procura os motores em `G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem`, inclusive em subpastas. Para geração real, instale o ComfyUI separadamente, mantenha os modelos nessa pasta ou use `extra_model_paths.yaml`, configure `PIPI_COMFYUI_URL` e finalize um `workflow.json` compatível.

Se a pasta estiver montada em outra letra, defina explicitamente o caminho antes de iniciar:

```powershell
$env:PIPI_MODELS_DIR="G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem"
$env:PIPI_PORT="7300"
python .\pipi_server.py
```

O endpoint `http://127.0.0.1:7300/api/health` informa `pasta_motores` e `pasta_existe`. O endpoint `http://127.0.0.1:7300/api/imagens` mostra, para cada motor, `baixado`, `tamanho_local` e `caminho_local`.

## Motores

Os motores estão listados em `motores.json` com licença, fonte oficial, link de download, arquivo esperado e recomendação de VRAM. O catálogo não baixa automaticamente modelos grandes: o usuário baixa o arquivo da fonte oficial, aceita a licença quando exigido e coloca o arquivo na pasta `motores/` ou na pasta correspondente do ComfyUI.

O catálogo inicial inclui **FLUX.1 Schnell**, **SDXL Base 1.0** e **SDXL Refiner 1.0**. Consulte as licenças oficiais antes de uso comercial. O FLUX.1 Schnell é um modelo de 12B que a ficha oficial descreve como capaz de gerar em 1–4 passos e sob licença Apache-2.0; o SDXL Base é distribuído sob OpenRAIL++ e pode funcionar como módulo standalone; o Refiner é opcional para uma pipeline em duas etapas. Fontes: [FLUX.1 Schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell), [SDXL Base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) e [SDXL Refiner 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0).

O ComfyUI documenta que checkpoints, VAE, LoRA, ControlNet e upscalers são arquivos separados, normalmente colocados em `ComfyUI/models/`; também é possível compartilhar diretórios usando `extra_model_paths.yaml`. Consulte a [documentação oficial de modelos do ComfyUI](https://docs.comfy.org/basic-concepts/models) antes de copiar arquivos grandes.

## Backends e limite atual
O servidor não inventa uma imagem se o motor ou workflow não estiver configurado. Há dois caminhos reais: Hugging Face `text_to_image`, quando `HF_TOKEN` e `HF_IMAGE_MODEL` estão configurados, e ComfyUI, quando `PIPI_COMFYUI_URL` e `workflow.json` estão disponíveis. No caminho ComfyUI, a Pipi envia o workflow API, substitui campos de prompt, acompanha a fila, baixa a primeira imagem retornada e grava o PNG em `producao/`. Workflows muito personalizados podem exigir ajuste dos nomes dos nós.

Para Hugging Face:

```powershell
pip install -r .\requirements.txt
$env:HF_TOKEN="seu_token_fine_grained_com_permissao_de_inference"
$env:HF_IMAGE_MODEL="black-forest-labs/FLUX.1-schnell"
python .\pipi_server.py
```

Para escolher explicitamente esse caminho no job, envie `backend: huggingface`. O token nunca deve ser colocado no HTML, no `config.json` ou no GitHub.
