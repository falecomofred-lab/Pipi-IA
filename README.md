# Pipi IA

**Escreva. Ela desenha.**

Geração de imagem em qualidade comercial a partir de uma frase em
português. Roda no navegador, na sua máquina, e usa uma placa de verdade
só nos segundos em que está desenhando.

Uma peça da plataforma da **Venure** — [venure.com.br](https://venure.com.br)

---

## O que ela faz

| | |
|---|---|
| **Entrada** | Uma frase em português. Escrita ou falada. |
| **Saída** | PNG até 1344 px, nos formatos quadrado, retrato, paisagem, story e capa. |
| **Modelo** | FLUX.1-schnell — licença Apache 2.0, uso comercial liberado. |
| **Placa** | NVIDIA L40S 48 GB, sob demanda, na Modal. |
| **Tempo** | ~1 min a primeira imagem do dia (a placa acorda). Depois, segundos. |

A placa **liga e desliga sozinha**. Não há servidor para manter no ar nem
assinatura mensal de nuvem: paga-se o tempo em que ela desenha.

## O que a torna diferente

**O Bigode escreve o prompt.** Você descreve em português o que quer ver;
o assistente de texto da Venure reescreve em inglês, no formato que o
FLUX entende melhor — e **mostra o resultado, editável**. Em duas semanas
você escreve direto, sem intermediário. Ferramenta que esconde o próprio
funcionamento cria dependência; esta mostra.

**Voz de ponta.** Whisper large-v3. Começa a gravar quando você fala e
**para sozinha quando você cala** — sem clicar em nada.

**Suas imagens ficam com você.** Vão para uma pasta no seu disco, não
para a conta de ninguém.

## Instalação

```bash
git clone https://github.com/falecomofred-lab/Pipi-IA.git
cd Pipi-IA
pip install -r requirements.txt
```

Publique o gerador na sua própria conta da Modal:

```bash
pip install modal
python -m modal setup
python -m modal secret create pipi-token PIPI_TOKEN=<uma-senha-longa>
python -m modal secret create huggingface-token HF_TOKEN=<seu-token-hf>
python -m modal deploy modal_pipi.py
python usar_modal.py          # grava o endereço e confirma que responde
```

Depois, para usar:

```bash
python pipi_server.py         # abre em http://localhost:7300
```

## Segurança

O servidor escuta só em `127.0.0.1`. Nada desta pasta é exposto à rede
sem você pedir (`PIPI_ABRIR_REDE=1`).

Credenciais ficam em `modal.json` e `ponte.txt`, que o `.gitignore`
mantém fora do controle de versão. Elas nunca entram no repositório.

## Direitos

© 2026 Venure. Pipi IA é uma marca da Venure. Todos os direitos
reservados sobre o programa.

**As imagens que você gera são suas** — uso comercial liberado, sem
royalties e sem obrigação de crédito. O FLUX.1-schnell é distribuído sob
Apache 2.0, e é ela que rege a saída do modelo.

---

**Venure** · [venure.com.br](https://venure.com.br) · *Tecnologia que muda vidas*
