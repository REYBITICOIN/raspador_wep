# raspador_wep

Laboratório independente de inteligência web da Toca da Onça.

## Objetivo

Commerce OS da Toca da Onça para:

- manter um catálogo central de produtos;
- importar produtos da loja própria;
- preparar, publicar e sincronizar anúncios em marketplaces por APIs oficiais;
- operar Mercado Livre, Shopee, Amazon e Meta por conectores independentes;
- acompanhar preço, estoque, concorrência, tendências e desempenho;
- usar navegador automatizado somente quando uma operação não possuir API adequada.

## Segurança operacional

- Toda publicação passa por prévia, validação e aprovação.
- Segredos e tokens ficam somente no backend.
- CAPTCHA, autenticação e controles de acesso não são contornados.
- APIs pagas exigem autorização explícita.
- O protótipo antigo permanece preservado na branch de arquivo.

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


## Linha de miniagentes

O fluxo usa nove agentes de responsabilidade única: importação, validação comercial,
tratamento de imagens, tabela de medidas, redação, SEO, validação do marketplace,
publicação e sincronização. Cada etapa entrega uma saída explícita para a próxima.

- Imagens são copiadas para um perfil quadrado, sem alterar os arquivos originais.
- Tabelas de medidas só são geradas com valores confirmados.
- NVIDIA ou Grok podem melhorar o texto, mas não podem inventar dados do produto.
- SEOMonster 0.9.3 está instalado como auditor; o OAuth do Google ainda precisa ser autorizado.
- Publicação real permanece bloqueada até OAuth e validação oficial do canal.
