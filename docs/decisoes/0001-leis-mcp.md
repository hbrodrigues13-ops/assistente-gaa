# Decisão 0001: leis-mcp para verificação de legislação

Data: 07/11/2026. Aprovada por Henrique Borges Rodrigues.

## Contexto

O princípio 3 exige que todo artigo de lei citado seja conferido antes de entrar na minuta. O leis-mcp 0.2.0 (MIT, github.com/mazulo/leis-mcp) dá acesso ao acervo `ctresb/leis` (cerca de 1,2 milhão de normas em Markdown), com leitura por artigo, parágrafo, inciso e alínea, link oficial (normas.leg.br/LexML) e avisos de revogação.

## Decisão

1. Usar o leis-mcp como **servidor MCP externo**, configurado em `.mcp.json` com versão fixada. Ele não entra como dependência do pacote `assistente`.
2. Na Fase 3, a verificação de citações consulta o leis-mcp por um adaptador em `src/assistente/fontes/`, com versão falsa para testes sem rede (seção 8.6).
3. O resultado do leis-mcp é **triagem**. O texto vem de conversão automática e pode conter erro de OCR; a conferência final é feita no link oficial devolvido em `fonte`.

## Cobertura verificada em 07/11/2026 (índice do commit c9f21b4)

- Coberto: legislação federal, estadual, parte da municipal, reguladores; temas repetitivos do STJ, controle concentrado do STF, súmulas e temas de outros tribunais.
- Não coberto: resoluções do CNJ (ex.: Res. 455/2022, DJEN), normas do município de Marília, acórdãos com relator e data.
- Consequência: feriados e suspensões vêm da tabela versionada do domínio; acórdãos continuam indo para a lista "a verificar".

## Dispositivos já conferidos com ele

- CPC, art. 218, § 3º: 5 dias na falta de prazo legal ou judicial.
- CPC, art. 219: contagem só em dias úteis, apenas para prazos processuais.
- CPC, art. 220: suspensão de 20 de dezembro a 20 de janeiro, inclusive.
- CPC, art. 224, §§ 1º a 3º: exclusão do dia do começo; prorrogação por expediente irregular ou indisponibilidade da comunicação eletrônica; publicação no primeiro dia útil após a disponibilização; início no primeiro dia útil após a publicação.
- Lei 11.419/2006, art. 4º, §§ 3º e 4º: mesma regra para o DJe.
