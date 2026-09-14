"""CLIENTE DA MODAL — o lado da Pipi

Fala com o endpoint publicado pelo modal_pipi.py. Guarda o endereco e o
token em `modal.json`, ao lado deste arquivo.

POR QUE ARQUIVO E NAO VARIAVEL DE AMBIENTE
    Variavel morre quando a janela do Prompt fecha, e voce teria que
    reescrever a cada vez. O endereco da Modal, ao contrario do tunel do
    Colab, e FIXO -- entao guardar faz ainda mais sentido: configura uma
    vez e esquece.

O TOKEN NAO APARECE EM LUGAR NENHUM
    Nem em log, nem em mensagem de erro, nem na tela. Ele e o que impede
    um estranho de gastar o seu credito.

Venure - venure.com.br
"""

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "modal.json"


class ModalError(RuntimeError):
    pass


def _ler():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def gravar(url, token):
    CONFIG.write_text(
        json.dumps({"url": url.strip(), "token": token.strip()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")


def configurado():
    d = _ler()
    return bool(d.get("url") and d.get("token"))


def endereco():
    return _ler().get("url", "")


def status():
    d = _ler()
    if not d.get("url"):
        return {"configurado": False, "online": False,
                "erro": "endereco da Modal nao configurado"}
    # Nao ha ping barato: acordar o container custa GPU. Entao "online"
    # aqui quer dizer "configurado e com token" -- mentir de outro jeito
    # seria pior. Quem descobre se responde e a primeira imagem.
    return {"configurado": True, "online": bool(d.get("token")),
            "url": d["url"], "modelo": "FLUX.1-schnell"}


def gerar(prompt, formato="quadrado", passos=4, semente=0, destino=None,
          timeout=600):
    """Pede a imagem e grava o PNG. Devolve o caminho do arquivo."""
    d = _ler()
    url, token = d.get("url", "").strip(), d.get("token", "").strip()
    if not url or not token:
        raise ModalError(
            "A Modal nao esta configurada. Rode: python usar_modal.py")

    corpo = json.dumps({
        "token": token, "prompt": prompt, "formato": formato,
        "passos": int(passos or 4), "semente": int(semente or 0),
    }).encode("utf-8")

    pedido = urllib.request.Request(
        url, data=corpo, headers={"Content-Type": "application/json"},
        method="POST")

    try:
        # O timeout e longo de proposito: um container frio leva de 20 a
        # 40 segundos so para subir o modelo do Volume para a placa.
        # Cortar cedo faria a Pipi desistir de um pedido que ia dar certo.
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            bruto = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300]
        raise ModalError("Modal respondeu %s: %s" % (e.code, detalhe)) from e
    except Exception as e:
        raise ModalError("Nao cheguei na Modal: %s" % e) from e

    try:
        r = json.loads(bruto)
    except Exception as e:
        raise ModalError("A Modal devolveu algo que nao e JSON.") from e

    if not r.get("ok"):
        raise ModalError(str(r.get("erro") or "a Modal recusou o pedido"))

    b64 = r.get("imagem_b64")
    if not b64:
        # A TRAVA DO ESQUELETO
        #   Se o endereco apontar para o endpoint de teste antigo, ele
        #   responde ok:true com "mensagem" e nenhuma imagem. Sem esta
        #   checagem, a Pipi gravaria um arquivo vazio e diria que deu
        #   certo.
        #
        # MOSTRAR A PROVA, NAO FAZER PERGUNTAS               (13/09)
        #   A primeira versao desta mensagem listava tres coisas para o
        #   Fred conferir -- tendo a resposta da Modal na mao o tempo
        #   todo. Mandar a pessoa investigar o que voce ja sabe e
        #   transferir trabalho sem motivo.
        #
        #   O endpoint de teste se identifica sozinho: ele devolve
        #   "prompt_recebido" e uma media_url terminada em .invalid.
        marcas = [c for c in ("prompt_recebido", "media_url", "mensagem")
                  if c in r]
        if marcas:
            raise ModalError(
                "Este endereco e o do ENDPOINT DE TESTE, nao o gerador. "
                "Ele respondeu: %s. Rode `modal deploy modal_pipi.py` e "
                "use o endereco novo, que termina em "
                "'-desenhista-gerar.modal.run'."
                % json.dumps({k: r[k] for k in marcas}, ensure_ascii=False)[:200])
        raise ModalError(
            "A Modal respondeu sem imagem. Campos que vieram: %s"
            % ", ".join(sorted(r.keys())))

    destino = Path(destino) if destino else (RAIZ / "producao" / "modal.png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(base64.b64decode(b64))
    return str(destino), r.get("segundos"), r.get("licenca", "")
