#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR A EDIÇÃO DA PIPI — e provar que ela edita mesmo
Venure · venure.com.br · 22/09/2026

    python usar_modal_edita.py

COMO ESTE TESTE FUNCIONA, E POR QUE ASSIM

    Um modelo de edição quebrado não devolve erro. Ele devolve a imagem
    ORIGINAL de volta, ou uma imagem plausível que ignora a instrução. Um
    teste que só conferisse "voltou uma imagem?" diria "passou" nos dois
    casos.

    Então o teste é medido em pixels:

      1. monto aqui um quadrado PRETO no meio de um fundo BRANCO
      2. peço: "pinte o quadrado de vermelho"
      3. conto quantos pixels vermelhos existem antes e depois

    Antes: zero. Se depois continuar zero, ele não editou -- não importa
    quão bonita seja a imagem que voltou. Se aparecerem vermelhos onde
    havia preto, ele entendeu a instrução e executou.

    É a mesma ideia da palavra escondida no teste da visão do Bigode:
    procurar uma coisa que só pode estar lá se funcionou.

CUSTO DESTE TESTE

    L40S, $0,000542/s. O primeiro pedido acorda a placa e carrega ~41 GB
    do Volume: conte de 2 a 4 minutos. Dá uns 10 centavos de dólar, uma
    vez. As edições seguintes levam segundos.
