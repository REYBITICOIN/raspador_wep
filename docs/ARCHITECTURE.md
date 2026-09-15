# Arquitetura do laboratório

O projeto é independente do Jarvis e não executa ações em redes sociais.

## Fluxo

1. O usuário autentica pelo Supabase Auth.
2. O dashboard envia uma URL pública e uma instrução para a API.
3. A API valida destino, permissão e orçamento.
4. Scrapling coleta a página em worker isolado.
5. ScrapeGraphAI transforma o conteúdo em JSON.
6. O Model Router escolhe Ollama/NVIDIA; Grok só é permitido quando `ALLOW_PAID_MODELS=true`.
7. Resultado e métricas são salvos no PostgreSQL com RLS.

## Segredos

NVIDIA, xAI/Grok e a chave secreta Supabase existem apenas no ambiente do backend. O dashboard recebe somente configuração pública e estados booleanos de conexão.

## Situação da versão 0.1

O dashboard, API de controle e esquema inicial do banco estão presentes. Os workers Scrapling e ScrapeGraphAI ainda serão conectados; o endpoint de criação apenas enfileira de forma simulada e não coleta páginas.

