"""PIPI IA NA MODAL — gerador de imagem de verdade
venure.com.br · 13/09/2026

O QUE ISTO SUBSTITUI
    O endpoint que estava publicado (`modal_api_teste.py`) era um esqueleto:
    respondia {"mensagem": "Processamento simulado com sucesso"} e uma
    media_url apontando para exemplo.invalid. Servia para provar que a API
    respondia; nao gerava imagem nenhuma.

    Este aqui carrega o modelo e desenha.

POR QUE FLUX.1-schnell, E NAO O dev
    LICENCA. O schnell e Apache 2.0 -- uso comercial liberado. O dev e
    non-commercial: nao serve para criativo de cliente, que e o seu caso.

    E VELOCIDADE, que aqui e dinheiro. O schnell e destilado e gera em
    4 passos; o dev precisa de ~25. Como a Modal cobra por segundo de GPU,
    isso e a diferenca entre caber e nao caber nos $30 do mes.

POR QUE UM VOLUME
    O modelo tem ~24 GB. Sem Volume, TODO container frio baixaria os 24 GB
    de novo -- minutos de GPU paga so para chegar no ponto de partida. O
    Volume guarda o cache do HuggingFace entre execucoes: baixa uma vez,
    monta instantaneo depois.

    ATENCAO: armazenamento em Volume CONTINUA sendo cobrado mesmo com o
    spend limit em zero. Foi o que a propria tela da Modal avisou. E pouco
    para 24 GB, mas nao e zero.

POR QUE L40S, E NAO L4 -- A CONTA QUE EU ERREI      (17/09)
    A versao anterior pedia uma L4 e confiava no `enable_model_cpu_offload`
    para caber. Nao cabia, e nao havia como caber:

        torch.OutOfMemoryError: CUDA out of memory. Tried to allocate
        90.00 MiB. GPU 0 has a total capacity of 22.03 GiB of which
        77.12 MiB is free. Process 1 has 21.95 GiB memory in use.

    O transformer do FLUX tem 12 bilhoes de parametros. Em bfloat16 sao
    2 bytes cada: ~24 GB para ELE SO. A L4 anuncia 24 GB e entrega 22,03
    GiB utilizaveis. O modelo nao cabe nem sozinho, nem com nada.

    E o `enable_model_cpu_offload` nao resolve isso: ele troca MODELOS
    inteiros de lugar, um por vez -- e o maior deles continua sendo os
    24 GB. Quem fatia por submodulo e o `enable_sequential_cpu_offload`,
    que cabe em qualquer placa e leva minutos por imagem.

    A L40S tem 48 GB. O modelo inteiro sobe de uma vez, sem malabarismo.

    E SAI MAIS BARATO, nao mais caro (precos conferidos em 17/09):

        L40S   $0,000542/s   imagem quente em ~4s    ~$0,002
        L4     $0,000222/s   imagem em ~2min          ~$0,027
                             (com sequential offload, a unica que caberia)

    A L40S custa 2,4x por segundo e gasta 30x menos segundos. Placa mais
    barata que nao cabe nao e economia: e o mesmo dinheiro, gasto esperando.

O FLUX.1-schnell E APACHE 2.0 E MESMO ASSIM E GATED    (14/09)
    A licenca libera uso comercial, mas o repositorio no Hugging Face pede
    que voce aceite um formulario antes de baixar. Sem isso o download
    devolve 401 -- e foi exatamente o que derrubou este app:

        GatedRepoError: Access to model black-forest-labs/FLUX.1-schnell
        is restricted. You must have access to it and be authenticated.

    O container morria no @modal.enter(), a Modal subia outro, e ele morria
    igual. De hora em hora, desde o deploy. Quem pedia imagem ficava com o
    pedido "Pending" para sempre, sem mensagem de erro nenhuma.

    Por isso agora sao DOIS segredos, e o carregamento nao derruba mais o
    container: se falhar, ele guarda o motivo e RESPONDE o motivo.

COMO PUBLICAR

    pip install modal
    modal setup                       (uma vez, abre o navegador)

    1. Aceite a licenca (uma vez, no navegador, logado):
       https://huggingface.co/black-forest-labs/FLUX.1-schnell

    2. Crie um token de leitura em:
       https://huggingface.co/settings/tokens

    3. Guarde os dois segredos na Modal:

    modal secret create pipi-token PIPI_TOKEN=<invente-uma-senha-longa>
    modal secret create huggingface-token HF_TOKEN=<o token hf_... do passo 2>

    modal deploy modal_pipi.py

    O endereco sai no fim. Guarde junto com o token: no seu Windows,

        python usar_modal.py

CUSTO
    Cada imagem sao poucos segundos de GPU. O que pesa e o container frio:
    subir o modelo do Volume para a placa leva ~20 a 40 segundos, e isso
    conta. Por isso o `scaledown_window` abaixo mantem ele vivo por 2
    minutos depois do ultimo pedido -- quem gera varias imagens seguidas
    paga o aquecimento uma vez so.
"""

