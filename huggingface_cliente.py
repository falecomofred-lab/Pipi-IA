"""Cliente opcional da Hugging Face para a Pipi IA."""
from __future__ import annotations
import os
from pathlib import Path
class HuggingFaceError(RuntimeError): pass
def token(): return os.environ.get('HF_TOKEN','').strip()
def configurado(): return bool(token())
def _client():
    try: from huggingface_hub import InferenceClient
    except ImportError as exc: raise HuggingFaceError('Instale huggingface_hub para usar a API Hugging Face.') from exc
    return InferenceClient(token=token() or None)
def text_to_image(prompt, model=None, negative_prompt=None, width=None, height=None, steps=None, guidance=None, seed=None):
    try:
        return _client().text_to_image(prompt=prompt, model=model or os.environ.get('HF_IMAGE_MODEL'), negative_prompt=negative_prompt or None, width=width, height=height, num_inference_steps=steps, guidance_scale=guidance, seed=seed)
    except Exception as exc: raise HuggingFaceError(f'Hugging Face imagem falhou: {exc}') from exc
def download(repo_id, filename, destination, revision=None):
    try: from huggingface_hub import hf_hub_download
    except ImportError as exc: raise HuggingFaceError('Instale huggingface_hub para baixar modelos.') from exc
    dest=Path(destination); dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        cached=hf_hub_download(repo_id=repo_id, filename=filename, revision=revision); dest.write_bytes(Path(cached).read_bytes()); return str(dest)
    except Exception as exc: raise HuggingFaceError(f'Download Hugging Face falhou: {exc}') from exc
def status(): return {'configurado':configurado(),'token_presente':bool(token()),'imagem_modelo':os.environ.get('HF_IMAGE_MODEL','')}
