# Decisão 0003: dados-publicos-mcp para investigação do devedor

Data: 07/11/2026. Aprovada por Henrique Borges Rodrigues.

## Contexto

O dados-publicos-mcp 0.1.0 (AGPL-3.0, github.com/Licitei/dados-publicos-mcp) indexa localmente bases públicas e as expõe por MCP. Fontes relevantes para recuperação de crédito:

- `receita-cnpj`: empresas, estabelecimentos, sócios e Simples (IDPJ, art. 133 do CPC; grupo econômico; localização de sócios);
- `pgfn` e `pgfn-nao-previdenciario`: dívida ativa por CNPJ (concorrência de credores, perfil do devedor);
- `querido-diario`: diários oficiais municipais;
- `precedentes`: súmulas, temas e decisões em Markdown;
- `indices-reajuste`: IPCA, INPC, IGP-M e outros do SGS/BCB.

## Decisão

1. Uso como **servidor MCP externo**, instalado na máquina de Henrique (runtime Bun 1.3+). Nenhum código dele é copiado para este repositório, por causa da AGPL.
2. Entra na **Fase 2**, na etapa de contexto e no cruzamento de devedor contumaz.
3. Fontes pesadas (`receita-cnpj`, `pgfn-nao-previdenciario`, `querido-diario`) são indexadas sob demanda.

## Dados pessoais (LGPD)

Dados de acesso público podem ser consultados e mantidos, observados:

- LGPD, art. 7º, § 3º: o tratamento deve considerar a finalidade, a boa-fé e o interesse público que justificaram a disponibilização;
- LGPD, art. 7º, § 7º: o tratamento posterior para nova finalidade exige propósito legítimo e específico;
- LGPD, art. 7º, VI: exercício regular de direitos em processo judicial.

Regra do projeto: o dado guardado fica vinculado ao crédito ou processo que justificou a consulta e é mantido enquanto durar a cobrança e o prazo prescricional correspondente. Não se monta cadastro geral de pessoas sem vínculo com crédito do cliente.
