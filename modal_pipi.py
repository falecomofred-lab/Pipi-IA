"""PIPI IA NA MODAL — gerador de imagem de verdade
venure.com.br · 13/09/2026

O QUE ISTO SUBSTITUI
    O endpoint que estava publicado (`modal_api_teste.py`) era um esqueleto:
    respondia {"mensagem": "Processamento simulado com sucesso"} e uma
    media_url apontando para exemplo.invalid. Servia para provar que a API
    respondia; nao gerava imagem nenhuma.

    Este aqui carrega o modelo e desenha.

POR QUE FLUX.1-schnell, E NAO O dev
    LICENCA. O schnell e Apache 2.0 -- uso comercial liberado. O dev e
    non-commercial: nao serve para criativo de cliente, que e o seu caso.

    E VELOCIDADE, que aqui e dinheiro. O schnell e destilado e gera em
    4 passos; o dev precisa de ~25. Como a Modal cobra por segundo de GPU,
    isso e a diferenca entre caber e nao caber nos $30 do mes.

POR QUE UM VOLUME
    O modelo tem ~24 GB. Sem Volume, TODO container frio baixaria os 24 GB
    de novo -- minutos de GPU paga so para chegar no ponto de partida. O
    Volume guarda o cache do HuggingFace entre execucoes: baixa uma vez,
    monta instantaneo depois.

    ATENCAO: armazenamento em Volume CONTINUA sendo cobrado mesmo com o
    spend limit em zero. Foi o que a propria tela da Modal avisou. E pouco
    para 24 GB, mas nao e zero.

POR QUE cpu_offload
    O schnell em bfloat16 ocupa ~24 GB, que e exatamente o tamanho da L4.
    Sem folga, ele estoura na hora de montar a imagem. O `cpu_offload`
    mantem os blocos na RAM e sobe um por vez para a placa: cabe com
    sobra, custando alguns segundos a mais por imagem.

    Se voce migrar para uma GPU de 48 GB (L40S), troque por `.to("cuda")`
    e ganhe esses segundos de volta.

COMO PUBLICAR

    pip install modal
    modal setup                       (uma vez, abre o navegador)

    modal secret create pipi-token PIPI_TOKEN=<invente-uma-senha-longa>
    modal deploy modal_pipi.py

    O endereco sai no fim. Guarde junto com o token: no seu Windows,

        python usar_modal.py

CUSTO
    Cada imagem sao poucos segundos de GPU. O que pesa e o container frio:
    subir o modelo do Volume para a placa leva ~20 a 40 segundos, e isso
    conta. Por isso o `scaledown_window` abaixo mantem ele vivo por 2
    minutos depois do ultimo pedido -- quem gera varias imagens seguidas
    paga o aquecimento uma vez so.
"""

import io
import os
import time

import modal

APP = "pipi-ia"
MODELO = "black-forest-labs/FLUX.1-schnell"

# O cache do HuggingFace mora aqui, e sobrevive entre execucoes.
CACHE = "/cache"
volume = modal.Volume.from_name("pipi-modelos", create_if_missing=True)

imagem = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.5.1",
        "diffusers==0.32.2",
        "transformers==4.48.0",
        "accelerate==1.3.0",
        "sentencepiece==0.2.0",
        "protobuf==5.29.3",
        "huggingface_hub[hf_transfer]==0.28.1",
        "fastapi[standard]==0.115.8",
        "Pillow==11.1.0",
    )
    # hf_transfer acelera muito o primeiro download. So vale na primeira
    # vez, mas a primeira vez e justamente a cara.
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": CACHE})
)

app = modal.App(APP, image=imagem)


@app.cls(
    gpu="L4",                      # 24 GB. Troque para "L40S" se precisar de folga.
    volumes={CACHE: volume},
    secrets=[modal.Secret.from_name("pipi-token"), modal.Secret.from_name("huggingface-token")],
    timeout=600,
    # Mantem o container vivo 2 min apos o ultimo pedido: quem gera varias
    # imagens seguidas paga o aquecimento uma vez so.
    scaledown_window=120,
)
class Desenhista:

    @modal.enter()
    def carregar(self):
        """Roda UMA vez por container, nao a cada pedido."""
        try:
            import torch
            from diffusers import FluxPipeline
            import subprocess

            print("[MODAL] ===== VERIFICAÇÕES INICIAIS =====")

            # Verificar HF_TOKEN
            hf_token = os.environ.get("HF_TOKEN", "").strip()
            print(f"[MODAL] HF_TOKEN configurado: {bool(hf_token)}")
            if hf_token:
                print(f"[MODAL] HF_TOKEN length: {len(hf_token)}")

            # Verificar PIPI_TOKEN
            pipi_token = os.environ.get("PIPI_TOKEN", "").strip()
            print(f"[MODAL] PIPI_TOKEN configurado: {bool(pipi_token)}")

            print("[MODAL] Carregando FLUX.1-schnell...")
            self.pipe = FluxPipeline.from_pretrained(
                MODELO, torch_dtype=torch.bfloat16, cache_dir=CACHE)
            self.pipe.enable_model_cpu_offload()
            print("[MODAL] ✓ Modelo carregado com sucesso!")
        except Exception as e:
            print(f"[MODAL] ✗ ERRO FATAL: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise

    @modal.fastapi_endpoint(method="POST", docs=True)
    def gerar(self, dados):
        try:
            import base64
            import torch

            esperado = (os.environ.get("PIPI_TOKEN") or "").strip()
            recebido = str(dados.get("token") or "").strip()

            if not esperado:
                return {"ok": False, "erro": "Token nao configurado"}
            if recebido != esperado:
                return {"ok": False, "erro": "Token invalido"}

            prompt = str(dados.get("prompt") or "").strip()
            if not prompt:
                return {"ok": False, "erro": "Prompt obrigatorio"}

            FORMATOS = {
                "quadrado": (1024, 1024), "retrato": (832, 1216),
                "paisagem": (1216, 832), "story": (768, 1344),
                "capa": (1344, 768),
            }
            largura, altura = FORMATOS.get(
                str(dados.get("formato") or "quadrado"), (1024, 1024))

            passos = max(1, min(8, int(dados.get("passos") or 4)))
            semente = int(dados.get("semente") or 0)
            gerador = (torch.Generator("cpu").manual_seed(semente) if semente else None)

            comeco = time.time()
            img = self.pipe(
                prompt,
                width=largura, height=altura,
                num_inference_steps=passos,
                guidance_scale=0.0,
                generator=gerador,
                max_sequence_length=256,
            ).images[0]

            buf = io.BytesIO()
            img.save(buf, format="PNG")

            return {
                "ok": True,
                "imagem_b64": base64.b64encode(buf.getvalue()).decode(),
                "formato": "png",
                "largura": largura, "altura": altura,
                "passos": passos, "semente": semente,
                "segundos": round(time.time() - comeco, 1),
                "modelo": MODELO,
                "licenca": "Apache-2.0 (uso comercial liberado)",
            }
        except Exception as e:
            print(f"[MODAL] ERRO em gerar(): {e}")
            return {"ok": False, "erro": f"Erro interno: {str(e)[:100]}"}
