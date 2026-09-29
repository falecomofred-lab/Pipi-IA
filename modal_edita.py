"""PIPI EDITA — transformar uma imagem que já existe
Venure · venure.com.br · 17/09/2026

Recebe UMA imagem e uma instrução ("troque o fundo por um estúdio branco",
"deixe a camisa azul", "tire a placa da parede") e devolve a imagem editada.

O MODELO, E POR QUE ESTE
    Qwen/Qwen-Image-Edit. Conferido hoje na API do Hugging Face:

        "license": "apache-2.0"       uso comercial liberado
        "gated": false                sem formulario no caminho
        "library_name": "diffusers"   mesma biblioteca do modal_pipi.py
        parametros BF16: 20.430.401.088

    Apache 2.0 importa: e criativo de cliente. E "gated: false" importa
    porque foi exatamente o formulario do FLUX que deixou a Pipi um dia
    inteiro em crash-loop.

    Ao contrario do FLUX schnell, este ACEITA prompt negativo -- ele usa
    true_cfg_scale, entao o mecanismo de "evite X" existe aqui.

EU ERREI A CONTA DE MEMORIA, E ESTE ARQUIVO NAO REPETE O ERRO   (17/09)
    Eu disse ao Fred que este modelo "cabe numa L40S com folga", olhando
    para o .gguf de 15 GB do pendrive. Errado por dois motivos:

      1. O .gguf de 15 GB e QUANTIZADO e serve ao ComfyUI, nao ao
         diffusers. Aqui os pesos vem em bfloat16.
      2. Em bfloat16 sao 20,43 bilhoes de parametros x 2 bytes = ~41 GB.
         A L40S tem 48. Cabem os pesos e sobra quase nada para as
         ativacoes e para o VAE fechar a imagem.

    E o mesmo erro que eu cometi com o FLUX na L4, onde jurei que o
    cpu_offload resolvia e ele estourou na primeira imagem.

    Entao desta vez NAO afirmo que cabe. O arquivo:

      . usa cpu_offload, que mantem na placa um modelo por vez em vez de
        todos -- e aqui o maior deles e bem menor que os 41 GB do total;
      . MEDE o pico de VRAM e devolve o numero em toda resposta;
      . tem a placa numa constante de uma linha.

    A primeira edicao responde, com numero, a pergunta que eu nao deveria
    ter respondido de cabeca: L40S basta, ou precisa subir?

O ARMAZENAMENTO NAO E DE GRACA, E ISSO PESA NO SEU TETO
    Os pesos ficam no Volume: ~58 GB para este modelo, alem dos ~24 GB do
    FLUX que ja estao la. Volume custa $0,09 por GB por mes E CONTINUA
    SENDO COBRADO com o spend limit em zero.

        82 GB x $0,09 = ~$7,40 por mes

    Isso e um quarto do seu teto de $30, parado, sem gerar nada. Se a
    edicao de imagem for ocasional, vale apagar o Volume dela entre usos:

        python -m modal volume delete pipi-edita-modelos

COMO PUBLICAR

    python -m modal deploy modal_edita.py

    O endereco sai no fim, terminado em `-editor-editar.modal.run`.
    Depois:  python usar_modal.py --edicao
"""

import base64
import io
import os
import time

import modal

APP = "pipi-edita"
MODELO = "Qwen/Qwen-Image-Edit"

# A PLACA FICA AQUI, NUMA LINHA                               (17/09)
#
#   Trocar de placa deve ser uma palavra, nao uma caca pelo arquivo. E o
#   numero que decide a troca sai na propria resposta ("vram_pico_gb").
#
#   A escada de precos da Modal, para nao decidir de memoria:
#       L40S      48 GB   $0,000542/s
#       A100      80 GB   $0,000694/s
#       H100      80 GB   $0,001097/s
#       H200     141 GB   $0,001261/s
PLACA = "L40S"
PRECO_SEG = {"L40S": 0.000542, "A100-40GB": 0.000583, "A100-80GB": 0.000694,
             "H100": 0.001097, "H200": 0.001261}.get(PLACA, 0.000542)

