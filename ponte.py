"""A PONTE ENTRE O BIGODE E A PIPI
Venure · venure.com.br · 17/09/2026

O Bigode pede uma imagem; a Pipi desenha e devolve. Este arquivo cuida do
unico detalhe delicado disso: provar que quem esta pedindo e o Bigode.

POR QUE PRECISA DE PROVA, SE OS DOIS RODAM NA MESMA MAQUINA
    Porque "na mesma maquina" inclui o SEU NAVEGADOR. Qualquer pagina
    aberta numa aba pode mandar um POST para http://127.0.0.1:7300 --
    isso se chama CSRF e e trivial. Sem prova, um site qualquer poderia
    ficar gerando imagem na sua conta da Modal ate o credito acabar.

    Duas condicoes, nao uma:
      1. a conexao vem de 127.0.0.1 (nao vem de fora da maquina);
      2. o pedido traz o segredo do arquivo ponte.txt.

    A segunda e o que barra a aba do navegador: uma pagina web nao
    consegue ler arquivo do seu disco, entao nao tem como saber o segredo.

POR QUE ARQUIVO, E NAO SENHA DIGITADA
    Ninguem vai digitar senha para o Bigode falar com a Pipi. O segredo
    nasce sozinho na primeira vez e fica no disco, ao lado dos dois
    projetos -- que e exatamente o que o `usuarios.json` compartilhado ja
    faz para o login.

    O ponte.txt esta no .gitignore. Ele nao vale nada fora desta maquina,
    mas segredo publicado vira habito de publicar segredo.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "ponte.txt"
CABECALHO = "X-Venure-Ponte"


def segredo():
    """Le o segredo; cria na primeira vez.

    Falhar ao criar NAO e fatal: sem segredo a ponte fica fechada e o
    Bigode continua desenhando pelo caminho antigo. Uma ferramenta a menos
    e melhor do que a Pipi nao abrir.
    """
    try:
        if ARQUIVO.is_file():
            valor = ARQUIVO.read_text(encoding="utf-8").strip()
            if valor:
                return valor
        valor = secrets.token_urlsafe(32)
        ARQUIVO.write_text(valor, encoding="utf-8")
        return valor
    except Exception:
        return ""


def confere(handler):
    """O pedido veio do Bigode desta maquina?"""
    esperado = segredo()
    if not esperado:
        return False, "a ponte nao foi configurada nesta instalacao"

    # 1) de onde veio
    try:
        origem = handler.client_address[0]
    except Exception:
        origem = ""
    if origem not in ("127.0.0.1", "::1", "localhost"):
        return False, "a ponte so atende esta maquina (veio de %s)" % (origem or "?")

    # 2) com o que veio
    recebido = (handler.headers.get(CABECALHO) or "").strip()
    if not recebido:
        return False, "sem o cabecalho %s" % CABECALHO
    # compare_digest: comparar segredo com == vaza o tamanho pelo tempo
    # gasto. Custa nada usar a forma certa.
    if not secrets.compare_digest(recebido, esperado):
        return False, "segredo da ponte nao confere"

    return True, ""


def caminho_para_o_bigode():
    """Onde o Bigode deve procurar este arquivo. So para mensagem de erro."""
    return str(ARQUIVO)


if __name__ == "__main__":
    # Util para conferir na mao que os dois lados leem o mesmo arquivo.
    s = segredo()
    print("ponte.txt : %s" % ARQUIVO)
    print("existe    : %s" % ARQUIVO.is_file())
    print("segredo   : %s...%s (%d caracteres)"
          % (s[:4], s[-4:], len(s)) if s else "segredo   : (nao consegui criar)")
    print("cabecalho : %s" % CABECALHO)
    print()
    print("O Bigode procura por este arquivo na pasta da Pipi.")
    print("Variavel PIPI_PASTA muda o lugar, se voce mover o projeto.")
    _ = os
