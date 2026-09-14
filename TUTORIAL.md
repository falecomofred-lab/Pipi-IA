# Tutorial — Pipi IA

*Venure · venure.com.br · 14/09/2026*

---

## Parte 0 — O que ela é, e o que ela não é

A Pipi **cria imagens**. Só isso. Ela não conversa, não lê seus arquivos, não pesquisa — isso é o Bigode, que é outro programa.

Os dois não compartilham motor. Um `.gguf` de texto não desenha; um de imagem não conversa. Se você trocar, nada funciona e a mensagem de erro não vai explicar por quê.

### A Pipi é maestro, não desenhista

Ela monta o pedido, escolhe o formato e guarda o resultado. Quem **desenha** é um motor, e ela sabe falar com três:

| motor | endereço | quando usar |
|---|---|---|
| **Modal** | fixo, na nuvem | o melhor — não expira |
| **ComfyUI no Colab** | muda a cada sessão | gratuito |
| **Hugging Face** | API | reserva, só com `HF_TOKEN` |

Se a Modal estiver configurada, ela ganha — e o cabeçalho da tela mostra qual está valendo.

### Por que não roda na sua máquina

O ComfyUI local sobe, mas em **processador**: o PyTorch instalado aí é a compilação `+cpu`, que ignora placa mesmo se houver uma. Gerar um FLUX assim leva dezenas de minutos por imagem. Funciona no papel e não serve na prática.

---

## Parte 1 — Caminho recomendado: Modal

Endereço **fixo**, não expira em 12 horas, não some quando você fecha a aba, e escala a zero entre um pedido e outro.

### Publicar (uma vez só)

Na pasta da Pipi:

```
python -m pip install --upgrade modal
python -m modal setup
python -m modal secret create pipi-token PIPI_TOKEN=escolha-uma-senha-longa
python -m modal deploy modal_pipi.py
```

> **Use `python -m modal`, não `modal`.** O `pip` instala o executável numa pasta que não está no PATH do Windows; o `python -m` chama o módulo direto e funciona sempre.

O `deploy` demora vários minutos na primeira vez — monta a imagem com PyTorch e diffusers. No fim imprime o endereço, terminado em **`-desenhista-gerar.modal.run`**.

> Repare no `desenhista-gerar`. É como você distingue do endpoint de teste antigo, que termina em `gerar-midia` e **não gera imagem nenhuma**.

### Apontar a Pipi

```
python usar_modal.py
```

Cole o endereço e o token. Ele **testa gerando uma imagem de verdade** antes de gravar.

Isso custa alguns segundos de GPU. Vale: um ping não prova nada aqui — o endpoint de teste respondia 200 dizendo *"Processamento simulado com sucesso"* e passaria em qualquer verificação superficial. A única prova que serve é receber pixels.

**A primeira imagem demora muito**: o container frio baixa ~24 GB do FLUX para o Volume. Cinco a dez minutos, e não é travamento. Da segunda vez em diante é rápido.

### Iniciar
```
pipi.bat
```
Abre em `http://localhost:7300`.

### Desligar a Modal
```
python usar_modal.py --remover
```

### Sobre o custo

Você travou o **usage limit em $30**, que é exatamente o crédito mensal do plano Starter. E o **spend limit está em $0**: quando o crédito acabar, tudo para em vez de cobrar.

Uma ressalva que a própria tela da Modal dá: *"Volume storage charges will still accrue"* — o armazenamento dos ~24 GB de pesos passa por fora dessa trava. É pouco, mas não é zero.

---

## Parte 2 — Caminho gratuito: Colab

**1.** Abra o **Pipi IA.ipynb** no Colab.

**2.** *Ambiente de execução → Alterar o tipo → **T4 GPU** → Salvar*

**3.** *Ambiente de execução → **Executar tudo***

| célula | o que faz |
|---|---|
| 1 | monta o Drive e lista os seus modelos |
| 2 | instala o ComfyUI e o leitor de GGUF |
| 3 | liga a sua pasta **IA Imagem** ao ComfyUI |
| 4 | *(opcional)* baixa o FLUX.1-schnell completo |
| 5 | sobe o ComfyUI |
| 6 | **publica e imprime o endereço** |
| 7 | confere o que ele enxerga |
| 8 | desliga |

**4.** Copie o endereço da célula 6.

**5.** No Windows, na pasta da Pipi:
```
python usar_desenhista_do_colab.py
```
Cole. Ele testa e mostra **qual placa respondeu** — se aparecer **Tesla T4**, chegou no lugar certo.

**6.** `pipi.bat`

