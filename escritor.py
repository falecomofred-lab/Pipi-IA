"""O ESCRITOR DE PROMPT — o modelo do Bigode virando redator de imagem
Venure · venure.com.br · 17/09/2026

Voce escreve em portugues solto: "cafe ao amanhecer, algo pra story".
Isto devolve um prompt em ingles com luz, lente, composicao e material --
que e o que o FLUX entende bem.

POR QUE NAO PASSAR PELO CHAT DO BIGODE
    Seria o caminho obvio: a Pipi chama /api/chat e pronto. Mas o prompt
    de sistema do Bigode tem ~3.835 tokens de identidade, regras de
    conduta e o esquema de 34 ferramentas. Nada disso tem a ver com
    reescrever uma frase -- e tudo isso seria LIDO em cada pedido, antes
    da sua frase, a cada imagem.

    No motor local, a ~4 tok/s de prefill, e espera pura. Na Modal, e
    segundo de placa pago. No Hugging Face, e token pago.

    Entao a Pipi fala DIRETO com o modelo, com um prompt de sistema
    proprio de 20 linhas. Mesmo modelo, mesma conta, sem a bagagem.

DE ONDE VEM O ENDERECO
    Do config.json do Cerebro -- a mesma fonte que o Bigode usa. Uma
    verdade so sobre qual modelo esta valendo: trocar de motor lá muda
    aqui, sem ninguem reconfigurar nada.

O QUE ELE SABE DO FLUX, E POR QUE CADA REGRA EXISTE
    . INGLES. O T5 que le a frase foi treinado esmagadoramente em ingles.
      Portugues funciona e entrega menos, sobretudo em luz e lente.
    . PROSA, nao lista de palavras. O FLUX nao e SDXL: "masterpiece, best
      quality, 8k" piora o resultado em vez de melhorar.
    . NADA DE NEGATIVA. O schnell e destilado com guidance_scale=0.0 -- o
      mecanismo que faz "sem X" funcionar nao existe nele. "Fundo limpo"
      sim; "sem bagunca" nao.
    . TETO DE ~200 PALAVRAS. O max_sequence_length e 256 tokens. Passando
      disso o resto e cortado EM SILENCIO.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# O manual do FLUX, condensado. Curto de proposito: instrucao longa gasta
# a janela do modelo e, num 7B, dilui o que importa.
SISTEMA = """You rewrite image ideas into prompts for FLUX.1-schnell.
Think like a director of photography, not like a tagger.

Rules:
1. Answer with the prompt ONLY. No preamble, no quotes, no explanation.
2. Write in ENGLISH, as flowing prose in two or three active sentences.
3. Never use keyword lists, never use words like "masterpiece", "8k",
   "best quality", "trending on artstation", "octane render". The T5
   encoder reads grammar, not tags. Tag soup degrades FLUX output.
4. Never write what to avoid. There is no negative prompt. Say what IS
   there instead: "clean background", not "no clutter".
5. Stay under 120 words. Hard ceiling; the rest is cut in silence.
6. BUILD THE FRAME IN LAYERS, with spatial prepositions: what is in the
   foreground, what sits behind it, what closes the background. A model
   running in four steps resolves three clear planes far better than
   fifteen scattered objects.
7. PHYSICS, NOT ADJECTIVES. Never "beautiful lighting" or "vivid colours".
   Name the actual light source and its direction, the colour temperature,
   the grading, the lens and aperture. Say "low winter sun raking in from
   the left, warm amber on the steam, deep blue shadow behind, 50mm at
   f/1.8, shallow depth of field" -- not "amazing morning light".
8. Materials and texture beat quantity: brushed steel, chipped enamel,
   condensation, worn oak. One surface described well is worth ten named.
9. Keep any text the user wants inside the image in quotes, verbatim.
   FLUX renders legible text well.