"""

import base64
import getpass
import io
import json
import sys
import time
import re
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

# A Pipi guarda as credenciais da Modal aqui, e nao num config.json.
CONFIG = BASE / "modal.json"

LADO = 512
INSTRUCAO = ("Pinte o quadrado central de vermelho vivo. "
             "Mantenha o fundo branco.")


def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════
# DESCOBRIR EM VEZ DE PERGUNTAR                            (22/09/2026)
# ══════════════════════════════════════════════════════════════════════
#
#   A primeira versao pedia o endereco e a senha. O Fred respondeu, com
#   razao: "nao tenho, me passa". E ele estava certo duas vezes --
#   primeiro porque a senha e dele e nao minha, e segundo porque O
#   PROGRAMA JA SABE.
#
#   O `modal.json` da Pipi guarda a senha e o endereco do gerador. Os
#   enderecos da Modal seguem sempre a mesma forma:
#
#       https://<conta>--<app>-<classe>-<rota>.modal.run
#
#   Entao o endereco do gerador entrega o nome da conta, e daqui sai o do
#   editor sem ninguem digitar nada. Pedir uma informacao que o programa
#   tem e defeito de projeto, nao seguranca.
def achar_conta(cfg):
    m = re.search(r"https://([^/]+?)--", str(cfg.get("url") or ""))
    return m.group(1) if m else ""


def endereco_do_editor(conta):
    # app `pipi-edita`, classe `Editor`, rota `editar` -- os tres nomes
    # estao no modal_edita.py e e a Modal que os junta assim.
    return "https://%s--pipi-edita-editor-editar.modal.run" % conta


def quadrado_preto():
    """Fundo branco com um quadrado preto no meio. (PIL.Image, base64)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    m = LADO // 4
    ImageDraw.Draw(img).rectangle([(m, m), (LADO - m, LADO - m)],
                                  fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return img, base64.b64encode(buf.getvalue()).decode("ascii")


def conta_vermelho(img):
    """Fração de pixels claramente vermelhos (0 a 1).

    "Claramente vermelho" = o canal R domina os outros dois com folga.
    A folga de 60 evita contar cinza, marrom e bege como vermelho -- sem
    ela, uma sombra qualquer passaria no teste.
    """
    peq = img.convert("RGB").resize((128, 128))
    pix = list(peq.getdata())
    n = sum(1 for r, g, b in pix if r > 110 and r - g > 60 and r - b > 60)
    return n / float(len(pix))


def main():
    print()
    print("  EDIÇÃO DE IMAGEM DA PIPI (Qwen-Image-Edit)")
    print("  " + "-" * 64)
    print("  O endereço sai no fim de:")
    print("      python -m modal deploy modal_edita.py")

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print()
        print("  [x] O Pillow não está neste Python: %s" % sys.executable)
        print("      Sem ele não dá para montar nem medir a imagem de teste,")
        print("      e sem medir eu não gravo nada. Rode:")
        print("          python -m pip install pillow")
        print()
        return 1

    dados = ler_config()
    antes_cfg = dados.get("edicao_modal") or {}

    # ---- a senha ----------------------------------------------------
    token = str(antes_cfg.get("token") or dados.get("token") or "").strip()
    if token:
        print("\n  senha .....: achei no modal.json (%d caracteres)" % len(token))
        print("               (não é impressa, e não precisa ser digitada)")
    else:
        print("\n  [!] Não achei a senha da Pipi no modal.json.")
        print("      Ela é a mesma do `modal secret create pipi-token`.")
        token = getpass.getpass("  Senha (não aparece ao digitar): ").strip()
        if not token:
            print("\n  [x] Sem senha o endpoint recusa — e deve recusar mesmo.")
            return 1

    # ---- o endereço -------------------------------------------------
    url = str(antes_cfg.get("url") or "").strip()
    if not url:
        conta = achar_conta(dados)
        if conta:
            url = endereco_do_editor(conta)
            print("  conta .....: %s" % conta)
            print("  endereço ..: %s" % url)
            print("               (deduzido do endereço do gerador)")
        else:
            print("\n  [!] Não achei o nome da sua conta da Modal no modal.json.")
            url = input("  Endereço (…-editar.modal.run): ").strip()

    if not url.startswith("https://"):
        print("\n  [x] O endereço precisa começar com https://")
        return 1

    from PIL import Image
    original, b64 = quadrado_preto()
    vermelho_antes = conta_vermelho(original)

    print()
    print("  Mandando um quadrado PRETO num fundo branco.")
    print("  Instrução: %r" % INSTRUCAO)
    print("  vermelho na entrada: %.1f%%" % (vermelho_antes * 100))
    print()
    print("  (a primeira vez carrega ~41 GB do Volume: 2 a 4 minutos)")

    corpo = json.dumps({"token": token, "imagem_b64": b64,
                        "instrucao": INSTRUCAO}).encode("utf-8")
    inicio = time.time()
    try:
        pedido = urllib.request.Request(
            url, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pedido, timeout=900) as r:
            saida = json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as erro:
        print("\n  [x] HTTP %s" % erro.code)
        if erro.code == 404:
            # 404 TEM DUAS CAUSAS, E EU NAO SEI QUAL          (22/09)
            #
            #   Ou o app nao foi publicado, ou o endereco que eu deduzi do
            #   nome da conta esta errado. Apontar uma das duas como certa
            #   seria mandar voce consertar a coisa errada -- o defeito que
            #   mais custou tempo neste projeto.
            #
            #   `modal app list` responde a pergunta em um comando: se
            #   `pipi-edita` nao aparecer, falta publicar; se aparecer, o
            #   endereco e que esta errado.
            print("      A Modal não conhece este endereço. São DUAS causas")
            print("      possíveis, e este comando diz qual:")
            print()
            print("          modal app list")
            print()
            print("      . `pipi-edita` NÃO aparece na lista")
            print("             -> falta publicar:")
            print("                python -m modal deploy modal_edita.py")
            print()
            print("      . `pipi-edita` APARECE na lista")
            print("             -> o endereço que eu montei está errado.")
            print("                O certo sai no fim do deploy, na linha")
            print("                'Created web function'. Me mande ele.")
        elif erro.code == 503:
            print("      O endereço existe e o contêiner não respondeu.")
            print("      Veja o motivo com:  modal app logs pipi-edita")
        return 1
    except Exception as erro:
        print("\n  [x] Não consegui falar com a Modal.")
        print("      %s" % str(erro)[:240])
        return 1

    levou = time.time() - inicio

    if not saida.get("ok"):
        print("\n  [x] A Modal respondeu, mas recusou:")
        print("      %s" % saida.get("erro", "(sem motivo)"))
        print("\n      Não gravei nada no config.json.")
        return 1

    # A chave da imagem muda de nome entre versões do arquivo; aceito as
    # duas em vez de quebrar por um detalhe de nome.
    b64_saida = str(saida.get("imagem_b64") or saida.get("imagem") or "")
    if not b64_saida:
        print("\n  [x] A resposta veio sem imagem. Campos que chegaram: %s"
              % ", ".join(sorted(saida.keys())))
        return 1

    try:
        editada = Image.open(io.BytesIO(base64.b64decode(b64_saida)))
    except Exception as erro:
        print("\n  [x] Não consegui abrir a imagem que voltou: %s"
              % str(erro)[:150])
        return 1

    vermelho_depois = conta_vermelho(editada)

    print()
    print("  [dados] tempo .............. %.0fs" % levou)
    if saida.get("segundos"):
        print("  [dados] na placa ........... %.1fs" % saida["segundos"])
    if saida.get("vram_pico_gb"):
        print("  [dados] pico de memória .... %.1f GB (a L40S tem 48)"
              % saida["vram_pico_gb"])
    print("  [dados] vermelho na saída .. %.1f%%  (entrada: %.1f%%)"
          % (vermelho_depois * 100, vermelho_antes * 100))

    destino = BASE / "teste_da_edicao.png"
    try:
        destino.write_bytes(base64.b64decode(b64_saida))
        print("  [dados] gravei ............. %s" % destino.name)
    except Exception:
        pass

    # O QUADRADO OCUPA 25% DA IMAGEM. Exigir 8% é folgado o bastante para
    # aceitar um vermelho parcial ou com sombra, e apertado o bastante para
    # reprovar uma imagem que voltou igual.
    if vermelho_depois < 0.08:
        print()
        print("  [x] REPROVADO. A instrução era pintar de vermelho e a saída")
        print("      quase não tem vermelho. Ou ele devolveu a original, ou")
        print("      ignorou a instrução. Abra o %s e veja." % destino.name)
        print("\n      Não gravei nada no config.json.")
        return 1

    print()
    print("  [ok] ELE EDITOU DE VERDADE.")

    dados["edicao_modal"] = {"url": url, "token": token, "ligada": True}
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print("       Gravado no config.json da Pipi.")
    print()
    print("  Agora dá para fazer os botões de Trocar Fundo e Reiluminar")
    print("  na tela nova — com motor atrás deles, não só desenho.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
