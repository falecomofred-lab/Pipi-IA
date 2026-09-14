"""APONTAR A PIPI PARA A MODAL

Rode NO SEU WINDOWS, na pasta da Pipi IA:

    python usar_modal.py

Ele pede o endereco que o `modal deploy` imprimiu e o token que voce
criou, testa gerando uma imagem de verdade, e so grava se funcionar.

POR QUE TESTAR GERANDO
    Um ping nao prova nada aqui. O endpoint de teste antigo respondia
    200 e dizia "Processamento simulado com sucesso" -- passaria em
    qualquer verificacao superficial e nao geraria imagem nenhuma.

    A unica prova que serve e pedir uma imagem e receber pixels. Custa
    alguns segundos de GPU do seu credito. Vale: e mais barato do que
    descobrir na hora de entregar trabalho de cliente.

PARA DESLIGAR

    python usar_modal.py --remover

Venure - venure.com.br
"""

import sys
from pathlib import Path

import modal_cliente

RAIZ = Path(__file__).resolve().parent


def main():
    if "--remover" in sys.argv:
        if modal_cliente.CONFIG.is_file():
            modal_cliente.CONFIG.unlink()
        print("\n  Pronto. A Pipi volta a usar o ComfyUI.\n")
        return

    print()
    print("=" * 68)
    print("  USAR A MODAL")
    print("=" * 68)
    print()
    print("  1. Cole o endereco que o `modal deploy` imprimiu.")
    print("     Ele termina em .modal.run e NAO muda mais.")
    print()
    url = input("  endereco > ").strip().rstrip("/")

    if not url.startswith("http"):
        raise SystemExit("\n  Isso nao e um endereco. Comece com https://\n")

    print()
    print("  2. Cole o token que voce usou no `modal secret create`.")
    print()
    token = input("  token > ").strip()
    if not token:
        raise SystemExit("\n  Sem token nao da: o endereco e publico.\n")

    modal_cliente.gravar(url, token)

    print()
    print("  Testando de verdade -- vou pedir uma imagem.")
    print("  O primeiro pedido acorda o container e leva de 30s a 2 min.")
    print()

    try:
        caminho, segundos, licenca = modal_cliente.gerar(
            "um gato de bigode branco sentado numa poltrona de veludo, "
            "luz de fim de tarde pela janela, fotografia",
            formato="quadrado", passos=4,
            destino=RAIZ / "producao" / "teste_modal.png")
    except Exception as erro:
        # Nao deixa configuracao quebrada gravada: seria pior do que
        # nenhuma, porque a Pipi tentaria usar e falharia toda vez.
        if modal_cliente.CONFIG.is_file():
            modal_cliente.CONFIG.unlink()
        texto = str(erro)
        print("  NAO GRAVEI NADA")
        print()
        print("  " + texto)
        print()

        # QUANDO JA SE SABE A CAUSA, NAO SE PEDE INVESTIGACAO   (13/09)
        #
        #   Antes esta lista de tres perguntas saia SEMPRE -- inclusive
        #   logo abaixo de uma mensagem que ja dizia exatamente qual era
        #   o problema. Ler "o endereco e o do teste antigo" e, na linha
        #   seguinte, "confira se o endereco e o do teste antigo" faz a
        #   pessoa duvidar do diagnostico que estava certo.
        #
        #   A lista so aparece agora quando a falha NAO se explicou.
        if "ENDPOINT DE TESTE" not in texto and "Token" not in texto:
            print("  Confira:")
            print("    . o deploy terminou sem erro?")
            print("    . o token e o mesmo do `modal secret create pipi-token`?")
            print()
        print("=" * 68)
        print()
        return

    print("  FUNCIONOU.")
    print()
    print("    imagem ... %s" % caminho)
    print("    tempo .... %ss" % segundos)
    print("    licenca .. %s" % licenca)
    print()
    print("  Abra o arquivo para conferir que saiu imagem de verdade.")
    print("  A partir de agora a Pipi usa a Modal.")
    print()
    print("  Para voltar ao ComfyUI:  python usar_modal.py --remover")
    print("=" * 68)
    print()


if __name__ == "__main__":
    main()