CACHE = "/cache"
volume = modal.Volume.from_name("pipi-edita-modelos", create_if_missing=True)

def _baixar():
    """Traz os ~41 GB para o Volume DURANTE a construcao da imagem.

    SEM ISTO, O DOWNLOAD ACONTECIA NO PRIMEIRO PEDIDO          (22/09)

        O `from_pretrained` do `carregar()` baixa o que falta. Como nao
        havia nenhum passo de download na construcao, esses 41 GB viriam
        no primeiro `editar` -- com a L40S ja ligada e contando $0,000542
        por segundo, esperando rede.

        Nao e so caro: e o tipo de espera que estoura o tempo do primeiro
        pedido, falha, e faz a pessoa tentar de novo -- pagando o
        aquecimento outra vez sem nunca chegar ao fim.

        Aqui acontece uma vez, no `modal deploy`, com voce olhando, e sem
        placa reservada.

    Funcao com nome, no topo do arquivo, e nao lambda:
        InvalidError: Image.run_function does not support lambda functions.
    """
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=MODELO, cache_dir=CACHE,
                      # Os .bin sao a versao antiga dos mesmos pesos que os
                      # .safetensors. Sem este filtro, o download dobra.
                      ignore_patterns=["*.bin", "*.pth", "*.msgpack"])


imagem = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        # SEM PINO NESTES QUATRO, E ESTA E A EXCECAO DA CASA     (22/09)
        #
        #   A regra do projeto e prender versao (a licao do faster-whisper).
        #   Aqui ela nao serve, e o motivo esta no proprio model card do
        #   Qwen-Image-Edit, conferido hoje:
        #
        #       "Install the latest version of diffusers
        #        pip install git+https://github.com/huggingface/diffusers"
        #
        #   O modelo e novo e usa o Qwen2.5-VL como text encoder. Com
        #   transformers 4.51.3 + diffusers 0.35.1 o carregamento morria em:
        #
        #       AttributeError: 'dict' object has no attribute 'to_dict'
        #
        #   -- que e transformers velho recebendo uma config aninhada que
        #   ele nao sabe montar. Prender numeros aqui e escolher uma
        #   combinacao no escuro e pagar 20 minutos de build por tentativa;
        #   ja paguei duas.
        #
        #   Entao: pip resolve. E, para isso nao virar um misterio no dia em
        #   que quebrar, o `carregar()` abaixo DEVOLVE as versoes que
        #   entraram -- a medicao vem junto com o erro, nao depois dele.
        "torch",
        # O torchvision NAO vem junto com o torch, e o transformers
        # precisa dele so para EXISTIR o AutoVideoProcessor -- que este
        # modelo nem usa, mas que e carregado no import da familia Qwen2.5-VL:
        #
        #     ImportError: AutoVideoProcessor requires the Torchvision
        #     library but it was not found in your environment.
        #
        # Esta linha existe no modal_olho.py desde o primeiro dia. Aqui eu
        # simplesmente nao a escrevi.
        "torchvision",
        "diffusers",
        "transformers",
        "accelerate",
        "sentencepiece==0.2.0",
        "protobuf==5.29.3",
        # FAIXA, E NAO NUMERO EXATO — E POR QUE                  (22/09)
        #
        #   Estava `==0.28.1`, copiado do modal_voz.py e do modal_olho.py.
        #   La funciona; aqui nao, e o pip disse por que:
        #
        #       diffusers 0.35.1 depends on huggingface-hub>=0.34.0
        #       The user requested huggingface_hub==0.28.1
        #
        #   Dois pinos que nao podem coexistir. Copiei a versao sem olhar
        #   o que mais estava na lista -- o diffusers nao existe naqueles
        #   arquivos.
        #
        #   O pino exato continua sendo a regra da casa (a licao do
        #   faster-whisper), mas aqui ele precisa CABER: a faixa prende o
        #   que importa de verdade, que e nao saltar para a major 1.x, e
        #   deixa o pip achar um numero que sirva aos tres pacotes.
        "huggingface_hub[hf_transfer]>=0.34.0,<1.0",
        "fastapi[standard]==0.115.8",
        "Pillow==11.1.0",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": CACHE})
    .run_function(_baixar, volumes={CACHE: volume}, timeout=60 * 60)
)

