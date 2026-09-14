#!/usr/bin/env python3
"""Servidor independente da Pipi IA.

Backends suportados: ComfyUI local/remoto e Hugging Face Inference Providers.
Os pesos locais são apenas catalogados; a execução usa o motor escolhido.
"""
from __future__ import annotations
import json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
# O HUGGING FACE E OPCIONAL -- E PRECISA SE COMPORTAR COMO TAL  (13/09)
#
#     Este import era direto, e derrubava a Pipi inteira quando o modulo
#     nao estava alcancavel:
#
#         ModuleNotFoundError: No module named 'huggingface_cliente'
#
#     O arquivo ate existe na pasta. O que faltou foi o Python usado
#     enxergar a pasta: o pipi.bat pode acabar escolhendo o Python
#     embarcado do pendrive, que tem um python312._pth e por isso monta
#     o sys.path de um jeito mais fechado.
#
#     Mas a causa exata importa menos do que o efeito: o Hugging Face so
#     e usado por quem configurou HF_TOKEN. Um acessorio que ninguem
#     ligou nao pode impedir a ferramenta de abrir. Se ele nao vier, a
#     Pipi segue com o ComfyUI, que e o motor principal.
try:
    import huggingface_cliente
except Exception as _erro_hf:
    class _HuggingFaceAusente:
        _porque = str(_erro_hf)
        @staticmethod
        def configurado(): return False
        @classmethod
        def status(cls):
            return {'configurado': False, 'online': False,
                    'erro': 'huggingface_cliente indisponivel: ' + cls._porque}
        @classmethod
        def chat(cls, *a, **k):
            raise RuntimeError('Hugging Face indisponivel: ' + cls._porque)
        @classmethod
        def text_to_image(cls, *a, **k):
            raise RuntimeError('Hugging Face indisponivel: ' + cls._porque)
    huggingface_cliente = _HuggingFaceAusente()

# A Modal, pelo mesmo motivo: opcional, e falhar em carregar nao pode
# derrubar a Pipi inteira.
try:
    import modal_cliente
except Exception as _erro_modal:
    class _ModalAusente:
        _porque = str(_erro_modal)
        @staticmethod
        def configurado(): return False
        @classmethod
        def status(cls):
            return {'configurado': False, 'online': False,
                    'erro': 'modal_cliente indisponivel: ' + cls._porque}
        @classmethod
        def gerar(cls, *a, **k):
            raise RuntimeError('Modal indisponivel: ' + cls._porque)
    modal_cliente = _ModalAusente()
ROOT=Path(__file__).resolve().parent; WEB=ROOT/'web'; OUT=ROOT/'producao'; OUT.mkdir(exist_ok=True)

# MOTOR REMOTO GRAVADO EM ARQUIVO   (13/09)
#
#     A variavel de ambiente some quando o Prompt de Comando fecha, e o
#     endereco do Colab muda a cada sessao -- entao exigir que o Fred
#     reescreva `set PIPI_COMFYUI_URL=...` toda vez e pedir para ele errar.
#     O usar_desenhista_do_colab.py grava o endereco em motor_remoto.txt e
#     este arquivo passa a ser lido na partida.
#
#     A variavel de ambiente continua ganhando quando existe: quem a define
#     de proposito esta mandando, e uma sobrescrita silenciosa seria pior.
def _motor_gravado():
    arq = ROOT/'motor_remoto.txt'
    try:
        return arq.read_text(encoding='utf-8').strip() if arq.is_file() else ''
    except Exception:
        return ''
COMFY=(os.environ.get('PIPI_COMFYUI_URL','') or _motor_gravado()).rstrip('/')
MODELS_DIR=Path(os.environ.get('PIPI_MODELS_DIR',r'G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem'))
JOBS={}; LOCK=threading.RLock()
def catalog():
    data=json.loads((ROOT/'motores.json').read_text(encoding='utf-8'))
    for item in data:
        nome=item.get('arquivo',''); path=MODELS_DIR/nome
        if not path.exists() and MODELS_DIR.exists():
            hits=list(MODELS_DIR.rglob(nome)); path=hits[0] if hits else path
        item['baixado']=path.exists(); item['tamanho_local']=path.stat().st_size if path.exists() else 0
        item['caminho_local']=str(path)
    return data
