"""CLOUDFLARE WORKERS AI — a reserva gratuita da Pipi        (29/09/2026)

O MESMO MODELO, OUTRO LUGAR
    A Pipi desenha com FLUX.1-schnell na Modal. A Cloudflare roda o MESMO
    FLUX.1-schnell (@cf/black-forest-labs/flux-1-schnell), com 10.000
    "neurons" gratis por dia. Uma imagem de 4 passos gasta ~58 neurons
    (4 blocos de 512x512 x 4,8 + 4 passos x 9,6) -- cerca de 170 imagens
    por dia sem pagar nada. No plano gratis, passou da cota o pedido FALHA
    (nao cobra). A cota volta a meia-noite UTC (21h em Brasilia).

    Docs: https://developers.cloudflare.com/workers-ai/platform/pricing/

QUANDO ENTRA
    So quando a Modal nao desenha (conta parada, sem credito, fora do ar).
    Quem decide a ordem e o pipi_server.py.

O QUE MUDA NA IMAGEM
    - Sai QUADRADA (a Cloudflare nao aceita largura/altura). Para retrato,
      paisagem, story e capa, a Pipi corta do centro -- se o Pillow estiver
      instalado. Sem Pillow, entrega quadrada mesmo.
    - Sai em JPEG. Com Pillow vira PNG; sem Pillow fica .jpg.

CONFIGURACAO: cloudflare.json, ao lado deste arquivo (fora do Git):
    {"account_id": "...", "token": "..."}
    O token e criado em dash.cloudflare.com > Manage account >
    Account API Tokens > Create Token > modelo "Workers AI".
    O token nao aparece em log, erro ou tela.

Venure - venure.com.br
"""

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "cloudflare.json"
MODELO = "@cf/black-forest-labs/flux-1-schnell"
API = os.environ.get("CF_API_BASE", "https://api.cloudflare.com/client/v4").rstrip("/")
FORMATOS = {                     # mesmas proporcoes do pipi_server.py
    "quadrado": (1024, 1024), "retrato": (832, 1216), "paisagem": (1216, 832),
    "story": (768, 1344), "capa": (1344, 768),
}


class CloudflareError(RuntimeError):
    pass


def _ler():
    try:
        d = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if str(d.get("token") or "").strip().upper().startswith("COLE_AQUI"):
        d["token"] = ""                 # modelo ainda nao preenchido
    return d


def configurado():
    d = _ler()
    return bool(str(d.get("account_id") or "").strip() and str(d.get("token") or "").strip())


def _cortar(caminho_jpg, formato, destino_png):
    """Corta do centro para a proporcao do formato e grava PNG (precisa Pillow)."""
    try:
        from PIL import Image
    except Exception:
        return None
    with Image.open(caminho_jpg) as img:
        img = img.convert("RGB")
        larg, alt = img.size
        alvo_l, alvo_a = FORMATOS.get(formato, (1024, 1024))
        razao = alvo_l / alvo_a
        if abs(larg / alt - razao) > 0.01:
            if larg / alt > razao:            # sobra largura
                nova_l = int(round(alt * razao))
                x = (larg - nova_l) // 2
                img = img.crop((x, 0, x + nova_l, alt))
            else:                             # sobra altura
                nova_a = int(round(larg / razao))
                y = (alt - nova_a) // 2
                img = img.crop((0, y, larg, y + nova_a))
        img.save(destino_png, "PNG")
    return destino_png


def gerar(prompt, formato="quadrado", passos=4, semente=0, destino=None, timeout=120):
    """Mesma assinatura e mesmo retorno do modal_cliente.gerar:
    (caminho, segundos, licenca, extra)."""
    d = _ler()
    conta = str(d.get("account_id") or "").strip()
    token = str(d.get("token") or "").strip()
    if not conta or not token:
        raise CloudflareError("A Cloudflare nao esta configurada (cloudflare.json sem "
                              "account_id ou token).")

    corpo = {"prompt": str(prompt)[:2048], "steps": max(1, min(8, int(passos or 4)))}
    if int(semente or 0) > 0:
        corpo["seed"] = int(semente)
    pedido = urllib.request.Request(
        "%s/accounts/%s/ai/run/%s" % (API, conta, MODELO),
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST")

    inicio = time.time()
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            bruto = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300].replace(token, "***")
        if e.code in (401, 403):
            raise CloudflareError("A Cloudflare recusou o token (HTTP %d). Crie outro com o "
                                  "modelo 'Workers AI'." % e.code) from None
        if e.code == 429 or "neuron" in detalhe.lower() or "quota" in detalhe.lower():
            raise CloudflareError("Acabou a cota gratis de hoje na Cloudflare (volta as 21h "
                                  "de Brasilia). Detalhe: " + detalhe[:150]) from None
        raise CloudflareError("Cloudflare respondeu %s: %s" % (e.code, detalhe)) from None
    except Exception as e:
        raise CloudflareError("Nao cheguei na Cloudflare: %s" % e) from None

    try:
        r = json.loads(bruto)
    except Exception:
        raise CloudflareError("A Cloudflare devolveu algo que nao e JSON.") from None
    if not r.get("success", True):
        erros = "; ".join(str(x.get("message", x)) for x in (r.get("errors") or []))[:300]
        raise CloudflareError("A Cloudflare recusou: " + (erros or "motivo nao informado"))
    b64 = (r.get("result") or {}).get("image") or r.get("image")
    if not b64:
        raise CloudflareError("A Cloudflare respondeu sem imagem.")
    segundos = round(time.time() - inicio, 1)

    destino = Path(destino) if destino else (RAIZ / "producao" / "cloudflare.png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    jpg = destino.with_suffix(".jpg")
    jpg.write_bytes(base64.b64decode(b64))
    final = jpg
    try:
        if _cortar(jpg, formato, destino.with_suffix(".png")):
            final = destino.with_suffix(".png")
            jpg.unlink()
    except Exception:
        final = jpg

    extra = {"motor": "Cloudflare Workers AI", "modelo": "FLUX.1-schnell",
             "passos": corpo["steps"], "custo_usd": 0.0,
             "quadrada": final.suffix == ".jpg" and formato != "quadrado"}
    return str(final), segundos, "Apache-2.0", extra


if __name__ == "__main__":
    # Teste rapido:  python cloudflare_cliente.py "um gato laranja"
    import sys
    texto = " ".join(sys.argv[1:]) or "um gato laranja numa janela, luz de fim de tarde"
    print(gerar(texto))
