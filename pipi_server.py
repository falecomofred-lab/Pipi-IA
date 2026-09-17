#!/usr/bin/env python3
"""Servidor Pipi IA refatorado — código 100% PPIA, melhor estruturado.

Mantém toda a lógica original, apenas reorganizada em funções claras.
Motor principal: Modal. Fallback: ComfyUI.
"""
from __future__ import annotations
import json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen

# ============ INICIALIZAÇÃO ============

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
OUT = ROOT / 'producao'
OUT.mkdir(exist_ok=True)

JOBS = {}
LOCK = threading.RLock()

# ============ IMPORTAÇÃO DE BACKENDS OPCIONAIS ============

try:
    import modal_cliente
except Exception as _erro_modal:
    class _ModalAusente:
        @staticmethod
        def configurado():
            return False
        @staticmethod
        def status():
            return {'configurado': False, 'online': False}
        @staticmethod
        def gerar(*a, **k):
            raise RuntimeError('Modal indisponivel')
    modal_cliente = _ModalAusente()

try:
    import huggingface_cliente
except Exception as _erro_hf:
    class _HuggingFaceAusente:
        @staticmethod
        def configurado():
            return False
        @staticmethod
        def status():
            return {'configurado': False, 'online': False}
        @staticmethod
        def text_to_image(*a, **k):
            raise RuntimeError('Hugging Face indisponivel')
    huggingface_cliente = _HuggingFaceAusente()

try:
    import login_venure
except Exception:
    class _SemLogin:
        @staticmethod
        def ligado():
            return False
        @staticmethod
        def autorizado(h):
            return True
        @staticmethod
        def sessao(h):
            return None
    login_venure = _SemLogin()

# ============ CONFIGURAÇÃO ============

def _motor_gravado() -> str:
    """Lê URL de ComfyUI remoto do arquivo motor_remoto.txt."""
    arq = ROOT / 'motor_remoto.txt'
    try:
        return arq.read_text(encoding='utf-8').strip() if arq.is_file() else ''
    except:
        return ''

COMFY = (os.environ.get('PIPI_COMFYUI_URL', '') or _motor_gravado()).rstrip('/')
MODELS_DIR = Path(os.environ.get(
    'PIPI_MODELS_DIR',
    r'G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem'
))

TIPOS = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
    '.txt': 'text/plain; charset=utf-8',
}

# ============ UTILITÁRIOS DE REDE ============

def http_json(url: str, payload=None, method='GET', timeout=30):
    """Faz requisição HTTP JSON."""
    body = None if payload is None else json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json'}
    with urlopen(Request(url, data=body, headers=headers, method=method), timeout=timeout) as r:
        return r.status, r.read()

def send_json(handler, status: int, data: dict):
    """Envia resposta JSON."""
    raw = json.dumps(data, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)

def enviar_arquivo(handler, caminho: Path):
    """Envia arquivo com MIME type correto."""
    dados = caminho.read_bytes()
    handler.send_response(200)
    handler.send_header('Content-Type', TIPOS.get(caminho.suffix.lower(), 'application/octet-stream'))
    handler.send_header('Content-Length', str(len(dados)))
    handler.end_headers()
    handler.wfile.write(dados)

# ============ STATUS DE MOTORES ============

def comfy_status() -> dict:
    """Verifica status do ComfyUI."""
    if not COMFY:
        return {'configurado': False, 'online': False, 'url': ''}
    try:
        status, _ = http_json(COMFY + '/system_stats', timeout=5)
        return {
            'configurado': True,
            'online': 200 <= status < 300,
            'url': COMFY,
            'http': status
        }
    except Exception as exc:
        return {
            'configurado': True,
            'online': False,
            'url': COMFY,
            'erro': str(exc)[:240]
        }

def health() -> dict:
    """Retorna saúde de todos os motores."""
    modal_st = modal_cliente.status()
    comfy_st = comfy_status()
    hf_st = huggingface_cliente.status()

    pronto = modal_st.get('online') or comfy_st.get('online') or hf_st.get('online')

    return {
        'ok': True,
        'servico': 'pipi-ia',
        'estado': 'pronto' if pronto else 'sem_motor',
        'modal': modal_st,
        'comfyui': comfy_st,
        'huggingface': hf_st,
    }

