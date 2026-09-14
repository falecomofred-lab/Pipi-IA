"""LOGIN DA PIPI — a mesma conta do Bigode

A Pipi nao tem contas proprias. Ela usa o `autenticacao.py` do Cerebro e
o `usuarios.json` de la. Uma conta, dois programas.

POR QUE NAO COPIAR O usuarios.json PARA CA
    Seria mais simples e estaria errado. Duas listas de conta divergem no
    primeiro dia em que voce troca a senha num lado so -- e voce descobre
    quando ficar trancado fora de um dos dois, sem entender por que a
    senha "parou de funcionar".

    Aqui nao ha copia. A Pipi aponta a variavel BIGODE_USUARIOS para o
    arquivo do Cerebro e as duas leem a mesma verdade.

ONDE ELA PROCURA O CEREBRO
    1. a variavel BIGODE_CEREBRO, se voce definir
    2. ..\\Cerebro          (o vizinho, que e o caso normal)
    3. C:\\Users\\<voce>\\Downloads\\Cerebro
    4. a copia do pendrive

    A primeira que tiver um autenticacao.py vence.

SE ELA NAO ACHAR
    A Pipi abre assim mesmo, SEM login. Trancar a ferramenta porque o
    vizinho mudou de lugar seria pior do que deixar entrar: aqui nao ha
    dado de terceiro, e a Pipi escuta so em 127.0.0.1.
    A tela avisa, em vez de mentir que esta protegida.

Venure - venure.com.br
"""

import os
import sys
from http import cookies
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

_CANDIDATOS = [
    os.environ.get("BIGODE_CEREBRO", "").strip(),
    str(RAIZ.parent / "Cerebro"),
    str(Path.home() / "Downloads" / "Cerebro"),
    r"G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro",
]

CEREBRO = None
autenticacao = None
PORQUE = ""

for _c in _CANDIDATOS:
    if not _c:
        continue
    _p = Path(_c)
    if (_p / "autenticacao.py").is_file():
        CEREBRO = _p
        break

if CEREBRO is None:
    PORQUE = "nao achei a pasta do Cerebro (procurei em: %s)" % ", ".join(
        [c for c in _CANDIDATOS if c])
else:
    # BIGODE_USUARIOS precisa estar definido ANTES do import: o
    # autenticacao.py le a variavel no momento em que e carregado.
    os.environ.setdefault("BIGODE_USUARIOS", str(CEREBRO / "usuarios.json"))
    if str(CEREBRO) not in sys.path:
        sys.path.insert(0, str(CEREBRO))
    try:
        import autenticacao  # noqa: E402
    except Exception as erro:
        autenticacao = None
        PORQUE = "achei o Cerebro em %s mas nao consegui carregar o " \
                 "autenticacao.py: %s" % (CEREBRO, erro)

COOKIE = "pipi_sessao"


def ligado():
    """Da para exigir login? So quando ha modulo E ha pelo menos uma conta.

    A segunda metade importa: numa instalacao nova o usuarios.json esta
    vazio, e exigir login ali trancaria voce para fora da sua propria
    ferramenta, sem tela de criar conta para socorrer. Quem cria conta e
    o Bigode."""
    if autenticacao is None:
        return False
    try:
        return autenticacao.existe_alguem()
    except Exception:
        return False


def motivo():
    """Por que o login esta desligado, em uma frase, para a tela mostrar."""
    if autenticacao is None:
        return PORQUE
    if not ligado():
        return ("o Cerebro ainda nao tem nenhuma conta criada -- crie a sua "
                "no Bigode e ela vale aqui tambem")
    return ""


def token_do_pedido(handler):
    bruto = handler.headers.get("Cookie", "")
    if not bruto:
        return ""
    try:
        c = cookies.SimpleCookie()
        c.load(bruto)
        return c[COOKIE].value if COOKIE in c else ""
    except Exception:
        return ""


def sessao(handler):
    """Quem esta falando comigo? None quando ninguem.

    A funcao no Cerebro chama-se `sessao_de`. A primeira versao deste
    arquivo chutou `ver_sessao` com um fallback para `sessao` -- nenhum
    dos dois existe. O fallback e que era o veneno: em vez de estourar
    na cara, ele engolia o AttributeError e devolvia None, e a Pipi
    ficaria dizendo "faca login" para sempre, inclusive depois de voce
    entrar com a senha certa.

    Quando nao se sabe o nome de uma funcao, o certo e ir ler -- nao
    tentar tres e ficar com o silencio do que sobrar."""
    if autenticacao is None:
        return None
    t = token_do_pedido(handler)
    if not t:
        return None
    try:
        return autenticacao.sessao_de(t)
    except Exception:
        return None


def autorizado(handler):
    if not ligado():
        return True                 # sem login configurado, passa
    return sessao(handler) is not None


def entrar(email, senha):
    """Devolve (ok, cookie_ou_erro)."""
    if autenticacao is None:
        return False, "login indisponivel: " + PORQUE
    try:
        r = autenticacao.conferir(email, senha)
    except Exception as erro:
        return False, str(erro)

    if not r or not r.get("ok"):
        return False, (r or {}).get("erro", "E-mail ou senha nao conferem.")

    # `conferir` devolve os campos na raiz -- {"ok","email","nome","foto"} --
    # e nao dentro de um "usuario". Ler do lugar errado nao daria erro:
    # abriria a sessao com nome vazio, e o "Ola, " sem nome ficaria ali
    # para sempre sem ninguem saber de onde veio.
    token = autenticacao.abrir_sessao(r.get("email", email),
                                      r.get("nome", ""), r.get("foto", ""))
    # HttpOnly: o JavaScript da pagina nao le o cracha, entao um script
    # injetado numa aba nao consegue roubar a sessao.
    # SameSite=Lax: o cracha nao viaja em pedido vindo de outro site.
    return True, ("%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d"
                  % (COOKIE, token, 30 * 86400))


def sair(handler):
    if autenticacao is not None:
        t = token_do_pedido(handler)
        if t:
            try:
                autenticacao.fechar_sessao(t)
            except Exception:
                pass
    return "%s=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" % COOKIE