# TIPO CERTO PARA CADA ARQUIVO                                  (13/09)
#
#     Tudo era servido como 'application/octet-stream'. Para imagem o
#     navegador ate adivinha pelo conteudo e mostra assim mesmo -- mas
#     FOLHA DE ESTILO ele recusa: em modo padrao, um .css que chega com
#     octet-stream e ignorado em silencio, sem erro na tela.
#
#     Ou seja: qualquer estilo externo que a Pipi tentasse carregar
#     simplesmente nao ia valer, e a pagina apareceria crua sem nada
#     explicar o motivo. Este dicionario e o conserto.
TIPOS = {
    '.html': 'text/html; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg':  'image/svg+xml',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',  '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',  '.gif':  'image/gif',
    '.ico':  'image/x-icon',
    '.woff2':'font/woff2',  '.woff': 'font/woff',
    '.txt':  'text/plain; charset=utf-8',
}

# Onde fica o web\ do Cerebro, para reaproveitar o venure.css.
CEREBRO_WEB=None
for _c in (os.environ.get('BIGODE_CEREBRO','').strip(),
           str(ROOT.parent/'Cerebro'),
           str(Path.home()/'Downloads'/'Cerebro')):
    if _c and (Path(_c)/'web').is_dir():
        CEREBRO_WEB=Path(_c)/'web'; break

def enviar_arquivo(h,caminho):
    dados=caminho.read_bytes()
    h.send_response(200)
    h.send_header('Content-Type',TIPOS.get(caminho.suffix.lower(),'application/octet-stream'))
    h.send_header('Content-Length',str(len(dados)))
    h.end_headers(); h.wfile.write(dados)

def send_json(h,status,data):
    raw=json.dumps(data,ensure_ascii=False).encode(); h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Content-Length',str(len(raw))); h.end_headers(); h.wfile.write(raw)
def comfy_status():
    if not COMFY: return {'configurado':False,'online':False,'url':''}
    try:
        status,_=http_json(COMFY+'/system_stats',timeout=5)
        return {'configurado':True,'online':200 <= status < 300,'url':COMFY,'http':status}
    except Exception as exc:
        return {'configurado':True,'online':False,'url':COMFY,'erro':str(exc)[:240]}
def http_json(url, payload=None, method='GET', timeout=30):
    body=None if payload is None else json.dumps(payload).encode(); headers={'Content-Type':'application/json'}
    with urlopen(Request(url,data=body,headers=headers,method=method),timeout=timeout) as r: return r.status, r.read()
def _replace_prompt(obj, prompt, negative=''):
    if isinstance(obj, dict):
        # Workflow API: identifica CLIPTextEncode pelo título para não trocar
        # o texto negativo pelo prompt positivo.
        if obj.get('class_type') == 'CLIPTextEncode':
            inputs = obj.setdefault('inputs', {})
            title = str((obj.get('_meta') or {}).get('title', '')).lower()
            inputs['text'] = negative if 'negative' in title else prompt
            return
        for k,v in list(obj.items()):
            if isinstance(v,str) and k.lower() in {'prompt','positive','positive_prompt'}: obj[k]=prompt
            elif isinstance(v,str) and negative and k.lower() in {'negative','negative_prompt'}: obj[k]=negative
            else: _replace_prompt(v,prompt,negative)
    elif isinstance(obj,list):
        for v in obj: _replace_prompt(v,prompt,negative)