# ============ GERAÇÃO DE IMAGEM ============

def _replace_prompt(obj, prompt: str, negative: str = ''):
    """Substitui prompts no workflow do ComfyUI."""
    if isinstance(obj, dict):
        if obj.get('class_type') == 'CLIPTextEncode':
            inputs = obj.setdefault('inputs', {})
            title = str((obj.get('_meta') or {}).get('title', '')).lower()
            inputs['text'] = negative if 'negative' in title else prompt
            return
        for k, v in list(obj.items()):
            if isinstance(v, str) and k.lower() in {'prompt', 'positive', 'positive_prompt'}:
                obj[k] = prompt
            elif isinstance(v, str) and negative and k.lower() in {'negative', 'negative_prompt'}:
                obj[k] = negative
            else:
                _replace_prompt(v, prompt, negative)
    elif isinstance(obj, list):
        for v in obj:
            _replace_prompt(v, prompt, negative)

def _comfy_job(jid: str, prompt: str, payload: dict) -> str:
    """Gera imagem via ComfyUI."""
    wf = ROOT / 'workflow.json'
    if not wf.exists():
        raise RuntimeError('ComfyUI conectado, mas workflow.json não existe.')

    graph = json.loads(wf.read_text(encoding='utf-8'))
    _replace_prompt(graph, prompt, str(payload.get('negativo') or ''))

    status, raw = http_json(COMFY + '/prompt', {'prompt': graph, 'client_id': 'pipi-' + jid}, 'POST', 30)
    data = json.loads(raw)
    pid = data.get('prompt_id')

    if not pid:
        raise RuntimeError('ComfyUI não retornou prompt_id.')

    for _ in range(300):
        time.sleep(1)
        _, raw = http_json(COMFY + '/history/' + pid)
        hist = json.loads(raw).get(pid)

        if not hist:
            continue

        outputs = hist.get('outputs') or {}
        images = []
        for node in outputs.values():
            images.extend(node.get('images') or [])

        if images:
            img = images[0]
            query = urlencode({k: img.get(k, '') for k in ('filename', 'subfolder', 'type')})
            _, blob = http_json(COMFY + '/view?' + query)
            dest = OUT / (img.get('filename') or (jid + '.png'))
            dest.write_bytes(blob)
            return str(dest)

        if hist.get('status', {}).get('status_str') == 'error':
            raise RuntimeError('ComfyUI informou erro no workflow.')

    raise RuntimeError('Timeout aguardando ComfyUI (300s).')

def _hf_job(jid: str, prompt: str, payload: dict) -> str:
    """Gera imagem via Hugging Face."""
    image = huggingface_cliente.text_to_image(
        prompt,
        model=payload.get('hf_model') or os.environ.get('HF_IMAGE_MODEL'),
        negative_prompt=payload.get('negativo'),
        width=payload.get('width'),
        height=payload.get('height'),
        steps=payload.get('passos'),
        guidance=payload.get('guidance'),
        seed=payload.get('semente') or None
    )
    dest = OUT / (jid + '.png')
    image.save(dest)
    return str(dest)

def _modal_job(jid: str, prompt: str, payload: dict) -> str:
    """Gera imagem via Modal."""
    destino = OUT / (jid + '.png')
    caminho, _seg, _lic = modal_cliente.gerar(
        prompt,
        formato=payload.get('formato') or 'quadrado',
        passos=payload.get('passos') or 4,
        semente=payload.get('semente') or 0,
        destino=destino
    )
    return caminho

