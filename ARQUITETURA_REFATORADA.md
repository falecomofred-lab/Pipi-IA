# Pipi IA — Arquitetura Refatorada (100% Puro)

## O que mudou

**Antes:** `pipi_server.py` — monolítico, difícil de navegar.  
**Depois:** `pipi_server_refatorado.py` — mesmo código, melhor organizado.

### Mudanças

1. **Funções nomeadas claramente**
   - `http_json()` — requisições HTTP
   - `send_json()` — respostas JSON
   - `enviar_arquivo()` — serve arquivos com MIME correto
   - `comfy_status()` — status do ComfyUI
   - `health()` — status de todos os motores

2. **Geração de imagem modularizada**
   - `_modal_job()` — gera via Modal
   - `_comfy_job()` — gera via ComfyUI
   - `_hf_job()` — gera via Hugging Face
   - `run_job()` — orquestra escolha de motor
   - `create_job()` — cria novo job

3. **Seções bem definidas**
   ```python
   # Inicialização
   # Importação de backends opcionais
   # Configuração
   # Utilitários de rede
   # Status de motores
   # Geração de imagem
   # HTTP Handler
   # Main
   ```

## Como usar

### Modo refatorado (recomendado):
```bash
python pipi_server_refatorado.py
```

### Modo original (mantido para compatibilidade):
```bash
python pipi_server.py
```

Ambos funcionam identicamente. Escolha qual preferir.

## APIs (iguais em ambos)

```
GET  /api/health              → Status de todos os motores
GET  /api/logs                → Histórico de jobs
GET  /api/imagens/job/{id}    → Status de um job
GET  /                        → Web UI
GET  /producao/{arquivo}      → Baixar imagem gerada
POST /api/imagens/job         → Criar novo job
```

## Lógica de seleção de motor

Prioridade automática:
1. **Modal** — se configurado (`modal_cliente.configurado()`)
2. **ComfyUI** — se URL configurada
3. **Hugging Face** — se HF_TOKEN configurado

Ou específico via `backend` no payload:
```json
{
  "prompt": "...",
  "backend": "modal"  // força usar Modal
}
```

## Dependências internas (100% PPIA)

- `modal_cliente.py` — integração com Modal
- `huggingface_cliente.py` — integração com HF (opcional)
- `login_venure.py` — autenticação (opcional)
- `motores.json` — catálogo de modelos
- `workflow.json` — workflow do ComfyUI
- `web/` — interface web

## Nada externo

- ✅ Sem Vortex
- ✅ Sem dependências de terceiros (além de stdlib)
- ✅ Código puro Pipi IA
- ✅ Compatível 100% com versão original

## Quando usar qual

| Situação | Use |
|----------|-----|
| Quer código mais legível | `pipi_server_refatorado.py` |
| Quer histórico + commits | `pipi_server.py` (original) |
| Quer estender funcionalidade | `pipi_server_refatorado.py` |
| Debugging | `pipi_server_refatorado.py` (funções nomeadas) |

## Próximas melhorias (só Pipi)

- [ ] Adicionar testes unitários
- [ ] Melhorar logging
- [ ] Cache de jobs em disco
- [ ] Métricas de uso por motor
- [ ] Priorização de fila

Tudo mantendo 100% código Pipi IA.
