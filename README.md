# CommerceHub V2 ML PRO — Functional Fix

Correção das rotas ausentes para iniciar o fluxo de venda no Mercado Livre.

## Adicionado/corrigido

- `/setup`
- `/new-product`
- `/sell-flow`
- `/api/foundation/status`
- `/api/setup/check`
- `/api/routes`

## Testes

- `/api/health` deve retornar `v2-ml-pro-functional-fix`
- `/setup`
- `/new-product`
- `/sell-flow`
- `/api/routes`
- `/products`
- `/mercado-livre`

Se o `/api/health` ainda mostrar `enterprise-backend-reviewed-stable`, a Vercel não recebeu esta versão ou você subiu no projeto/domínio errado.