def run_job(jid: str, prompt: str, payload: dict):
    """Processa um job de geração."""
    with LOCK:
        JOBS[jid]['estado'] = 'preparando'

    try:
        backend = str(payload.get('backend') or '').lower()

        # Ordem de preferência: Modal > ComfyUI > HuggingFace
        if backend == 'modal' or (not backend and modal_cliente.configurado()):
            resultado = _modal_job(jid, prompt, payload)
        elif backend == 'huggingface' or (not COMFY and huggingface_cliente.configurado()):
            resultado = _hf_job(jid, prompt, payload)
        elif COMFY:
            resultado = _comfy_job(jid, prompt, payload)
        else:
            raise RuntimeError('Nenhum motor conectado. Configure Modal, ComfyUI ou HuggingFace.')

        nome = Path(resultado).name if resultado else ''
        endereco = '/producao/' + nome if nome else str(resultado)

        with LOCK:
            JOBS[jid].update(
                estado='concluido',
                resultado=endereco,
                arquivo=str(resultado),
                nome=nome
            )
    except Exception as exc:
        with LOCK:
            JOBS[jid].update(estado='erro', erro=str(exc))

def create_job(prompt: str, payload: dict) -> str:
    """Cria novo job de geração."""
    jid = 'pipi-ia_' + uuid.uuid4().hex[:12]
    with LOCK:
        JOBS[jid] = {
            'id': jid,
            'estado': 'fila',
            'criado_em': time.time(),
            'prompt': prompt,
            'resultado': None,
            'erro': ''
        }
    threading.Thread(target=run_job, args=(jid, prompt, payload), daemon=True).start()
    return jid

# ============ HTTP HANDLER ============

class Handler(BaseHTTPRequestHandler):
    """Handler HTTP."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        """GET: informações e arquivos."""
        path = urlparse(self.path).path

        if path == '/api/health':
            return send_json(self, 200, health())

        if path == '/api/logs':
            with LOCK:
                jobs = list(JOBS.values())[-40:]
            return send_json(self, 200, {
                'ok': True,
                'arquivos': [],
                'jobs': jobs,
                'comfyui': bool(COMFY),
                'huggingface': huggingface_cliente.status(),
                'modal': modal_cliente.status()
            })

        if path.startswith('/api/imagens/job/'):
            jid = path.rsplit('/', 1)[-1]
            with LOCK:
                item = JOBS.get(jid)
            return send_json(self, 200 if item else 404, item or {'ok': False, 'erro': 'job não encontrado'})

        if path == '/' or path == '/index.html':
            if (WEB / 'index.html').is_file():
                return enviar_arquivo(self, WEB / 'index.html')

        if path.startswith('/producao/'):
            nome = path[len('/producao/'):]
            alvo = (OUT / nome).resolve()
            if str(alvo).startswith(str(OUT.resolve())) and alvo.is_file():
                return enviar_arquivo(self, alvo)
            return send_json(self, 404, {'ok': False, 'erro': 'imagem não encontrada'})

        if path == '/manifest.json' and (ROOT / 'manifest.json').is_file():
            return enviar_arquivo(self, ROOT / 'manifest.json')

        if path.startswith('/'):
            rel = path.lstrip('/')
            target = (WEB / rel).resolve()
            if str(target).startswith(str(WEB.resolve())) and target.is_file():
                return enviar_arquivo(self, target)

        send_json(self, 404, {'ok': False, 'erro': 'rota não encontrada'})

    def do_POST(self):
        """POST: criar job."""
        path = urlparse(self.path).path

        if path == '/api/imagens/job':
            try:
                tamanho = int(self.headers.get('Content-Length', '0')) or 0
                bruto = self.rfile.read(tamanho)
                corpo = json.loads(bruto or b'{}')
            except:
                return send_json(self, 400, {'ok': False, 'erro': 'JSON inválido'})

            prompt = str(corpo.get('prompt') or corpo.get('descricao') or '').strip()
            if not prompt:
                return send_json(self, 400, {'ok': False, 'erro': 'Informe um prompt'})

            return send_json(self, 202, {
                'ok': True,
                'job_id': create_job(prompt, corpo),
                'estado': 'fila'
            })

        send_json(self, 404, {'ok': False, 'erro': 'rota não encontrada'})

# ============ MAIN ============

if __name__ == '__main__':
    port = int(os.environ.get('PIPI_PORT', '7300'))
    print(f'\n{"="*60}')
    print(f'  Pipi IA — Servidor Refatorado')
    print(f'  http://127.0.0.1:{port}')
    print(f'{"="*60}\n')
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n\nServidor encerrado com sucesso.\n')
        server.shutdown()