**Quando o Colab desligar:**
```
python usar_desenhista_do_colab.py --local
```

---

## Parte 3 — Os seus modelos

Ficam em `IA Imagem`, no pendrive espelhado pelo Drive. Hoje:

| arquivo | tipo | licença |
|---|---|---|
| `flux1-schnell-Q4_K_S` | desenha | **Apache 2.0 — comercial liberado** |
| `flux1-dev-Q5_1` | desenha | **não comercial** |
| `qwen-image-edit-2511` | edita imagem | conferir |
| `z_image_turbo_bf16` | desenha | conferir |
| `qwen_3_4b` | texto | conferir |

**Use o schnell para trabalho de cliente.** O `flux1-dev` é licença não comercial — não serve para criativo pago, mesmo que a imagem fique melhor.

### Um FLUX precisa de quatro peças

| peça | o que faz |
|---|---|
| FLUX (UNET) | desenha |
| T5-XXL | lê a frase inteira |
| clip_l | lê palavra por palavra |
| ae (VAE) | transforma o resultado em pixel |

**Com uma faltando não sai imagem nenhuma** — e o erro não diz isso. A célula 7 do notebook pergunta ao ComfyUI quais ele achou e mostra `VAZIO` no que falta.

### Como o ComfyUI enxerga a sua pasta

Ele só olha para a pasta `models` dele mesmo. O `extra_model_paths.yaml` é o que o faz ler a `IA Imagem` direto, **sem copiar**. Copiar gastaria o dobro de espaço e criaria duas verdades: um modelo novo ficaria invisível até alguém lembrar de copiar.

> Ler 12 GB através do Drive montado é lento. Se a primeira imagem demorar demais, prefira o schnell, que fica no disco local do Colab.

---

## Parte 4 — Login

A Pipi usa a **mesma conta do Bigode**. Não há cadastro separado.

Ela lê o `usuarios.json` do Cerebro, sem cópia. Duas listas de conta divergem no primeiro dia em que você troca a senha num lado só — e você descobre quando ficar trancado fora de um dos dois.

**Se o Cerebro não tiver nenhuma conta criada**, o login fica desligado e a tela avisa. Quem cria conta é o Bigode.

**Se a Pipi não achar a pasta do Cerebro**, ela abre sem login em vez de trancar. Aqui não há dado de terceiro e ela escuta só em `127.0.0.1`.

---

## Parte 5 — Quando der errado

**`ModuleNotFoundError: huggingface_cliente`** — resolvido: o import virou opcional. Se voltar, é o `pipi.bat` escolhendo o Python embarcado do pendrive, que não tem pacotes.

**"Nenhum motor conectado"** — nenhum dos três está configurado. Rode `python usar_modal.py` ou `python usar_desenhista_do_colab.py`.

**"Este endereço é o do ENDPOINT DE TESTE"** — você colou o endereço antigo (`gerar-midia`). Use o que termina em `desenhista-gerar`.

**A imagem sai como texto, sem aparecer** — resolvido: o servidor mandava o caminho de disco (`G:\...`), que o navegador não abre. Agora manda `/producao/arquivo.png`.

**A tela aparece sem estilo** — resolvido: tudo era servido como `application/octet-stream`, e o navegador **ignora um `.css` que chega assim, em silêncio**.

**O ComfyUI local não responde** — ele demora mais que os 120 segundos que o `pipi.bat` espera, porque sobe em CPU. Com a Modal configurada isso deixa de importar.

---

## Parte 6 — Uma coisa para levar a sério

**O ComfyUI não tem senha. Nenhuma.**

Enquanto o túnel do Colab estiver de pé, quem tiver o endereço manda desenhar na sua placa e vê as imagens que você gerou. O endereço é sorteado, mas isso é obscuridade, não proteção.

Não cole em grupo. Rode a célula 8 ao terminar.

A Modal é diferente: o endpoint exige token, e sem ele responde `401`.

**Nunca publique o `modal.json`.** Ele guarda o token do seu endpoint — com ele na mão, qualquer um desenha na sua conta até o crédito acabar. O `.gitignore` já o barra.

---

## Resumo de uma página

**Modal (recomendado):** `python -m modal deploy modal_pipi.py` → `python usar_modal.py` → `pipi.bat`

**Colab (gratuito):** notebook → T4 → Executar tudo → copia o endereço da célula 6 → `python usar_desenhista_do_colab.py` → `pipi.bat`

**Voltar ao normal:** `python usar_modal.py --remover` ou `python usar_desenhista_do_colab.py --local`

**Para trabalho de cliente:** use o **schnell**, não o `flux1-dev`.