10. Keep the user's intent. Do not add people, brands or objects they did
    not ask for."""


def _cfg_cerebro():
    """O config.json do Bigode. Mesma busca que o pipi_server faz pelo CSS."""
    for base in (os.environ.get("BIGODE_CEREBRO", "").strip(),
                 str(RAIZ.parent / "Cerebro"),
                 str(Path.home() / "Downloads" / "Cerebro")):
        if not base:
            continue
        arq = Path(base) / "config.json"
        if arq.is_file():
            try:
                return json.loads(arq.read_text(encoding="utf-8-sig") or "{}")
            except Exception:
                return {}
    return {}


def _destino(cfg):
    """(url, cabecalhos, modelo) do motor que o Bigode esta usando agora."""
    provedor = str(cfg.get("modelo_provedor") or "local").lower()

    if provedor == "huggingface":
        hf = cfg.get("huggingface") or {}
        token = (os.environ.get("HF_TOKEN", "").strip()
                 or str(hf.get("token") or "").strip())
        if not token:
            raise RuntimeError("o Bigode esta em Hugging Face, mas sem token")
        return ("https://router.huggingface.co/v1/chat/completions",
                {"Content-Type": "application/json",
                 "Authorization": "Bearer " + token},
                str(hf.get("texto_modelo")
                    or "Qwen/Qwen2.5-Coder-32B-Instruct"))

    if provedor == "modal":
        m = cfg.get("modal") or {}
        url = str(m.get("url") or "").strip()
        if not url:
            raise RuntimeError("o Bigode esta em Modal, mas sem endereco")
        cab = {"Content-Type": "application/json"}
        if m.get("token"):
            cab["Authorization"] = "Bearer " + str(m["token"]).strip()
        return url, cab, ""

    url = str(cfg.get("llm_url") or "").strip()
    if not url:
        raise RuntimeError("nao achei o endereco do motor no config do Bigode")
    cab = {"Content-Type": "application/json"}
    if cfg.get("llm_chave"):
        cab["Authorization"] = "Bearer " + str(cfg["llm_chave"]).strip()
    return url, cab, ""


def disponivel():
    try:
        _destino(_cfg_cerebro())
        return True
    except Exception:
        return False


def _limpar(texto):
    """Tira o que o modelo insiste em pôr em volta do prompt.

    Modelo pequeno quase sempre embrulha: "Here is the prompt:", aspas,
    cerca de codigo, um "Prompt:" na frente. Nada disso vai para o FLUX --
    e deixar passar significa gastar tokens do teto de 256 com lixo.
    """
    t = (texto or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("```", 1)[0]
    linhas = [l for l in t.splitlines() if l.strip()]
    # Descarta uma primeira linha que seja so anuncio.
    if linhas and len(linhas) > 1:
        primeira = linhas[0].lower().rstrip(":").strip()
        if (len(primeira) < 60 and
                any(p in primeira for p in ("prompt", "here is", "aqui esta",
                                            "sure", "certainly"))):
            linhas = linhas[1:]
    t = " ".join(l.strip() for l in linhas).strip()
    for par in ('""', "''", "“”"):
        if len(t) > 1 and t[0] == par[0] and t[-1] == par[1]:
            t = t[1:-1].strip()
    if t.lower().startswith("prompt:"):
        t = t[7:].strip()

    # O TETO DE 256 TOKENS E REAL, E 180 PALAVRAS NAO CABIAM   (18/09)
    #
    #   Este trecho dizia "180 palavras ficam com folga dentro dos 256
    #   tokens". Eu nao contei. O T5 quebra em SentencePiece, e prosa de
    #   fotografia e cara: "bioluminescence", "f/1.8", "Portra", nome de
    #   lente e temperatura de cor viram 2 ou 3 pedacos cada. A conta real
    #   fica perto de 1,4 token por palavra, as vezes 1,6.
    #
    #       180 x 1,4 = 252    no limite, sem margem
    #       180 x 1,6 = 288    cortado em silencio
    #
    #   Ou seja: a regra que existia para impedir o corte era, ela mesma,
    #   uma aposta no corte. Terceira afirmacao minha nesta semana escrita
    #   como fato sem conferencia -- as outras duas foram o <img> da tela
    #   do Bigode e o ponte.txt "criado ao abrir a Pipi".
    #
    #   120 palavras (~170 tokens no pior caso) cabem com folga de verdade.
    #   E folga aqui nao e desperdicio: o FLUX.1-schnell roda em 4 passos e
    #   nao tem como resolver quinze elementos: descricao precisa de tres
    #   planos rende mais do que uma lista longa.
    #
    #   Ainda assim isto continua sendo estimativa. Quem conta de verdade e
    #   o proprio T5, la na Modal, que ja esta carregado -- e agora devolve
    #   o numero junto com a imagem.
    palavras = t.split()
    if len(palavras) > 120:
        t = " ".join(palavras[:120])
    return t


def escrever(ideia, formato="", timeout=240):
    """Devolve (prompt_em_ingles, modelo_usado). Levanta em caso de falha."""
    ideia = (ideia or "").strip()
    if not ideia:
        raise RuntimeError("escreva a ideia primeiro")

    cfg = _cfg_cerebro()
    url, cabecalhos, modelo = _destino(cfg)

    pedido_humano = "Image idea (Portuguese): %s" % ideia
    if formato:
        # O formato muda o enquadramento, e o modelo precisa saber disso
        # para sugerir plano e lente coerentes -- retrato pede outra coisa
        # que capa.
        jeito = {"quadrado": "square 1:1", "retrato": "vertical portrait 2:3",
                 "paisagem": "horizontal landscape 3:2",
                 "story": "tall vertical 9:16", "capa": "wide banner 16:9"}
        if formato in jeito:
            pedido_humano += "\nFraming: %s." % jeito[formato]

    corpo = {
        "messages": [{"role": "system", "content": SISTEMA},
                     {"role": "user", "content": pedido_humano}],
        # Baixa de proposito: aqui nao se quer criatividade na REDACAO, se
        # quer fidelidade a ideia. A criatividade e do FLUX.
        "temperature": 0.3,
        "max_tokens": 320,
        "stream": False,
    }
    if modelo:
        corpo["model"] = modelo

    req = urllib.request.Request(
        url, data=json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
        headers=cabecalhos, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError("o motor do Bigode respondeu %s: %s"
                           % (e.code, detalhe)) from e
    except Exception as e:
        raise RuntimeError(
            "nao cheguei no motor do Bigode (%s). Ele esta aberto?" % e) from e

    try:
        bruto = dados["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        bruto = str(dados.get("text") or dados.get("mensagem") or "")

    prompt = _limpar(bruto)
    if not prompt:
        raise RuntimeError("o motor respondeu sem texto")
    return prompt, (modelo or str(cfg.get("modelo_atual")
                                  or cfg.get("modelo") or "motor local"))
