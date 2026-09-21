# Tutorial — Pipi IA

*Venure · venure.com.br · 17/09/2026*

---

## Parte 0 — O que ela é

A Pipi **cria imagens**. Só isso. Ela não conversa, não lê seus arquivos, não pesquisa — isso é o Bigode, que é outro programa.

**Ela é maestro, não desenhista.** Monta o pedido, guarda o resultado, mostra na tela. Quem desenha é uma **NVIDIA L40S na Modal**, rodando **FLUX.1-schnell**.

Um motor só, de propósito. Havia três aqui (ComfyUI, Hugging Face, Modal) e dois nunca desenharam nada nesta máquina. Três caminhos são três jeitos de falhar.

---

## Parte 1 — Abrir

```
pipi.bat
```

Abre em `http://127.0.0.1:7300`. Login: **a mesma conta do Bigode**.

O painel no topo da tela diz o que está valendo: ferramenta, placa, modelo, licença, crédito restante e o que acontece sozinho.

**Para fechar:** Ctrl+C na janela preta. Não há nada para desligar na Modal — a placa dorme sozinha 2 minutos depois da última imagem.

---

## Parte 2 — Primeira instalação

### a) Aceitar a licença do FLUX

O FLUX.1-schnell é Apache 2.0 — comercial liberado — **mas o repositório é gated**: exige aceitar um formulário antes de baixar. Sem isso, a Modal leva **401** e o container morre no arranque, repetidamente.

1. Abra <https://huggingface.co/black-forest-labs/FLUX.1-schnell>, logado, e aceite.
2. Crie um token de leitura em <https://huggingface.co/settings/tokens>.

### b) Instalar e publicar

```
python -m pip install -r requirements.txt
python -m modal setup
```

```
python -m modal secret create pipi-token PIPI_TOKEN=uma-senha-longa --force
python -m modal secret create huggingface-token HF_TOKEN=hf_o_seu_token --force
python -m modal deploy modal_pipi.py
```

> **Use `python -m modal`, não `modal`.** O `pip` instala o executável numa pasta fora do PATH do Windows.
>
> **E use `--force`, nunca `secret delete`.** Apagar um segredo que o app está usando põe o app em crash-loop até o próximo deploy — isso já consumiu crédito de madrugada aqui.

O `deploy` demora na primeira vez: monta a imagem com PyTorch e diffusers. No fim imprime o endereço, terminado em **`-desenhista-gerar.modal.run`**.

### c) Apontar a Pipi

```
python usar_modal.py
```

Cole o endereço e o token. Ele **testa gerando uma imagem de verdade** antes de gravar.

Um ping não bastaria: o roteador da Modal responde 200 mesmo com o container morto por baixo. Foi assim que a Pipi ficou um dia publicada, com endereço vivo, sem gerar nada.

**A primeira imagem leva de 5 a 10 minutos, calada** — o container baixa ~24 GB do FLUX para o Volume. **Não aperte Ctrl+C.** Da segunda vez em diante são segundos.

---

## Parte 3 — O custo

| | |
|---|---|
| Placa | NVIDIA L40S, $0,000542/s |
| Por imagem | ~4 s quente ≈ **US$ 0,002** |
| Teto do mês | **US$ 30** (crédito do plano Starter) |
| Spend limit | **US$ 0** — quando o crédito acaba, tudo para em vez de cobrar |

O painel da tela mostra o gasto do ciclo e o restante, consultando a própria Modal.

**Por que L40S e não L4, que é mais barata:** o transformer do FLUX tem 12 bilhões de parâmetros — em bfloat16 são ~24 GB só para ele. A L4 entrega 22,03 GiB utilizáveis: não cabe. Na L4, a única forma de caber seria fatiar por submódulo, o que leva ~2 minutos por imagem — **US$ 0,027**, mais caro que a L40S. Placa mais barata que não cabe não é economia.

**Uma ressalva:** o armazenamento do Volume (~24 GB de pesos) é cobrado por fora do teto, mesmo com o spend limit em zero. São centavos, mas não é zero.

**Não há motor de reserva.** Quando o crédito acabar, a Pipi para e a tela diz isso. Foi escolha sua, não esquecimento.

---

## Parte 4 — Quando der errado

**"A Modal não está configurada"** — rode `python usar_modal.py`.

**"Token invalido. Recebi N caracteres e esperava M"** — se os números batem, o contêiner ainda está com o segredo antigo: rode `modal deploy modal_pipi.py` e espere 1 minuto. Se não batem, foi o que você digitou.

**"O Hugging Face recusou o download (401, repositório gated)"** — a licença não está aceita nessa conta, ou o `huggingface-token` tem valor errado. Parte 2a.

**"A placa não tem memória para este modelo"** — o `gpu=` do `modal_pipi.py` saiu de `L40S`.

**O pedido fica parado e nunca volta** — era o crash-loop, quando o container morria e a Modal subia outro. Resolvido: o carregamento agora **responde o motivo** em vez de derrubar o container.

**Como olhar por dentro** — <https://modal.com/apps> → `pipi-ia` → **Logs**. A aba **Functions** mostra containers vivos e chamadas penduradas.

---

## Parte 5 — Manutenção

```
powershell -ExecutionPolicy Bypass -File .\LIMPAR_PIPI.ps1 -Ensaio
```

Mostra o que sairia da pasta. Sem `-Ensaio`, move para uma quarentena **ao lado** do projeto, com um LEIA-ME do que era cada arquivo. Nada é apagado.

---

## Parte 6 — Uma coisa para levar a sério

**Nunca publique o `modal.json`.** Ele guarda o token do seu endpoint — com ele na mão, qualquer um desenha na sua conta até o crédito acabar. O `.gitignore` já o barra.

E **não cole token em conversa nenhuma**, nem em chat com assistente. Token que aparece em texto está queimado; gere outro.

---

## Resumo de uma página

**Usar:** `pipi.bat` → login do Bigode → escreve → Criar imagem

**Instalar:** aceitar licença do FLUX → `modal setup` → dois `secret create --force` → `modal deploy modal_pipi.py` → `usar_modal.py`

**Trocar o token:** `modal secret create pipi-token PIPI_TOKEN=novo --force` → `modal deploy modal_pipi.py` → `usar_modal.py`

**As imagens são Apache 2.0** — uso comercial liberado, sem ressalva.
