# Pipi IA

Aplicação independente de criação de imagens da Venure. A Pipi tem o mesmo princípio operacional do Bigode IA: uma interface simples coordena recursos sob demanda, mostra o estado do motor e acompanha operações longas sem travar a tela.

## O que a Pipi coordena

- Seleção manual ou automática do motor de imagem.
- Estado dos componentes disponíveis.
- Prompt positivo, prompt negativo, formato, passos, guidance e semente.
- Jobs assíncronos com acompanhamento de fila, geração, conclusão e erro.
- Histórico local das criações da sessão.
- Área de motores, ajustes e nova criação.
- Destino de produção em `Pipi IA/produção`.
- Uso em celular como aplicação instalável.

## Estrutura

- `web/index.html`: aplicação visual independente no padrão maestro do Bigode.
- `web/img/pipi_gata_transparente.png`: mascote transparente e realçada.
- `web/img/pipi_gata.jpeg`: original fornecida.
- `manifest.json`: instalação como app no celular.

## Execução

Sirva a pasta `web` por HTTP no mesmo host do backend do Cerebro. A URL da API pode ser definida no menu **Ajustes** ou pela variável `window.PIPI_API_BASE`; vazia significa mesma origem.

Exemplo: `python -m http.server 7300 --directory web`. Em produção, use proxy reverso para encaminhar `/api` ao servidor do Bigode.

Endpoints usados:

- `GET /api/imagens`
- `POST /api/imagens/job`
- `GET /api/imagens/job/{id}`

A separação é de frontend e experiência, enquanto o backend de geração continua compartilhado para evitar duplicação de ComfyUI, modelos, VRAM e regras de segurança. A evolução futura pode criar um serviço de imagem próprio, desde que preserve autenticação, autorização, armazenamento e limite de jobs.
