# Toca Commerce Intelligence — Extensão Chrome

## Instalação local para teste

1. Abra `chrome://extensions`.
2. Ative **Modo do desenvolvedor**.
3. Clique em **Carregar sem compactação**.
4. Selecione `G:\TOCA_COMMERCE_OS\apps\browser-extension`.
5. Abra uma página de produto compatível e recarregue a página.

## Comportamento seguro

- Lê apenas a página aberta pelo usuário.
- Não contorna login, CAPTCHA ou bloqueios.
- Marca estoque e vendas como não confirmados quando não existe evidência.
- Salva capturas no backend local somente quando o usuário clica no botão.
- Nenhuma credencial de marketplace fica dentro da extensão.

## Contas do Chrome

Repita a instalação em cada perfil. Para distribuição permanente nas cinco contas,
o próximo passo é empacotar e publicar na Chrome Web Store ou usar uma política
administrativa de instalação.
