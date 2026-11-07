# Decisão 0004: base jurídica da Advocacia Aberta para verificar jurisprudência

Data: 07/11/2026. Aprovada por Henrique Borges Rodrigues.

## Contexto

O leis-mcp (decisão 0001) não traz acórdãos com relator e data. A Advocacia Aberta (MIT, github.com/emidio-trancoso/advocacia-aberta) traz, em JSON estruturado (`ferramentas/pesquisa/vade-mecum/data/`, cerca de 98 MB):

- súmulas do STJ (676, com situação ativa ou cancelada, órgão e data) e do STF, inclusive vinculantes;
- 1.474 temas repetitivos do STJ, com questão, tese firmada, processo paradigma, relator, data de julgamento e link oficial;
- 1.470 temas de repercussão geral do STF;
- 3.508 teses da Jurisprudência em Teses do STJ;
- 12.156 espelhos de acórdãos da Corte Especial e das Seções do STJ, com relator, data de publicação, ementa e link;
- legislação em JSON, inclusive Decreto-Lei 911/1969 e Lei 10.931/2004.

## Decisão

1. Na Fase 3, a verificação de citações consulta esses JSONs para súmula, tema e acórdão do STJ e do STF: confere número, órgão, relator, data e trecho, de forma determinística.
2. Os dados não entram no Git. Um script baixa a versão fixada por commit para a pasta de dados local, com hash conferido.
3. Continua valendo o princípio 3: a base é triagem; a conferência final é no link oficial.

## Limites

- Acórdãos de Turmas do STJ e do TJSP não estão cobertos. Esses continuam na lista "a verificar".
- A busca no TJPR e o exemplo penal do projeto não se aplicam ao GAA.
- Os protocolos de redação e revisão servem de referência, mas as skills do GAA prevalecem.