import io
import os
import time

import modal

APP = "pipi-ia"
MODELO = "black-forest-labs/FLUX.1-schnell"

# O cache do HuggingFace mora aqui, e sobrevive entre execucoes.
CACHE = "/cache"
volume = modal.Volume.from_name("pipi-modelos", create_if_missing=True)

imagem = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.5.1",
        "diffusers==0.32.2",
        "transformers==4.48.0",
        "accelerate==1.3.0",
        "sentencepiece==0.2.0",
        "protobuf==5.29.3",
        "huggingface_hub[hf_transfer]==0.28.1",
        "fastapi[standard]==0.115.8",
        "Pillow==11.1.0",
    )
    # hf_transfer acelera muito o primeiro download. So vale na primeira
    # vez, mas a primeira vez e justamente a cara.
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": CACHE})
)

app = modal.App(APP, image=imagem)


@app.cls(
    # 48 GB. O transformer do FLUX pede ~24 GB so para ele -- na L4, de
    # 22,03 GiB utilizaveis, nao cabia. Ver o cabecalho.
    gpu="L40S",
    volumes={CACHE: volume},
    # Dois segredos: um diz quem pode pedir imagem, o outro abre o
    # repositorio gated do FLUX. Ver o cabecalho.
    secrets=[modal.Secret.from_name("pipi-token"),
             modal.Secret.from_name("huggingface-token")],
    timeout=600,
    # CINCO MINUTOS, E NAO DOIS                                (17/09)
    #
    #   Medido no uso real do Fred: a imagem saia em ~40 segundos, quando o
    #   FLUX schnell em 4 passos leva 3 a 5 segundos quente. Os outros 35
    #   eram a placa acordando e subindo o modelo do Volume -- a cada
    #   imagem, porque 2 minutos nao cobrem o tempo de ler o resultado,
    #   ajustar uma palavra e pedir de novo.
    #
    #   Isso custava $0,022 por imagem em vez de $0,002. Dez vezes.
    #
    #   Cinco minutos cobrem uma rajada de ajuste: paga o aquecimento uma
    #   vez e as seguintes saem em segundos. Uma placa ociosa por 5 min
    #   custa $0,16 -- menos do que dois aquecimentos desperdicados.
    scaledown_window=300,
)
class Desenhista:

    @modal.enter()
    def carregar(self):
        """Roda UMA vez por container, nao a cada pedido.

        FALHAR AQUI NAO PODE DERRUBAR O CONTAINER            (14/09)
            Antes esta funcao deixava a excecao subir. A Modal trata isso
            como container quebrado: mata, sobe outro, ele quebra igual --
            crash-loop eterno. E o pedido de quem chamou fica "Pending",
            sem resposta e sem erro, ate o timeout de 10 minutos.

            Um erro que nao chega em ninguem custa mais caro do que o erro.
            Agora o motivo fica guardado e o `gerar` devolve ele.
        """
        self.pipe = None
        self.erro = ""
        try:
            import torch
            from diffusers import FluxPipeline

            self.pipe = FluxPipeline.from_pretrained(
                MODELO, torch_dtype=torch.bfloat16, cache_dir=CACHE,
                # Abre o repositorio gated. Sem isto: 401.
                token=(os.environ.get("HF_TOKEN") or "").strip() or None)
            # Tudo na placa de uma vez. Na L40S de 48 GB sobra metade.
            # Era aqui que estava o enable_model_cpu_offload, que prometia
            # caber na L4 e estourava na primeira imagem -- ver o cabecalho.
            self.pipe.to("cuda")
        except Exception as e:
            texto = "%s: %s" % (type(e).__name__, e)
            if "Gated" in texto or "401" in texto or "restricted" in texto:
                self.erro = (
                    "O Hugging Face recusou o download do FLUX.1-schnell "
                    "(401, repositorio gated). Duas coisas resolvem, nesta "
                    "ordem: (1) aceite a licenca em "
                    "https://huggingface.co/black-forest-labs/FLUX.1-schnell "
                    "com a sua conta; (2) rode `modal secret create "
                    "huggingface-token HF_TOKEN=hf_...` e `modal deploy "
                    "modal_pipi.py` de novo.")
            else:
                self.erro = "Nao consegui carregar o modelo. %s" % texto[:400]

    @modal.fastapi_endpoint(method="POST", docs=True)
    def gerar(self, dados: dict):
        import base64
        import torch

        # ---- quem esta pedindo? --------------------------------------
        # O endereco da Modal e publico. Sem token, qualquer um que o
        # descobrisse gastaria o seu credito -- e ele e limitado a $30.
        esperado = (os.environ.get("PIPI_TOKEN") or "").strip()
        recebido = str(dados.get("token") or "").strip()
        if not esperado:
            return {"ok": False,
                    "erro": "O segredo pipi-token nao foi configurado na Modal."}
        if recebido != esperado:
            # "TOKEN INVALIDO" SOZINHO MENTE POR OMISSAO           (17/09)
            #
            #   A Modal injeta o segredo quando o CONTEINER NASCE. Recem
            #   trocado o segredo, um conteiner que ja estava de pe ainda
            #   carrega o valor velho -- e responde "invalido" a um token
            #   que esta certo. Com o app em crash-loop, subindo de novo a
            #   cada 10 minutos, isso durou quase uma hora aqui: o Fred
            #   acertou o token e ouviu que estava errado.
            #
            #   Nao da para comparar os valores na mensagem (seria vazar o
            #   segredo). Da para dizer quantos caracteres cada lado tem,
            #   que separa "digitei outro" de "o conteiner esta velho", e
            #   da para lembrar do redeploy.
            return {"ok": False,
                    "erro": ("Token invalido. Recebi %d caracteres e esperava "
                             "%d. Se os numeros batem, o conteiner ainda esta "
                             "com o segredo antigo: rode `modal deploy "
                             "modal_pipi.py` e tente de novo em 1 minuto."
                             % (len(recebido), len(esperado)))}

        # O modelo carregou? Responder o motivo e melhor do que estourar:
        # quem chamou recebe texto em vez de um 500 mudo.
        if self.pipe is None:
            return {"ok": False,
                    "erro": self.erro or "O modelo nao esta carregado."}

        prompt = str(dados.get("prompt") or dados.get("descricao") or "").strip()
        if not prompt:
            return {"ok": False, "erro": "O campo 'prompt' e obrigatorio."}

        # ---- formato --------------------------------------------------
        # Os mesmos nomes que a tela da Pipi usa, para nao haver traducao
        # no meio do caminho.
        FORMATOS = {
            "quadrado": (1024, 1024), "retrato": (832, 1216),
            "paisagem": (1216, 832), "story": (768, 1344),
            "capa": (1344, 768),
        }
        largura, altura = FORMATOS.get(
            str(dados.get("formato") or "quadrado"), (1024, 1024))

        # O schnell e destilado: acima de ~4 passos nao melhora, so gasta
        # segundos de GPU. O teto de 8 existe para proteger o credito de
        # um valor digitado sem querer.
        passos = max(1, min(8, int(dados.get("passos") or 4)))

        semente = int(dados.get("semente") or 0)
        gerador = (torch.Generator("cpu").manual_seed(semente)
                   if semente else None)

        comeco = time.time()
        # UM 500 NAO CONTA NADA A QUEM PEDIU                    (17/09)
        #
        #   Sem este try, o estouro de memoria da L4 chegava na Pipi como
        #   "Modal respondeu 500: Internal Server Error". A causa estava
        #   nos registros da Modal -- oito telas de traceback -- e nao na
        #   mao de quem estava esperando a imagem.
        #
        #   Agora o motivo volta pelo mesmo caminho que a imagem voltaria.
        # ═══ CONTAR OS TOKENS EM VEZ DE ESTIMAR ═══════════════ (18/09) ═══
        #
        #   O teto de 256 e do T5, e o corte acontece EM SILENCIO: o prompt
        #   entra, o fim some, e a imagem sai sem a metade que voce pediu.
        #   Nada no caminho avisa.
        #
        #   Do lado da Pipi eu vinha adivinhando por contagem de palavras --
        #   e adivinhei errado: "180 palavras cabem com folga" nao cabiam.
        #   Mas o tokenizador de verdade esta AQUI, carregado, ao lado do
        #   modelo. Perguntar a ele custa milissegundos e acaba com o
        #   chute.
        #
        #   O numero volta junto com a imagem. Estimativa vira medicao.
        tokens_usados, cortou = None, False
        try:
            ids = self.pipe.tokenizer_2(
                prompt, truncation=False, add_special_tokens=True
            )["input_ids"]
            tokens_usados = len(ids)
            cortou = tokens_usados > 256
        except Exception:
            pass        # contar e um extra; nao pode impedir o desenho

        try:
            img = self.pipe(
                prompt,
                width=largura, height=altura,
                num_inference_steps=passos,
                # O schnell foi destilado SEM orientacao: guidance != 0 piora.
                guidance_scale=0.0,
                generator=gerador,
                max_sequence_length=256,
            ).images[0]
        except Exception as e:
            texto = "%s: %s" % (type(e).__name__, e)
            if "out of memory" in texto.lower():
                return {"ok": False,
                        "erro": ("A placa nao tem memoria para este modelo. "
                                 "O FLUX pede ~24 GB. Confira se o `gpu=` do "
                                 "modal_pipi.py esta em 'L40S' (48 GB) e rode "
                                 "`modal deploy modal_pipi.py` de novo. "
                                 "Detalhe: %s" % texto[:200])}
            return {"ok": False, "erro": "Falhou ao desenhar. %s" % texto[:400]}

        buf = io.BytesIO()
        img.save(buf, format="PNG")

        return {
            "ok": True,
            # base64 em vez de URL: nao precisa de bucket, nao expira e
            # nao deixa a imagem publica em lugar nenhum.
            "imagem_b64": base64.b64encode(buf.getvalue()).decode(),
            "formato": "png",
            "largura": largura, "altura": altura,
            "passos": passos, "semente": semente,
            "segundos": round(time.time() - comeco, 1),
            "modelo": MODELO,
            # Medido pelo T5 deste conteiner, nao estimado por palavra.
            "tokens": tokens_usados, "teto_tokens": 256, "cortou": cortou,
            "licenca": "Apache-2.0 (uso comercial liberado)",
        }