def _comfy_job(jid,prompt,payload):
    wf=ROOT/'workflow.json'
    if not wf.exists(): raise RuntimeError('ComfyUI conectado, mas workflow.json não existe.')
    graph=json.loads(wf.read_text(encoding='utf-8')); _replace_prompt(graph,prompt,str(payload.get('negativo') or ''))
    status,raw=http_json(COMFY+'/prompt',{'prompt':graph,'client_id':'pipi-'+jid},'POST',30); data=json.loads(raw); pid=data.get('prompt_id')
    if not pid: raise RuntimeError('ComfyUI não retornou prompt_id.')
    for _ in range(300):
        time.sleep(1); _,raw=http_json(COMFY+'/history/'+pid); hist=json.loads(raw).get(pid)
        if not hist: continue
        outputs=hist.get('outputs') or {}; images=[]
        for node in outputs.values(): images.extend(node.get('images') or [])
        if images:
            img=images[0]; query=urlencode({k:img.get(k,'') for k in ('filename','subfolder','type')}); _,blob=http_json(COMFY+'/view?'+query)
            dest=OUT/(img.get('filename') or (jid+'.png')); dest.write_bytes(blob)
            return str(dest)
        if hist.get('status',{}).get('status_str')=='error': raise RuntimeError('ComfyUI informou erro no workflow.')
    raise RuntimeError('Tempo limite aguardando o ComfyUI.')
def _hf_job(jid,prompt,payload):
    image=huggingface_cliente.text_to_image(prompt, model=payload.get('hf_model') or os.environ.get('HF_IMAGE_MODEL'), negative_prompt=payload.get('negativo'), width=payload.get('width'), height=payload.get('height'), steps=payload.get('passos'), guidance=payload.get('guidance'), seed=payload.get('semente') or None)
    dest=OUT/(jid+'.png'); image.save(dest); return str(dest)
def _modal_job(jid,prompt,payload):
    destino=OUT/(jid+'.png')
    caminho,_seg,_lic=modal_cliente.gerar(
        prompt, formato=payload.get('formato') or 'quadrado',
        passos=payload.get('passos') or 4,
        semente=payload.get('semente') or 0, destino=destino)
    return caminho

def run(jid,prompt,payload):
    with LOCK: JOBS[jid]['estado']='preparando'
    try:
        backend=str(payload.get('backend') or '').lower()

        # A ORDEM DE ESCOLHA, E POR QUE ELA E ESTA           (13/09)
        #
        #   A Modal vem PRIMEIRO quando esta configurada. Ela e a unica
        #   das tres que hoje gera imagem de verdade nesta maquina: o
        #   ComfyUI local existe mas roda em CPU e sem as pecas do
        #   modelo, e o Hugging Face so serve a quem pos um HF_TOKEN.
        #
        #   Quem configurou a Modal fez isso de proposito e pagou por
        #   ela. Deixar o ComfyUI local na frente faria a Pipi preferir
        #   o motor que nao funciona.
        if backend=='modal' or (not backend and modal_cliente.configurado()):
            resultado=_modal_job(jid,prompt,payload)
        elif backend=='huggingface' or (not COMFY and huggingface_cliente.configurado()):
            resultado=_hf_job(jid,prompt,payload)
        elif COMFY:
            resultado=_comfy_job(jid,prompt,payload)
        else:
            raise RuntimeError('Nenhum motor conectado. Configure a Modal '
                '(python usar_modal.py), aponte o ComfyUI do Colab '
                '(python usar_desenhista_do_colab.py), ou defina HF_TOKEN.')
        # O QUE VAI PARA A TELA E UM ENDERECO, NAO UM CAMINHO   (13/09)
        #
        #   Aqui ia o caminho no disco: "G:\\Meu Drive\\...\\pipi_x.png".
        #   A tela procura nele algo parecido com URL para montar o
        #   <img>. Caminho do Windows nunca casa com isso -- e mesmo que
        #   casasse, o navegador nao abre arquivo local por conta propria.
        #
        #   Efeito: a imagem era criada certinho na pasta e a tela
        #   mostrava so texto. Parecia que nao tinha funcionado.
        #
        #   Agora vai "/producao/pipi_x.png", que a rota nova serve. O
        #   caminho de disco continua disponivel em `arquivo`, para quem
        #   quiser abrir na pasta.
        try:
            nome=Path(resultado).name
            endereco='/producao/'+nome
        except Exception:
            nome=''; endereco=str(resultado)
        with LOCK: JOBS[jid].update(estado='concluido',resultado=endereco,
                                    arquivo=str(resultado),nome=nome)
    except Exception as exc:
        with LOCK: JOBS[jid].update(estado='erro',erro=str(exc))
