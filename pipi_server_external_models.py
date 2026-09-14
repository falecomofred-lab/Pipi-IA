#!/usr/bin/env python3
"""Servidor independente da Pipi IA.

Serve a interface própria e fornece um maestro mínimo para motores de imagem.
A geração real é delegada a um ComfyUI configurado via PIPI_COMFYUI_URL;
sem ele, a Pipi permanece funcional para catálogo, saúde, jobs e preparação.
"""
from __future__ import annotations
import json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
WEB=ROOT/'web'; MODELS=ROOT/'motores'; OUT=ROOT/'producao'
COMFY=os.environ.get('PIPI_COMFYUI_URL','').rstrip('/')
# Pasta oficial dos motores no computador Windows. Substitua por
# PIPI_MODELS_DIR se a letra da unidade ou a montagem mudar.
MODELS_DIR=Path(os.environ.get(
    'PIPI_MODELS_DIR',
    r'G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem'
))
JOBS={}; LOCK=threading.RLock()

def catalog():
    data=json.loads((ROOT/'motores.json').read_text(encoding='utf-8'))
    for item in data:
        nome=item.get('arquivo','')
        path=MODELS_DIR/nome
        if not path.exists() and MODELS_DIR.exists():
            encontrados=list(MODELS_DIR.rglob(nome))
            if encontrados:
                path=encontrados[0]
        item['baixado']=path.exists()
        item['tamanho_local']=path.stat().st_size if path.exists() else 0
        item['caminho_local']=str(path) if path.exists() else str(MODELS_DIR/nome)
    return data

def job(prompt, payload):
    jid='pipi_'+uuid.uuid4().hex[:12]
    with LOCK: JOBS[jid]={'id':jid,'estado':'fila','criado_em':time.time(),'prompt':prompt,'resultado':None,'erro':''}
    threading.Thread(target=run,args=(jid,prompt,payload),daemon=True).start()
    return jid

def run(jid,prompt,payload):
    with LOCK: JOBS[jid]['estado']='preparando'
    if not COMFY:
        with LOCK:
            JOBS[jid].update(estado='erro',erro='Nenhum motor de execução foi conectado. Instale o ComfyUI e defina PIPI_COMFYUI_URL; o catálogo de modelos está disponível em motores.json.')
        return
    # Esqueleto de integração: o workflow específico deve ser colocado em workflow.json.
    wf=ROOT/'workflow.json'
    if not wf.exists():
        with LOCK:
            JOBS[jid].update(estado='erro',erro='ComfyUI foi encontrado, mas falta workflow.json. Copie um workflow de texto para imagem e configure o nó de prompt.')
        return
    with LOCK: JOBS[jid].update(estado='erro',erro='Workflow detectado, mas o adaptador ComfyUI ainda precisa mapear os nós do seu workflow. Nenhuma imagem falsa é criada.')

def send_json(h,status,data):
    raw=json.dumps(data,ensure_ascii=False).encode(); h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Content-Length',str(len(raw))); h.end_headers(); h.wfile.write(raw)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/health': return send_json(self,200,{'ok':True,'servico':'pipi','estado':'pronto','comfyui':bool(COMFY),'motores':len(catalog()),'pasta_motores':str(MODELS_DIR),'pasta_existe':MODELS_DIR.exists()})
        if path=='/api/imagens': return send_json(self,200,{'ok':True,'motores':catalog(),'comfyui':bool(COMFY),'pasta_motores':str(MODELS_DIR),'pasta_existe':MODELS_DIR.exists(),'producao':str(OUT)})
        if path.startswith('/api/imagens/job/'):
            jid=path.rsplit('/',1)[-1]
            with LOCK: item=JOBS.get(jid)
            return send_json(self,200 if item else 404,item or {'ok':False,'erro':'job não encontrado'})
        if path=='/' or path=='/index.html':
            data=(WEB/'index.html').read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        rel=path.lstrip('/')
        target=(WEB/rel).resolve()
        if str(target).startswith(str(WEB.resolve())) and target.is_file():
            data=target.read_bytes(); self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        send_json(self,404,{'ok':False,'erro':'rota não encontrada'})
    def do_POST(self):
        path=urlparse(self.path).path
        if path!='/api/imagens/job': return send_json(self,404,{'ok':False,'erro':'rota não encontrada'})
        try: data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')) or 0) or '{}')
        except Exception: return send_json(self,400,{'ok':False,'erro':'JSON inválido'})
        prompt=str(data.get('prompt') or data.get('descricao') or '').strip()
        if not prompt: return send_json(self,400,{'ok':False,'erro':'Informe um prompt'})
        return send_json(self,202,{'ok':True,'job_id':job(prompt,data),'estado':'fila'})
if __name__=='__main__':
    port=int(os.environ.get('PIPI_PORT','7300')); print(f'Pipi IA independente em http://127.0.0.1:{port}'); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
