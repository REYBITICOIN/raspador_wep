# raspador_wep

Laboratório independente de inteligência web da Toca da Onça.

## Objetivo

Testar, em ambiente isolado:

- Scrapling para coleta de páginas públicas autorizadas;
- ScrapeGraphAI para interpretação e extração estruturada;
- roteamento entre Ollama/Qwen e NVIDIA;
- Grok somente quando houver autorização explícita de custo;
- banco de dados e autenticação em uma instalação Supabase isolada;
- dashboard próprio para criar testes e consultar resultados.

## Limites da fase inicial

- Não integra com TOCA_JARVIS_MASTER.
- Não publica nem executa ações no Facebook ou Instagram.
- Não usa APIs pagas sem autorização.
- Não contorna CAPTCHA, autenticação ou controles de acesso.
- Não armazena tokens, cookies, senhas ou chaves no Git.
- Não será exposto em subdomínio antes dos testes locais e aprovação.

## Arquitetura planejada

- `apps/dashboard`: interface web do laboratório.
- `services/api`: API central.
- `services/scrapling-worker`: coleta.
- `services/scrapegraph-worker`: extração com IA.
- `services/model-router`: seleção de modelos.
- `supabase`: migrações e políticas RLS.
- `tests`: testes unitários, integração, segurança e smoke tests.
- `docs`: arquitetura, decisões e evidências.

## Estado

Repositório inicializado. A implementação será feita em branch de desenvolvimento e validada antes de qualquer instalação na VPS.