app = modal.App(APP, image=imagem)


@app.cls(
    gpu=PLACA,
    volumes={CACHE: volume},
    secrets=[modal.Secret.from_name("pipi-token")],
    timeout=900,
    # Editar e conversa: voce olha o resultado, muda a instrucao e pede de
    # novo. Cinco minutos cobrem a rajada -- a licao dos 40 segundos.
    scaledown_window=300,
    # UMA PLACA, NUNCA DUAS                                    (22/09)
    #   Sem este teto, dois pedidos ao mesmo tempo -- duas abas abertas,
    #   ou um clique duplo -- sobem DUAS L40S. Sao ~US$ 3,90 por hora, e
    #   voce so descobriria na fatura. Editar e coisa de um de cada vez.
    max_containers=1,
)
class Editor:

    @modal.enter()
    def carregar(self):
        """Falhar aqui NAO derruba o container. A licao do modal_pipi.py."""
        self.pipe = None
        self.erro = ""
        try:
            import torch
            from diffusers import QwenImageEditPipeline

            self.pipe = QwenImageEditPipeline.from_pretrained(
                MODELO, torch_dtype=torch.bfloat16, cache_dir=CACHE)
            # UM MODELO POR VEZ NA PLACA
            #   Os pesos somam ~41 GB; a L40S tem 48. Com tudo junto nao
            #   sobra para ativacao nem para o VAE. O cpu_offload mantem na
            #   placa so o componente em uso -- e o maior deles e bem menor
            #   que o total. Se ainda estourar, o erro diz para subir PLACA.
            self.pipe.enable_model_cpu_offload()
        except Exception as e:
            texto = "%s: %s" % (type(e).__name__, e)
            # AS VERSOES VAO JUNTO COM O ERRO                    (22/09)
            #
            #   Sem isto, "'dict' object has no attribute 'to_dict'" e um
            #   enigma: nao da para saber com que combinacao de bibliotecas
            #   ele aconteceu, e o conserto vira tentativa e erro de 20
            #   minutos cada. Com as versoes na mao, o proximo passo e uma
            #   decisao, nao um palpite.
            self.erro = "Nao consegui carregar o %s. %s | %s" % (
                MODELO, texto[:350], self._versoes())

    @staticmethod
    def _versoes():
        """As versoes realmente instaladas, para ir junto de qualquer erro."""
        saida = []
        for nome in ("torch", "diffusers", "transformers", "accelerate"):
            try:
                mod = __import__(nome)
                saida.append("%s=%s" % (nome, getattr(mod, "__version__", "?")))
            except Exception as e:
                saida.append("%s=NAO IMPORTA (%s)" % (nome, type(e).__name__))
        return " ".join(saida)

    # docs=False: com True, a Modal publica uma pagina de documentacao
    # aberta no mesmo endereco, dizendo o formato exato do pedido. O
    # endereco e publico e o credito e seu -- nao ha motivo para facilitar.
    @modal.fastapi_endpoint(method="POST", docs=False)
    def editar(self, dados: dict):
        import torch
        from PIL import Image

        esperado = (os.environ.get("PIPI_TOKEN") or "").strip()
        recebido = str(dados.get("token") or "").strip()
        if not esperado:
            return {"ok": False,
                    "erro": "O segredo pipi-token nao foi configurado na Modal."}
        if recebido != esperado:
            return {"ok": False,
                    "erro": ("Token invalido. Recebi %d caracteres e esperava "
                             "%d. Se os numeros batem, o conteiner esta com o "
                             "segredo antigo: rode `modal deploy "
                             "modal_edita.py` e tente em 1 minuto."
                             % (len(recebido), len(esperado)))}

        if self.pipe is None:
            return {"ok": False, "erro": self.erro or "Modelo nao carregado."}

        instrucao = str(dados.get("instrucao") or dados.get("prompt") or "").strip()
        if not instrucao:
            return {"ok": False,
                    "erro": "Diga o que mudar. Ex: 'troque o fundo por um "
                            "estudio branco'."}

        b64 = str(dados.get("imagem_b64") or "").strip()
        if not b64:
            return {"ok": False, "erro": "Falta a imagem a editar (imagem_b64)."}
        try:
            entrada = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        except Exception as e:
            return {"ok": False, "erro": "Nao consegui abrir a imagem: %s" % e}

        # UM TETO NO TAMANHO DE ENTRADA
        #   Foto de celular tem 4000 px de lado. Editar nesse tamanho nao
        #   melhora o resultado e multiplica a memoria de ativacao -- que e
        #   exatamente o que esta apertado aqui.
        maior = max(entrada.size)
        if maior > 1536:
            fator = 1536 / maior
            entrada = entrada.resize(
                (int(entrada.width * fator), int(entrada.height * fator)),
                Image.LANCZOS)

        # Este modelo ACEITA negativa, ao contrario do FLUX schnell: ele usa
        # true_cfg_scale, e com cfg > 1 o "evite X" passa a valer.
        negativo = str(dados.get("negativo") or " ")
        passos = max(8, min(50, int(dados.get("passos") or 30)))
        forca = float(dados.get("forca") or 4.0)
        semente = int(dados.get("semente") or 0)
        gerador = (torch.Generator("cpu").manual_seed(semente)
                   if semente else None)

        try:
            torch.cuda.reset_peak_memory_stats()
        except Exception:
            pass

        comeco = time.time()
        try:
            saida = self.pipe(
                image=entrada,
                prompt=instrucao,
                negative_prompt=negativo,
                num_inference_steps=passos,
                true_cfg_scale=forca,
                generator=gerador,
            ).images[0]
        except Exception as e:
            texto = "%s: %s" % (type(e).__name__, e)
            if "out of memory" in texto.lower():
                return {"ok": False,
                        "erro": ("A %s nao deu conta. Os pesos deste modelo "
                                 "somam ~41 GB em bfloat16. Troque PLACA no "
                                 "modal_edita.py para 'A100-80GB' e rode "
                                 "`modal deploy modal_edita.py`. Detalhe: %s"
                                 % (PLACA, texto[:200]))}
            return {"ok": False, "erro": "Falhou ao editar. %s" % texto[:400]}

        segundos = round(time.time() - comeco, 1)

        # O NUMERO QUE DECIDE A PLACA
        #   Sem isto, escolher entre L40S e H200 seria palpite -- e a
        #   diferenca e 2,3x na conta, todo mes. Aqui ele sai de graca, na
        #   propria resposta, na primeira edicao.
        pico = None
        try:
            pico = round(torch.cuda.max_memory_allocated() / 1024**3, 1)
        except Exception:
            pass

        buf = io.BytesIO()
        saida.save(buf, format="PNG")
        return {
            "ok": True,
            "imagem_b64": base64.b64encode(buf.getvalue()).decode(),
            "formato": "png",
            "largura": saida.width, "altura": saida.height,
            "passos": passos, "semente": semente, "forca": forca,
            "segundos": segundos,
            "custo_usd": round(segundos * PRECO_SEG, 4),
            "placa": PLACA,
            "vram_pico_gb": pico,
            "modelo": MODELO,
            "licenca": "Apache-2.0 (uso comercial liberado)",
        }