def job(prompt,payload):
    jid='pipi_'+uuid.uuid4().hex[:12]
    with LOCK: JOBS[jid]={'id':jid,'estado':'fila','criado_em':time.time(),'prompt':prompt,'resultado':None,'erro':''}
    threading.Thread(target=run,args=(jid,prompt,payload),daemon=True).start(); return jid
# O LOGIN E OPCIONAL, COMO O HUGGING FACE                       (13/09)
#
#   Se o login_venure.py nao carregar, a Pipi abre sem login em vez de
#   trancar. Aqui nao ha dado de terceiro e ela escuta so em 127.0.0.1 --
#   ficar trancado fora da propria ferramenta por causa de um import
#   seria um estrago maior do que o risco que a tranca evita.
try:
    import login_venure
except Exception as _e_login:
    class _SemLogin:
        @staticmethod
        def ligado(): return False
        @staticmethod
        def autorizado(h): return True
        @staticmethod
        def motivo(): return 'login_venure indisponivel: %s' % _e_login
        @staticmethod
        def sessao(h): return None
    login_venure=_SemLogin()

def send_json_cookie(h,status,data,cookie):
    raw=json.dumps(data,ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header('Content-Type','application/json; charset=utf-8')
    if cookie: h.send_header('Set-Cookie',cookie)
    h.send_header('Content-Length',str(len(raw)))
    h.end_headers(); h.wfile.write(raw)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass

    # Rotas que respondem SEM login. A tela e o /api/eu precisam sair
    # antes de existir sessao, senao a pagina de entrar aparece crua.
    LIVRES=('/','/index.html','/api/eu','/api/entrar','/api/sair',
            '/venure.css','/manifest.json','/img/','/favicon')

    def _livre(self,path):
        return any(path==r or path.startswith(r) for r in self.LIVRES)

    def _barrado(self,path):
        if self._livre(path): return False
        if login_venure.autorizado(self): return False
        send_json(self,401,{'ok':False,'erro':'Faça login para usar a Pipi.'})
        return True

    def do_GET(self):
        path=urlparse(self.path).path

        if path=='/api/eu':
            s=login_venure.sessao(self)
            return send_json(self,200,{'ok':True,'exige':login_venure.ligado(),
                'logado':bool(s),'nome':(s or {}).get('nome',''),
                'motivo':login_venure.motivo()})

        if self._barrado(path): return

        if path=='/api/health':
            comfy=comfy_status()
            return send_json(self,200,{'ok':True,'servico':'pipi','estado':'pronto' if comfy.get('online') or huggingface_cliente.configurado() else 'sem_motor','comfyui':comfy,'huggingface':huggingface_cliente.status(),'motores':len(catalog()),'pasta_motores':str(MODELS_DIR),'pasta_existe':MODELS_DIR.exists()})
        if path=='/api/huggingface': return send_json(self,200,{'ok':True,**huggingface_cliente.status()})
        if path=='/api/logs':
            with LOCK: jobs=list(JOBS.values())[-40:]
            return send_json(self,200,{'ok':True,'arquivos':[],'jobs':jobs,'comfyui':bool(COMFY),'huggingface':huggingface_cliente.status()})
        if path=='/api/imagens':
            ms=catalog()
            # A tela le `componentes` para dizer o que falta. Este campo
            # nunca existiu na resposta, entao ela mostrava "T5 nao
            # detectado" para sempre -- inclusive com tudo instalado.
            baixados=[m for m in ms if m.get('baixado')]
            faltando=[m.get('arquivo','') for m in ms if not m.get('baixado')]
            componentes={'unet':(baixados[0].get('nome') if baixados else ''),
                         't5':('detectado' if baixados else 'não detectado'),
                         'faltando':faltando}
            return send_json(self,200,{'ok':True,'motores':ms,'modelos':ms,
                'componentes':componentes,
                'comfyui':bool(COMFY),'huggingface':huggingface_cliente.status(),
                'modal':modal_cliente.status(),
                'pasta_motores':str(MODELS_DIR),'pasta_existe':MODELS_DIR.exists(),
                'producao':str(OUT)})
        if path.startswith('/api/imagens/job/'):
            jid=path.rsplit('/',1)[-1]; item=JOBS.get(jid); return send_json(self,200 if item else 404,item or {'ok':False,'erro':'job não encontrado'})
        if path=='/' or path=='/index.html':
            data=(WEB/'index.html').read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        # As imagens que a Pipi produziu. Sem esta rota o <img> do
        # resultado aponta para um caminho de disco que o navegador nao
        # tem como abrir -- a imagem saia certinha na pasta e a tela
        # mostrava um quadrado quebrado.
        if path.startswith('/producao/'):
            alvo=(OUT/path[len('/producao/'):]).resolve()
            if str(alvo).startswith(str(OUT.resolve())) and alvo.is_file():
                return enviar_arquivo(self,alvo)
            return send_json(self,404,{'ok':False,'erro':'imagem não encontrada'})

        # O manifesto mora na RAIZ, nao em web\. Sem isto o <head> pedia
        # /manifest.json e levava 404 em toda visita.
        if path=='/manifest.json' and (ROOT/'manifest.json').is_file():
            return enviar_arquivo(self,ROOT/'manifest.json')

        # A folha de estilo que a Pipi divide com o Bigode. Procura aqui
        # primeiro; se nao houver, pega a do Cerebro -- assim existe UM
        # arquivo so, e um conserto de estilo vale para os dois.
        if path=='/venure.css':
            for c in (WEB/'venure.css', CEREBRO_WEB/'venure.css' if CEREBRO_WEB else None):
                if c and c.is_file():
                    return enviar_arquivo(self,c)
            return send_json(self,404,{'ok':False,'erro':'venure.css não encontrado'})

        rel=path.lstrip('/'); target=(WEB/rel).resolve()
        if str(target).startswith(str(WEB.resolve())) and target.is_file():
            return enviar_arquivo(self,target)
        send_json(self,404,{'ok':False,'erro':'rota não encontrada'})
    def do_POST(self):
        path=urlparse(self.path).path

        if path in ('/api/entrar','/api/sair','/api/imagens/job'):
            try:
                bruto=self.rfile.read(int(self.headers.get('Content-Length','0')) or 0)
                corpo=json.loads(bruto or b'{}')
            except Exception:
                return send_json(self,400,{'ok':False,'erro':'JSON inválido'})
        else:
            return send_json(self,404,{'ok':False,'erro':'rota não encontrada'})

        if path=='/api/entrar':
            ok,r=login_venure.entrar(str(corpo.get('email','')),
                                     str(corpo.get('senha','')))
            if ok: return send_json_cookie(self,200,{'ok':True},r)
            return send_json(self,401,{'ok':False,'erro':r})

        if path=='/api/sair':
            return send_json_cookie(self,200,{'ok':True},login_venure.sair(self))

        if self._barrado(path): return
        data=corpo
        prompt=str(data.get('prompt') or data.get('descricao') or '').strip()
        if not prompt: return send_json(self,400,{'ok':False,'erro':'Informe um prompt'})
        return send_json(self,202,{'ok':True,'job_id':job(prompt,data),'estado':'fila'})
if __name__=='__main__':
    port=int(os.environ.get('PIPI_PORT','7300')); print(f'Pipi IA independente em http://127.0.0.1:{port}'); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
