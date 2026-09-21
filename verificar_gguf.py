#!/usr/bin/env python3
"""Verifica GGUF sem carregar o modelo inteiro na memória.

Uso:
  python verificar_gguf.py
  python verificar_gguf.py "G:\\Outros computadores\\USB e dispositivos externos\\Pen IA"
  python verificar_gguf.py --load-test "C:\\caminho\\llamafile.exe"

A validação estrutural é aplicável a GGUF de texto e imagem. O teste de carga
com llamafile/llama-cli só é feito quando solicitado e é apropriado para modelos
compatíveis com llama.cpp; GGUF de difusão pode passar no cabeçalho e ainda não
ser executável por llama.cpp.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, struct, subprocess, sys, time
from pathlib import Path

DEFAULT_ROOTS = [
    r"G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem",
    r"G:\Outros computadores\USB e dispositivos externos\Pen IA",
]

class ParseError(Exception): pass
class Reader:
    def __init__(self, f, size): self.f=f; self.size=size; self.pos=0
    def read(self,n):
        if n < 0 or self.pos+n > self.size: raise ParseError(f"fim inesperado em {self.pos}, necessário {n} bytes")
        b=self.f.read(n)
        if len(b)!=n: raise ParseError(f"leitura incompleta em {self.pos}")
        self.pos+=n; return b
    def u32(self): return struct.unpack('<I',self.read(4))[0]
    def u64(self): return struct.unpack('<Q',self.read(8))[0]
    def i8(self): return struct.unpack('<b',self.read(1))[0]
    def string(self):
        n=self.u64()
        if n > 16*1024*1024: raise ParseError(f"string excessivamente grande: {n}")
        return self.read(n).decode('utf-8','replace')
    def value(self, typ, depth=0):
        if depth>8: raise ParseError('array aninhado demais')
        # GGUF metadata value types: UINT8, INT8, UINT16, INT16, UINT32,
        # INT32, FLOAT32, BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64.
        if typ==0: return struct.unpack('<B',self.read(1))[0]
        if typ==1: return struct.unpack('<b',self.read(1))[0]
        if typ==2: return struct.unpack('<H',self.read(2))[0]
        if typ==3: return struct.unpack('<h',self.read(2))[0]
        if typ==4: return struct.unpack('<I',self.read(4))[0]
        if typ==5: return struct.unpack('<i',self.read(4))[0]
        if typ==6: return struct.unpack('<f',self.read(4))[0]
        if typ==7: return struct.unpack('<?',self.read(1))[0]
        if typ==8: return self.string()
        if typ==9:
            subtype=self.u32(); n=self.u64()
            if n>10_000_000: raise ParseError(f"array excessivamente grande: {n}")
            for _ in range(n): self.value(subtype,depth+1)
            return f"array[{n}]"
        if typ==10: return self.u64()
        if typ==11: return struct.unpack('<q',self.read(8))[0]
        if typ==12: return struct.unpack('<d',self.read(8))[0]
        raise ParseError(f"tipo de metadado desconhecido: {typ}")

def sha256(path, chunk=8*1024*1024):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(chunk): h.update(b)
    return h.hexdigest()

def inspect(path):
    result={'arquivo':str(path),'nome':path.name,'tamanho_bytes':path.stat().st_size,'status':'ERRO','tipo':'desconhecido','arquitetura':'','erro':'','sha256':''}
    try:
        with path.open('rb') as f:
            r=Reader(f,path.stat().st_size)
            if r.read(4)!=b'GGUF': raise ParseError('magic GGUF ausente')
            version=r.u32(); tensors=r.u64(); kvs=r.u64()
            result.update({'versao':version,'tensors':tensors,'metadados':kvs})
            if version not in (1,2,3): raise ParseError(f'versão GGUF não suportada: {version}')
            if tensors>10_000_000 or kvs>1_000_000: raise ParseError('contagens incompatíveis com um arquivo GGUF normal')
            arch=''; keys=[]
            for _ in range(kvs):
                key=r.string(); typ=r.u32(); value=r.value(typ); keys.append(key)
                if key.endswith('.architecture') or key=='general.architecture': arch=str(value)
            infos=[]
            for _ in range(tensors):
                name=r.string(); dims=r.u32()
                if dims>16: raise ParseError(f'número de dimensões inválido: {dims}')
                shape=[r.u64() for _ in range(dims)]; typ=r.u32(); offset=r.u64()
                infos.append((name,shape,typ,offset))
            # O cabeçalho e as tabelas foram lidos sem sair do arquivo.
            # Os offsets são relativos ao início dos dados; não podem apontar antes.
            data_base=((r.pos+31)//32)*32
            if infos and any(off > path.stat().st_size-data_base for _,_,_,off in infos):
                raise ParseError('offset de tensor aponta além do tamanho do arquivo')
            result['arquitetura']=arch
            result['tipo']='imagem/difusão' if any(x in arch.lower() for x in ('flux','sdxl','stable','diffusion','dit')) else 'texto/llama ou outro'
            result['status']='OK_ESTRUTURA'
            result['bytes_cabecalho']=r.pos
            result['data_base_estimado']=data_base
            result['chaves_amostra']=keys[:8]
        # Hash é calculado somente depois da estrutura passar.
        result['sha256']=sha256(path)
    except Exception as exc:
        result['erro']=str(exc)
    return result

def load_test(path, executable, timeout):
    if not executable: return {'status':'NAO_EXECUTADO','detalhe':'llamafile/llama-cli não informado'}
    cmd=[executable,'-m',str(path),'--log-disable','-c','8','-n','1','-p','teste']
    started=time.time()
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        text=(p.stdout+'\n'+p.stderr).strip()[-1200:]
        return {'status':'OK_CARGA' if p.returncode==0 else 'FALHA_CARGA','codigo':p.returncode,'segundos':round(time.time()-started,1),'detalhe':text}
    except subprocess.TimeoutExpired:
        return {'status':'TIMEOUT_CARGA','segundos':round(time.time()-started,1),'detalhe':f'tempo limite de {timeout}s'}
    except Exception as exc:
        return {'status':'ERRO_EXECUTAVEL','detalhe':str(exc)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('roots',nargs='*',default=None); ap.add_argument('--load-test',dest='exe'); ap.add_argument('--timeout',type=int,default=180); ap.add_argument('--out',default='relatorio_gguf.json'); args=ap.parse_args()
    roots=[Path(x) for x in (args.roots or DEFAULT_ROOTS)]
    files=[]
    for root in roots:
        if root.exists(): files.extend(p for p in root.rglob('*.gguf') if p.is_file())
        else: print(f'[AVISO] pasta não encontrada: {root}',file=sys.stderr)
    unique=[]; seen=set()
    for p in files:
        key=str(p.resolve()).lower()
        if key not in seen: seen.add(key); unique.append(p)
    rows=[]
    for i,p in enumerate(sorted(unique,key=lambda x:str(x).lower()),1):
        print(f'[{i}/{len(unique)}] {p}',flush=True); item=inspect(p)
        if args.exe and item['status']=='OK_ESTRUTURA' and item['tipo'].startswith('texto'):
            item['teste_carga']=load_test(p,args.exe,args.timeout)
        else: item['teste_carga']={'status':'NAO_APLICAVEL' if item['status']=='OK_ESTRUTURA' else 'NAO_EXECUTADO','detalhe':'GGUF de imagem/estrutura inválida'}
        rows.append(item)
    report={'gerado_em':time.strftime('%Y-%m-%dT%H:%M:%S'),'pastas': [str(x) for x in roots],'total':len(rows),'resumo':{},'arquivos':rows}
    for status in ('OK_ESTRUTURA','ERRO'):
        report['resumo'][status]=sum(x['status']==status for x in rows)
    report['resumo']['carga_ok']=sum(x.get('teste_carga',{}).get('status')=='OK_CARGA' for x in rows)
    Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with Path(args.out).with_suffix('.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['arquivo','tipo','tamanho_bytes','versao','tensors','metadados','status','erro','sha256','teste_carga']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for x in rows:
            y=dict(x); y['teste_carga']=y.get('teste_carga',{}).get('status',''); w.writerow({k:y.get(k,'') for k in fields})
    print(json.dumps(report['resumo'],ensure_ascii=False))
    print(f'Relatórios: {args.out} e {Path(args.out).with_suffix(".csv")}')
    return 0 if all(x['status']=='OK_ESTRUTURA' for x in rows) else 2
if __name__=='__main__': raise SystemExit(main())
