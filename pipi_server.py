#!/usr/bin/env python3
"""PIPI IA — servidor da tela
Venure · venure.com.br · 17/09/2026

Um motor so: a Modal. O desenho acontece numa NVIDIA L40S na nuvem, no
FLUX.1-schnell. Este arquivo nao desenha nada -- ele mostra a tela, cuida
do login, enfileira o pedido e guarda a imagem que voltou.

POR QUE SO A MODAL                                            (17/09)
    Ate hoje havia tres caminhos aqui: ComfyUI (local ou no Colab),
    Hugging Face e Modal. Dois deles nunca chegaram a desenhar nesta
    maquina -- o ComfyUI local roda num PyTorch +cpu que ignora placa, e o
    Hugging Face exigia um token que nunca foi posto.

    Tres caminhos significam tres jeitos de falhar, tres mensagens de erro
    para entender e tres lugares para consertar quando algo quebra. Dois
    deles eram caminho morto. Sobrou o que funciona.

    O que saiu de cena esta na quarentena que o LIMPAR_PIPI.ps1 cria, com
    um LEIA-ME dizendo o que era cada arquivo.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# A MODAL E OBRIGATORIA, MAS O IMPORT NAO PODE DERRUBAR A TELA
#
#     Se o modal_cliente nao carregar, a Pipi abre e DIZ que nao carregou,
#     em vez de morrer na partida com um traceback. Uma ferramenta que nao
#     abre nao consegue explicar por que nao abre.
try:
    import modal_cliente
except Exception as _erro_modal:
    class _ModalAusente:
        _porque = str(_erro_modal)

        @staticmethod
        def configurado():
            return False

        @classmethod
        def status(cls):
            return {'configurado': False, 'online': False,
                    'erro': 'modal_cliente indisponivel: ' + cls._porque}

        @classmethod
        def endereco(cls):
            return ''

        @classmethod
        def gerar(cls, *a, **k):
            raise RuntimeError('Modal indisponivel: ' + cls._porque)

    modal_cliente = _ModalAusente()

# O escritor de prompt e OPCIONAL: ele depende do Bigode estar instalado
# ao lado. Sem ele a Pipi continua desenhando o que voce escrever a mao.
try:
    import escritor
except Exception as _erro_escritor:
    class _EscritorAusente:
        _porque = str(_erro_escritor)

        @staticmethod
        def disponivel():
            return False

        @classmethod
        def escrever(cls, *a, **k):
            raise RuntimeError('escritor indisponivel: ' + cls._porque)

    escritor = _EscritorAusente()

# A ponte com o Bigode. Opcional pelo mesmo motivo dos outros: se nao
# carregar, a Pipi abre normalmente e so a ponte fica fechada.
try:
    import ponte
except Exception as _erro_ponte:
    class _PonteAusente:
        CABECALHO = 'X-Venure-Ponte'

        @staticmethod
        def segredo():
            return ''

        @classmethod
        def confere(cls, h):
            return False, 'ponte indisponivel: %s' % _erro_ponte

    ponte = _PonteAusente()

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
OUT = ROOT / 'producao'
OUT.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# O QUE A TELA MOSTRA NO PAINEL
# ----------------------------------------------------------------------
# Escrito aqui, num lugar so, porque a tela nao deve adivinhar nada sobre
# o motor: ela pergunta e mostra. Quando a placa ou o modelo mudarem no
# modal_pipi.py, muda aqui tambem -- e a tela acompanha sem ser tocada.
PLACA = 'NVIDIA L40S · 48 GB'
MODELO = 'FLUX.1-schnell'
LICENCA = 'Apache 2.0 — uso comercial liberado'
PRECO_SEG = 0.000542          # L40S, tabela da Modal em 17/09/2026
TETO_MES = 30.00              # o credito do plano Starter

FORMATOS = {
    'quadrado': (1024, 1024),
    'retrato': (832, 1216),
    'paisagem': (1216, 832),
    'story': (768, 1344),
    'capa': (1344, 768),
}

JOBS = {}
LOCK = threading.RLock()

# ----------------------------------------------------------------------
# TIPO CERTO PARA CADA ARQUIVO                                  (13/09)
#
#     Tudo era servido como 'application/octet-stream'. Para imagem o
#     navegador ate adivinha pelo conteudo -- mas FOLHA DE ESTILO ele
#     recusa: um .css que chega com octet-stream e ignorado EM SILENCIO.
#     A pagina aparecia crua e nada explicava o motivo.
# ----------------------------------------------------------------------
TIPOS = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.webp': 'image/webp', '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2', '.woff': 'font/woff',
    '.txt': 'text/plain; charset=utf-8',
}

# Onde fica o web\ do Cerebro, para reaproveitar o venure.css. UM arquivo
# de estilo servido pelas duas ferramentas: consertar um detalhe aqui
# conserta no Bigode tambem.
CEREBRO_WEB = None
for _c in (os.environ.get('BIGODE_CEREBRO', '').strip(),
           str(ROOT.parent / 'Cerebro'),
           str(Path.home() / 'Downloads' / 'Cerebro')):
    if _c and (Path(_c) / 'web').is_dir():
        CEREBRO_WEB = Path(_c) / 'web'
        break


def pasta_no_drive():
    """Endereco da pasta producao/ no site do Google Drive, ou ''.

    A producao/ ja FICA dentro do Google Drive (G:\\Meu Drive\\...), entao o
    mosaico da pagina ja e o espelho dela: o Drive sobe o arquivo sozinho e
    a pagina le o local, que aparece na hora. O que falta e so o endereco
    para abrir a mesma pasta no navegador e mandar para um cliente.

    Esse endereco o programa nao tem como adivinhar -- o ID da pasta so
    existe na conta de quem usa. Entao le de drive.txt (ou da variavel
    PIPI_DRIVE) e, sem isso, devolve '' e o link simplesmente nao aparece.
    Link quebrado num produto e pior do que link nenhum.

    Para preencher: abra a pasta producao no drive.google.com e cole a URL
    da barra de enderecos dentro de um arquivo chamado drive.txt, aqui.
    """
    url = (os.environ.get('PIPI_DRIVE') or '').strip()
    if not url:
        try:
            url = (ROOT / 'drive.txt').read_text(encoding='utf-8').strip()
        except Exception:
            url = ''
    # So http(s). Um "javascript:..." gravado no arquivo viraria um clique
    # armado dentro da sua propria pagina -- a checagem custa uma linha.
    return url if url.startswith(('https://', 'http://')) else ''


# ----------------------------------------------------------------------
# GASTO DO CICLO
# ----------------------------------------------------------------------
# A Modal nao publica "credito restante". Ela publica o GASTO, pelo
# modal.billing. O restante e uma subtracao do teto de $30 do plano.
#
# Dizer "gastei X dos $30" e honesto. Dizer "restam Y" sem saber a data de
# virada do ciclo seria chute com cara de numero.
#
# ISTO NUNCA PODE QUEBRAR A TELA
#     E uma consulta externa, com credencial local, que pode falhar por
#     dez motivos que nao tem nada a ver com desenhar imagem. Roda em
#     thread, com cache de 10 minutos, e qualquer falha vira um campo
#     'erro' no painel -- nao um 500 na pagina.
_CACHE_GASTO = {'quando': 0.0, 'valor': None, 'erro': ''}
_LOCK_GASTO = threading.Lock()


def _consultar_gasto():
    """Pergunta a Modal quanto ja foi gasto no mes. Roda em subprocesso.

    POR QUE SUBPROCESSO, E NAO `import modal`
        O pacote modal puxa grpclib, protobuf e um cliente assincrono.
        Importar isso dentro do servidor da tela deixaria a partida mais
        lenta para todo mundo, por um numero que aparece num canto do
        painel. E se o import explodir, explode longe daqui.
    """
    codigo = (
        "import datetime, json, modal.billing as b;"
        "h=datetime.datetime.now(datetime.timezone.utc);"
        "i=h.replace(day=1,hour=0,minute=0,second=0,microsecond=0);"
        "r=b.workspace_billing_report(start=i,end=h,resolution='d');"
        "print(json.dumps(float(sum(float(x['cost']) for x in r))))"
    )
    saida = subprocess.run([sys.executable, '-c', codigo],
                           capture_output=True, text=True, timeout=60)
    if saida.returncode != 0:
        raise RuntimeError((saida.stderr or saida.stdout or '').strip()[-200:])
    return float(json.loads(saida.stdout.strip().splitlines()[-1]))


_GASTO_RODANDO = {'sim': False}


def _atualizar_gasto():
    try:
        valor = _consultar_gasto()
        novo = {'quando': time.time(), 'valor': valor, 'erro': ''}
    except Exception as exc:
        novo = {'quando': time.time(), 'valor': None,
                'erro': str(exc)[:200] or 'nao consegui consultar'}
    with _LOCK_GASTO:
        _CACHE_GASTO.update(novo)
        _GASTO_RODANDO['sim'] = False


def gasto_do_ciclo():
    """O gasto do mes, SEM segurar a tela.                        (29/09)

    A consulta a Modal roda num subprocesso que pode levar ate 60 s (com a
    conta parada, leva). Antes a tela ficava esperando e o navegador
    desistia -- no console aparecia ConnectionAbortedError [WinError 10053].
    Agora devolve o ultimo valor guardado na hora e atualiza em segundo
    plano.
    """
    with _LOCK_GASTO:
        idade = time.time() - _CACHE_GASTO['quando']
        velho = not _CACHE_GASTO['quando'] or idade >= 600
        if velho and not _GASTO_RODANDO['sim']:
            _GASTO_RODANDO['sim'] = True
            threading.Thread(target=_atualizar_gasto, daemon=True).start()
        atual = dict(_CACHE_GASTO)
    if not atual['quando']:
        atual['erro'] = 'consultando o gasto na Modal...'
    return atual


def painel():
    """Tudo o que a tela precisa saber sobre o motor, numa resposta."""
    st = modal_cliente.status()
    g = gasto_do_ciclo()
    pronto = bool(st.get('configurado')) or _cloudflare_pronta()
    dados = {
        'ok': True,
        'pronto': pronto,
        'motor': 'Modal',
        'placa': PLACA,
        'modelo': MODELO,
        'licenca': LICENCA,
        'endereco': modal_cliente.endereco(),
        'preco_segundo': PRECO_SEG,
        'teto_mes': TETO_MES,
        'producao': str(OUT),
        'formatos': list(FORMATOS.keys()),
        # A tela esconde o botao "melhorar" quando nao ha com o que melhorar.
        'escritor': escritor.disponivel(),
        # 18/09: era 180, e nao cabia. O teto real e de 256 TOKENS do T5,
        # e prosa de fotografia gasta ~1,4 token por palavra -- 180 dava
        # 252 no melhor caso e 288 no pior, ou seja, corte em silencio.
        # 120 cabe de verdade. O numero exato de cada imagem vem medido da
        # Modal e aparece embaixo dela.
        'palavras_max': 120,
        # Reserva gratuita (29/09): mesmo FLUX.1-schnell na Cloudflare.
        'reserva': 'Cloudflare Workers AI' if _cloudflare_pronta() else '',
    }
    if not pronto:
        dados['motivo'] = (st.get('erro')
                           or 'A Modal nao esta configurada. '
                              'Rode: python usar_modal.py')
    if g['valor'] is None:
        dados['credito'] = {'erro': g['erro']}
    else:
        dados['credito'] = {
            'gasto': round(g['valor'], 2),
            'teto': TETO_MES,
            'restante': round(max(0.0, TETO_MES - g['valor']), 2),
        }
    return dados


# ----------------------------------------------------------------------
# O PEDIDO
# ----------------------------------------------------------------------
# RESERVA GRATUITA: CLOUDFLARE                               (29/09)
#   Se a Modal nao desenhar (conta parada, sem credito, fora do ar), o
#   mesmo FLUX.1-schnell roda na Cloudflare Workers AI, de graca ate ~170
#   imagens por dia. Ver cloudflare_cliente.py.
try:
    import cloudflare_cliente
except Exception:
    cloudflare_cliente = None


def _cloudflare_pronta():
    try:
        return bool(cloudflare_cliente and cloudflare_cliente.configurado())
    except Exception:
        return False


def _desenhar(jid, prompt, payload):
    destino = OUT / (jid + '.png')
    args = dict(formato=payload.get('formato') or 'quadrado',
                passos=payload.get('passos') or 4,
                semente=payload.get('semente') or 0,
                destino=destino)
    falha_modal = ''
    if modal_cliente.configurado():
        try:
            caminho, segundos, licenca, extra = modal_cliente.gerar(prompt, **args)
            extra = dict(extra or {})
            extra.setdefault('motor', 'Modal')
            return caminho, segundos, licenca, extra
        except Exception as exc:
            falha_modal = str(exc)[:200]
            if not _cloudflare_pronta():
                raise
    if not _cloudflare_pronta():
        raise RuntimeError(
            'Nenhum motor configurado. Modal: python usar_modal.py | '
            'Cloudflare: preencha o cloudflare.json')
    with LOCK:
        JOBS[jid]['estado'] = 'desenhando na Cloudflare (reserva gratis)'
    caminho, segundos, licenca, extra = cloudflare_cliente.gerar(prompt, **args)
    extra = dict(extra or {})
    if falha_modal:
        extra['aviso'] = 'A Modal nao desenhou (%s). Usei a Cloudflare.' % falha_modal
    return caminho, segundos, licenca, extra


def run(jid, prompt, payload):
    with LOCK:
        JOBS[jid]['estado'] = 'acordando a placa'
    try:
        if not modal_cliente.configurado() and not _cloudflare_pronta():
            raise RuntimeError(
                'A Modal nao esta configurada. Na pasta da Pipi, rode: '
                'python usar_modal.py (ou preencha o cloudflare.json)')

        caminho, segundos, licenca, extra = _desenhar(jid, prompt, payload)

        # O QUE VAI PARA A TELA E UM ENDERECO, NAO UM CAMINHO   (13/09)
        #
        #   Aqui ia "G:\\Meu Drive\\...\\pipi_x.png". A tela procura algo
        #   parecido com URL para montar o <img>; caminho do Windows nunca
        #   casa -- e mesmo que casasse, o navegador nao abre arquivo local
        #   por conta propria. A imagem saia certinha na pasta e a tela
        #   mostrava so texto.
        nome = Path(caminho).name
        custo = None
        try:
            custo = round(float(segundos) * PRECO_SEG, 4)
        except Exception:
            pass
        if (extra or {}).get('custo_usd') is not None:
            custo = extra['custo_usd']          # Cloudflare: cota gratis

        with LOCK:
            JOBS[jid].update(estado='concluido',
                             resultado='/producao/' + nome,
                             arquivo=str(caminho), nome=nome,
                             segundos=segundos, licenca=licenca,
                             custo_usd=custo,
                             # Medicao do T5 na Modal, nao estimativa daqui.
                             tokens=(extra or {}).get('tokens'),
                             teto_tokens=(extra or {}).get('teto_tokens', 256),
                             cortou=bool((extra or {}).get('cortou')),
                             motor=(extra or {}).get('motor', 'Modal'),
                             aviso=(extra or {}).get('aviso', ''))
    except Exception as exc:
        with LOCK:
            JOBS[jid].update(estado='erro', erro=str(exc))


def job(prompt, payload):
    jid = 'pipi_' + uuid.uuid4().hex[:12]
    with LOCK:
        JOBS[jid] = {'id': jid, 'estado': 'fila', 'criado_em': time.time(),
                     'prompt': prompt, 'resultado': None, 'erro': ''}
    threading.Thread(target=run, args=(jid, prompt, payload),
                     daemon=True).start()
    return jid


# ----------------------------------------------------------------------
# LOGIN
# ----------------------------------------------------------------------
# Opcional pelo mesmo motivo do import da Modal: se o modulo nao carregar,
# a Pipi abre SEM login em vez de trancar. Aqui nao ha dado de terceiro e
# ela escuta so em 127.0.0.1 -- ficar trancado fora da propria ferramenta
# por causa de um import seria estrago maior do que o risco evitado.
try:
    import login_venure
except Exception as _e_login:
    class _SemLogin:
        @staticmethod
        def ligado():
            return False

        @staticmethod
        def autorizado(h):
            return True

        @staticmethod
        def motivo():
            return 'login_venure indisponivel: %s' % _e_login

        @staticmethod
        def sessao(h):
            return None

        # ESTES DOIS FALTAVAM NA VERSAO ANTERIOR                (17/09)
        #   O fallback nao tinha `entrar` nem `sair`. Se o login_venure
        #   falhasse ao importar, a tela abria sem login (certo) e depois
        #   estourava AttributeError em qualquer POST /api/entrar -- que e
        #   justamente o que alguem tentaria ao ver a tela estranha.
        @staticmethod
        def entrar(email, senha):
            return False, 'Login indisponivel nesta instalacao.'

        @staticmethod
        def sair(h):
            return ''

    login_venure = _SemLogin()


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# O ICONE DO APP
# ----------------------------------------------------------------------
# O manifest.json tinha "icons": [] -- vazio. E por isso que o Chrome nunca
# ofereceu "Instalar app": ele exige pelo menos um icone de 192 e um de 512
# para tratar a pagina como aplicativo. Sem isso a Pipi era so uma aba.
#
# DESENHADO EM CODIGO, COMO NO BIGODE
#     Escrever PNG na mao com zlib e struct nao e exibicao: e nao depender
#     de Pillow. A Pipi nao instala nada alem do `modal` (ver o
#     requirements.txt), e o icone nao vale uma dependencia nova.
#
#     Se um dia voce puser web/img/icone-192.png e icone-512.png na pasta,
#     eles ganham -- a foto da gata fica melhor que qualquer desenho. Ate
#     la, este serve.
#
# POR QUE FUNDO CHEIO E NAO A FOTO RECORTADA
#     A mesma licao que o Bigode aprendeu: recorte transparente DESAPARECE
#     na barra escura do Chrome. Sobrava um queixo branco flutuando.
_ICONES = {}


def _icone_desenhado(lado):
    """RESERVA, e so isso. O icone oficial e a foto da gata.

    Este desenho existe para a Pipi nunca ficar SEM icone -- se alguem
    apagar a pasta de imagens, ainda aparece algo com a cara da marca.

    O icone de verdade sao os arquivos web/img/icone-*.png, feitos pelo
    `fazer_icones.py` do Cerebro: a foto da gata sobre rosa claro. O
    `icone()` logo abaixo prefere esses arquivos e so cai aqui se eles
    nao existirem.
    """
    import struct
    import zlib

    linhas = bytearray()
    raio = lado * 0.22
    for y in range(lado):
        linhas.append(0)                        # filtro da linha
        for x in range(lado):
            # cantos arredondados
            dx = min(x, lado - 1 - x)
            dy = min(y, lado - 1 - y)
            if dx < raio and dy < raio and \
                    ((raio - dx) ** 2 + (raio - dy) ** 2) > raio * raio:
                linhas += bytes((0, 0, 0, 0))
                continue

            # Rosa queimado (#E0849B) para o vinho (#C96A85), na diagonal --
            # as mesmas duas cores do botao da tela.
            t = (x + y) / (2.0 * lado)
            r = int(224 + (201 - 224) * t)
            g = int(132 + (106 - 132) * t)
            b = int(155 + (133 - 155) * t)

            # O V da Venure, no mesmo desenho do icone do Bigode.
            nx = (x / lado - 0.5) * 2
            ny = (y / lado - 0.28) * 2
            no_v = (abs(abs(nx) * 1.35 - ny) < 0.20) and (-0.1 < ny < 1.25)
            linhas += bytes((43, 17, 25, 255)) if no_v else bytes((r, g, b, 255))

    def bloco(tipo, dados):
        c = tipo + dados
        return (struct.pack(">I", len(dados)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    cabecalho = struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", cabecalho)
            + bloco(b"IDAT", zlib.compress(bytes(linhas), 9))
            + bloco(b"IEND", b""))


def icone(lado):
    """A foto da gata sobre rosa claro, no tamanho pedido.

    Procura o arquivo EXATO primeiro. Antes eu pegava "o mais proximo por
    cima", o que fazia o icone de 16 px da aba ser um PNG de 180 encolhido
    pelo navegador -- e navegador encolhe pior que o Pillow.
    """
    if lado in _ICONES:
        return _ICONES[lado]

    arq = WEB / 'img' / ('icone-%d.png' % lado)
    if arq.is_file():
        _ICONES[lado] = arq.read_bytes()
        return _ICONES[lado]

    # Sem o tamanho exato, o mais proximo por cima -- nunca ampliando.
    for tamanho in (16, 32, 48, 64, 128, 180, 192, 512):
        if tamanho >= lado:
            arq = WEB / 'img' / ('icone-%d.png' % tamanho)
            if arq.is_file():
                _ICONES[lado] = arq.read_bytes()
                return _ICONES[lado]

    _ICONES[lado] = _icone_desenhado(lado)
    return _ICONES[lado]


def enviar_png(h, dados):
    h.send_response(200)
    h.send_header('Content-Type', 'image/png')
    h.send_header('Content-Length', str(len(dados)))
    # O Chrome guarda icone com afinco. Uma hora e o suficiente para nao
    # redesenhar a cada visita, e curto o bastante para a troca aparecer.
    h.send_header('Cache-Control', 'public, max-age=3600')
    h.end_headers()
    h.wfile.write(dados)


def _transcrever_no_bigode(audio):
    """Manda o WAV para o /api/transcrever do Bigode e devolve a resposta.

    Falhar aqui nao e erro fatal: a tela tem o ditado do Chrome como
    reserva. Por isso devolve ok:false com motivo, em vez de estourar.
    """
    import urllib.error
    import urllib.request

    if not audio:
        return {'ok': False, 'erro': 'áudio vazio'}

    base = (os.environ.get('BIGODE_URL') or 'http://127.0.0.1:7000').rstrip('/')
    try:
        pedido = urllib.request.Request(
            base + '/api/transcrever', data=audio,
            headers={'Content-Type': 'audio/wav'}, method='POST')
        with urllib.request.urlopen(pedido, timeout=120) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        return {'ok': False,
                'erro': 'O Bigode respondeu %s ao transcrever.' % e.code}
    except Exception:
        return {'ok': False,
                'erro': 'O Bigode não está aberto — usando o ditado do navegador.'}


def enviar_arquivo(h, caminho):
    dados = caminho.read_bytes()
    h.send_response(200)
    h.send_header('Content-Type',
                  TIPOS.get(caminho.suffix.lower(), 'application/octet-stream'))
    h.send_header('Content-Length', str(len(dados)))
    h.end_headers()
    h.wfile.write(dados)


def send_json(h, status, data):
    raw = json.dumps(data, ensure_ascii=False).encode()
    try:
        h.send_response(status)
        h.send_header('Content-Type', 'application/json; charset=utf-8')
        h.send_header('Content-Length', str(len(raw)))
        h.end_headers()
        h.wfile.write(raw)
    except (ConnectionError, OSError):
        pass      # o navegador fechou antes (WinError 10053): nada a fazer


def send_json_cookie(h, status, data, cookie):
    raw = json.dumps(data, ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header('Content-Type', 'application/json; charset=utf-8')
    if cookie:
        h.send_header('Set-Cookie', cookie)
    h.send_header('Content-Length', str(len(raw)))
    h.end_headers()
    h.wfile.write(raw)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    # Rotas que respondem SEM login. A tela e o /api/eu precisam sair antes
    # de existir sessao, senao a pagina de entrar aparece crua.
    LIVRES = ('/', '/index.html', '/api/eu', '/api/entrar', '/api/sair',
              '/venure.css', '/voz.js', '/manifest.json', '/img/',
              '/favicon', '/icone-', '/apple-touch-icon')

    def _livre(self, path):
        return any(path == r or path.startswith(r) for r in self.LIVRES)

    def _barrado(self, path):
        if self._livre(path):
            return False
        if login_venure.autorizado(self):
            return False
        send_json(self, 401, {'ok': False, 'erro': 'Faça login para usar a Pipi.'})
        return True

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/api/eu':
            s = login_venure.sessao(self)
            return send_json(self, 200, {
                'ok': True, 'exige': login_venure.ligado(),
                'logado': bool(s), 'nome': (s or {}).get('nome', ''),
                'motivo': login_venure.motivo()})

        if self._barrado(path):
            return

        # UMA ROTA SO PARA O PAINEL                             (17/09)
        #
        #   Antes eram tres (/api/health, /api/imagens, /api/huggingface),
        #   cada uma com um pedaco da verdade -- e foi assim que a tela
        #   passou a dizer "sem motor" com a Modal funcionando: ela lia a
        #   rota que nao sabia da Modal.
        if path in ('/api/estado', '/api/health'):
            return send_json(self, 200, painel())

        # O MOSAICO DAS CRIACOES                               (17/09)
        #
        #   O historico antigo guardava so o TEXTO do pedido, no navegador.
        #   Trocar de navegador e a lista sumia -- e as imagens, que estao
        #   no disco, nunca apareciam juntas. Aqui a fonte da verdade e a
        #   pasta producao\, que e onde elas realmente estao.
        if path == '/api/galeria':
            itens = []
            total = 0
            try:
                arquivos = [p for p in OUT.iterdir()
                            if p.is_file() and p.suffix.lower() in
                            ('.png', '.jpg', '.jpeg', '.webp')]
                arquivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                for p in arquivos[:120]:      # teto: 120 miniaturas bastam
                    st = p.stat()
                    total += st.st_size
                    itens.append({
                        'nome': p.name,
                        'url': '/producao/' + p.name,
                        'bytes': st.st_size,
                        'quando': time.strftime('%d/%m %H:%M',
                                                time.localtime(st.st_mtime)),
                    })
            except Exception as exc:
                return send_json(self, 200, {'ok': False, 'imagens': [],
                                             'erro': str(exc)[:200]})
            return send_json(self, 200, {
                'ok': True, 'imagens': itens,
                'pasta': str(OUT),
                'drive': pasta_no_drive(),
                'tamanho': '%.1f MB' % (total / 1e6) if total else '0 MB'})

        if path == '/api/logs':
            with LOCK:
                jobs = list(JOBS.values())[-40:]
            return send_json(self, 200, {'ok': True, 'jobs': jobs})

        if path.startswith('/api/imagens/job/'):
            jid = path.rsplit('/', 1)[-1]
            item = JOBS.get(jid)
            return send_json(self, 200 if item else 404,
                             item or {'ok': False, 'erro': 'job não encontrado'})

        if path in ('/', '/index.html'):
            return enviar_arquivo(self, WEB / 'index.html')

        # As imagens que a Pipi produziu.
        if path.startswith('/producao/'):
            alvo = (OUT / path[len('/producao/'):]).resolve()
            if str(alvo).startswith(str(OUT.resolve())) and alvo.is_file():
                return enviar_arquivo(self, alvo)
            return send_json(self, 404, {'ok': False, 'erro': 'imagem não encontrada'})

        # O manifesto mora na RAIZ, nao em web\.
        if path == '/manifest.json' and (ROOT / 'manifest.json').is_file():
            return enviar_arquivo(self, ROOT / 'manifest.json')

        # Os icones do aplicativo. Sem estas rotas o Chrome nao oferece
        # "Instalar app" -- ele exige 192 e 512 de verdade, servidos.
        if path == '/icone-192.png':
            return enviar_png(self, icone(192))
        if path == '/icone-512.png':
            return enviar_png(self, icone(512))
        if path.startswith('/apple-touch-icon'):
            return enviar_png(self, icone(180))
        if path.startswith('/favicon'):
            return enviar_png(self, icone(192))

        # Os dois arquivos que a Pipi divide com o Bigode: o estilo e a
        # captacao de voz. Procura aqui primeiro; se nao houver, pega o do
        # Cerebro -- assim existe UM de cada, e um conserto vale para os
        # dois projetos.
        if path in ('/venure.css', '/voz.js'):
            nome = path.lstrip('/')
            for c in (WEB / nome,
                      (CEREBRO_WEB / nome) if CEREBRO_WEB else None):
                if c and c.is_file():
                    return enviar_arquivo(self, c)
            return send_json(self, 404, {'ok': False,
                                         'erro': '%s não encontrado' % nome})

        alvo = (WEB / path.lstrip('/')).resolve()
        if str(alvo).startswith(str(WEB.resolve())) and alvo.is_file():
            return enviar_arquivo(self, alvo)
        send_json(self, 404, {'ok': False, 'erro': 'rota não encontrada'})

    def do_POST(self):
        path = urlparse(self.path).path

        # VOZ: UM WHISPER SO, PARA AS DUAS FERRAMENTAS          (17/09)
        #
        #   O Bigode ja tem transcricao por Whisper local, em /api/transcrever.
        #   Instalar um segundo Whisper aqui seria dobrar o download, dobrar a
        #   memoria e criar duas verdades sobre qualidade de audio -- pelo
        #   mesmo motivo que o venure.css e o usuarios.json sao compartilhados.
        #
        #   Entao a Pipi ENCAMINHA o audio para o Bigode. Servidor falando com
        #   servidor: sem CORS, sem chave, sem o navegador no meio.
        #
        #   Se o Bigode nao estiver de pe, isto responde ok:false e a tela cai
        #   sozinha no ditado do proprio Chrome. Voz nunca fica indisponivel.
        if path == '/api/transcrever':
            if self._barrado(path):
                return
            try:
                tam = int(self.headers.get('Content-Length', '0')) or 0
                audio = self.rfile.read(tam)
            except Exception:
                return send_json(self, 400, {'ok': False, 'erro': 'áudio inválido'})
            return send_json(self, 200, _transcrever_no_bigode(audio))

        # A PONTE COM O BIGODE                                 (17/09)
        #
        #   O Bigode pede aqui quando voce diz "desenhe alguma coisa" na
        #   tela dele. Ele espera a imagem ficar pronta e mostra no lugar.
        #
        #   NAO passa pelo login da Pipi: quem chama e um programa, nao uma
        #   pessoa, e nao teria como ter sessao. No lugar do login vao duas
        #   provas -- vir de 127.0.0.1 E trazer o segredo do ponte.txt.
        #   A segunda existe por causa do seu proprio navegador: uma aba
        #   qualquer consegue mandar POST para 127.0.0.1, mas nao consegue
        #   ler arquivo do seu disco.
        #
        #   E DESENHA DE VERDADE, na mesma fila e na mesma pasta que a tela
        #   usa. Um segundo caminho de desenho seria duas verdades sobre
        #   como a Pipi gera imagem -- e foi isso que custou o dia de
        #   ontem do lado do motor de texto.
        if path == '/api/ponte/imagem':
            try:
                tam = int(self.headers.get('Content-Length', '0')) or 0
                corpo_p = json.loads(self.rfile.read(tam) or b'{}')
            except Exception:
                return send_json(self, 400, {'ok': False, 'erro': 'JSON inválido'})

            ok, motivo = ponte.confere(self)
            if not ok:
                return send_json(self, 403, {'ok': False,
                                             'erro': 'ponte recusada: %s' % motivo})

            prompt = str(corpo_p.get('descricao') or corpo_p.get('prompt') or '').strip()
            if not prompt:
                return send_json(self, 400, {'ok': False,
                                             'erro': 'informe a descrição'})
            if not modal_cliente.configurado():
                return send_json(self, 200, {
                    'ok': False,
                    'erro': 'a Pipi está aberta, mas sem motor. '
                            'Rode: python usar_modal.py'})

            jid = job(prompt, corpo_p)
            # Espera aqui, sincrono, ate 10 minutos. Quem chamou foi o
            # Bigode no meio de uma resposta: devolver "job_id, pergunte
            # depois" faria ele ter de inventar um laco de espera proprio.
            limite = time.time() + 600
            while time.time() < limite:
                time.sleep(1.5)
                with LOCK:
                    item = dict(JOBS.get(jid) or {})
                if item.get('estado') == 'concluido':
                    return send_json(self, 200, {
                        'ok': True,
                        'arquivo': item.get('arquivo'),
                        'nome': item.get('nome'),
                        'url': 'http://127.0.0.1:%s%s' % (
                            os.environ.get('PIPI_PORT', '7300'),
                            item.get('resultado') or ''),
                        'segundos': item.get('segundos'),
                        'custo_usd': item.get('custo_usd'),
                        'licenca': item.get('licenca'),
                        'modelo': MODELO,
                    })
                if item.get('estado') == 'erro':
                    return send_json(self, 200, {'ok': False,
                                                 'erro': item.get('erro')})
            return send_json(self, 200, {'ok': False,
                                         'erro': 'a imagem não ficou pronta em 10 min'})

        if path not in ('/api/entrar', '/api/sair', '/api/imagens/job',
                        '/api/apagar', '/api/prompt'):
            return send_json(self, 404, {'ok': False, 'erro': 'rota não encontrada'})

        try:
            tam = int(self.headers.get('Content-Length', '0')) or 0
            corpo = json.loads(self.rfile.read(tam) or b'{}')
        except Exception:
            return send_json(self, 400, {'ok': False, 'erro': 'JSON inválido'})

        if path == '/api/entrar':
            ok, r = login_venure.entrar(str(corpo.get('email', '')),
                                        str(corpo.get('senha', '')))
            if ok:
                return send_json_cookie(self, 200, {'ok': True}, r)
            return send_json(self, 401, {'ok': False, 'erro': r})

        if path == '/api/sair':
            return send_json_cookie(self, 200, {'ok': True},
                                    login_venure.sair(self))

        if self._barrado(path):
            return

        # O BIGODE ESCREVENDO O PROMPT                          (17/09)
        #
        #   Devolve o prompt em ingles e NAO desenha nada. Desenhar aqui
        #   seria tirar de voce a chance de ler e corrigir antes de gastar
        #   placa -- e e lendo o que foi enviado que voce aprende a
        #   escrever direto, sem intermediario.
        if path == '/api/prompt':
            ideia = str(corpo.get('ideia') or corpo.get('prompt') or '').strip()
            try:
                texto, modelo = escritor.escrever(
                    ideia, formato=str(corpo.get('formato') or ''))
            except Exception as exc:
                return send_json(self, 200, {'ok': False,
                                             'erro': str(exc)[:300]})
            return send_json(self, 200, {'ok': True, 'prompt': texto,
                                         'modelo': modelo})

        if path == '/api/apagar':
            # SO DENTRO DE producao\, E SO O NOME DO ARQUIVO      (17/09)
            #
            #   Apagar por nome vindo do navegador e um caminho classico
            #   para estrago: "../../cerebro.py" apagaria outra coisa. Por
            #   isso o nome passa pelo Path().name (que descarta qualquer
            #   pasta) e o resultado e conferido contra a pasta producao
            #   DEPOIS de resolvido. As duas checagens, nao uma.
            nome = Path(str(corpo.get('nome') or '')).name
            if not nome:
                return send_json(self, 400, {'ok': False, 'erro': 'sem nome'})
            alvo = (OUT / nome).resolve()
            if not str(alvo).startswith(str(OUT.resolve())):
                return send_json(self, 400, {'ok': False,
                                             'erro': 'fora da pasta producao'})
            if not alvo.is_file():
                return send_json(self, 404, {'ok': False,
                                             'erro': 'esse arquivo não existe mais'})
            try:
                alvo.unlink()
            except Exception as exc:
                return send_json(self, 500, {'ok': False,
                                             'erro': 'não consegui apagar: %s'
                                                     % str(exc)[:160]})
            return send_json(self, 200, {'ok': True, 'apagado': nome})

        prompt = str(corpo.get('prompt') or corpo.get('descricao') or '').strip()
        if not prompt:
            return send_json(self, 400, {'ok': False, 'erro': 'Informe uma descrição'})
        return send_json(self, 202, {'ok': True, 'job_id': job(prompt, corpo),
                                     'estado': 'fila'})


if __name__ == '__main__':
    porta = int(os.environ.get('PIPI_PORT', '7300'))

    # SO A SUA MAQUINA, POR PADRAO                              (17/09)
    #
    #   Isto estava em '0.0.0.0' -- ou seja, qualquer aparelho na mesma
    #   rede alcancava a Pipi. E o comentario do proprio arquivo dizia,
    #   errado, que ela "escuta so em 127.0.0.1". Codigo e comentario
    #   discordando e pior do que codigo sem comentario.
    #
    #   Agora o padrao e so esta maquina. Para abrir no celular na mesma
    #   rede, de proposito:  set PIPI_ABRIR_REDE=1
    endereco = '0.0.0.0' if os.environ.get('PIPI_ABRIR_REDE') else '127.0.0.1'

    # A PONTE NASCE AQUI, E NAO NO PRIMEIRO PEDIDO             (18/09)
    #
    #   O ponte.txt so era criado dentro do `ponte.confere()`, que so roda
    #   QUANDO UM PEDIDO CHEGA. Do outro lado, o Bigode le o arquivo ANTES
    #   de pedir, e sem ele nem tenta -- devolve:
    #
    #       "A Pipi existe, mas o ponte.txt ainda nao foi criado.
    #        Abra a Pipi uma vez (pipi.bat) -- ela cria o arquivo sozinha."
    #
    #   Impasse fechado: o arquivo so nasce com um pedido, e o pedido so
    #   sai com o arquivo. A ponte nunca funcionaria na primeira vez.
    #
    #   Pior: aquela frase e minha, de ontem, e prometia um comportamento
    #   que eu nao tinha conferido -- abrir a Pipi NAO criava nada. E a
    #   segunda vez em dois dias que escrevo uma afirmacao dessas (a outra
    #   dizia que a tela do Bigode ja virava imagem sozinha). Afirmacao em
    #   comentario e em mensagem de erro tem o mesmo peso de codigo: quem
    #   le acredita e para de procurar.
    #
    #   Uma linha resolve, e faz a frase virar verdade.
    _ponte = ponte.segredo()
    if not _ponte:
        print('AVISO: nao consegui criar o ponte.txt. O Bigode nao vai '
              'conseguir pedir imagem para a Pipi.')

    print('Pipi IA · Modal · L40S · FLUX.1-schnell')
    print('Abra:  http://127.0.0.1:%d' % porta)
    if endereco == '0.0.0.0':
        print('Aberta para a rede local (PIPI_ABRIR_REDE=1).')
    if not modal_cliente.configurado():
        print('AVISO: a Modal nao esta configurada. Rode: python usar_modal.py')
    if _ponte:
        print('Ponte com o Bigode: pronta.')
    print('Ctrl+C encerra.')

    servidor = ThreadingHTTPServer((endereco, porta), Handler)

    # CTRL+C NAO E ERRO, ENTAO NAO PODE PARECER UM              (17/09)
    #
    #   Sem este try, apertar Ctrl+C imprimia oito linhas de traceback
    #   terminando dentro do selectors.py do Python:
    #
    #       Traceback (most recent call last):
    #         File "pipi_server.py", line 635, in <module>
    #         File "socketserver.py", line 235, in serve_forever
    #         File "selectors.py", line 305, in _select
    #           r, w, x = select.select(r, w, w, timeout)
    #
    #   Nada quebrou: e o KeyboardInterrupt chegando no meio da espera por
    #   conexao, que e exatamente onde o servidor passa 100% do tempo. Mas
    #   quem le aquilo aprende a ignorar traceback -- e no dia em que
    #   aparecer um de verdade, vai ignorar tambem.
    #
    #   O `shutdown` em thread separada e obrigatorio: chamado daqui, ele
    #   esperaria o proprio serve_forever terminar e travaria.
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('\nEncerrando...')
        threading.Thread(target=servidor.shutdown, daemon=True).start()
    finally:
        servidor.server_close()
        print('Pipi encerrada. As imagens estao em %s' % OUT)
