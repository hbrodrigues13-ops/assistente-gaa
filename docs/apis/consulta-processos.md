# Consulta de processos: DJEN, DataJud, Anthropic e dados-publicos-mcp

Referência consolidada das quatro fontes que o Fluxo 1 usa para acompanhar processos. Levantada em 12/11/2026.

Legenda de confiabilidade:
- **conferido:** lido no código-fonte ou na documentação oficial;
- **por terceiros:** descrito por guias e clientes de código aberto, ainda não testado contra a API real;
- **a testar:** precisa ser confirmado na primeira chamada real.

## 1. Visão geral

| Fonte | Para quê | Chave | Etapa do Fluxo 1 |
|---|---|---|---|
| DJEN (Comunica PJe) | publicações e intimações por OAB | não exige | 1. Coleta |
| DataJud (CNJ) | metadados e andamentos por número de processo | chave pública do CNJ | 4. Contexto e modo sombra |
| Anthropic (Claude) | classificar a publicação e redigir | `ANTHROPIC_API_KEY` | 2. Classificação; 5 e 6. Estratégia e minuta |
| dados-publicos-mcp | investigação do devedor (CNPJ, sócios, dívida ativa) | não exige | 4. Contexto (devedor contumaz) |

Sequência diária:

```
DJEN (por OAB, por data)
  -> deduplica pelo id da comunicação (princípio 5)
  -> valida o número CNJ (dominio/numero_cnj.py)
  -> calcula o prazo (dominio/prazos.py, código determinístico)
  -> Claude classifica classe, polo e ato (modelo leve, saída validada por pydantic)
  -> DataJud confirma andamentos do processo
  -> dados-publicos-mcp levanta dados do devedor, quando for o caso
  -> Henrique aprova; só então a tarefa vai ao Legal One (princípio 2)
```

## 2. DJEN: comunicações processuais

### Acesso

| Item | Valor | Confiabilidade |
|---|---|---|
| Produção | `https://comunicaapi.pje.jus.br/api/v1/comunicacao` | por terceiros |
| Homologação | `https://hcomunicaapi.cnj.jus.br/api/v1` (o CNJ cita esse host; guias citam outro) | por terceiros |
| Método | `GET` com parâmetros na URL | por terceiros |
| Autenticação | não exige para consulta | por terceiros |

### Parâmetros

| Parâmetro | Uso | Observação |
|---|---|---|
| `numeroOab` | número da OAB | comparação exata de texto; incluir a letra, se a inscrição tiver |
| `ufOab` | UF da OAB | obrigatório junto com `numeroOab` |
| `dataDisponibilizacaoInicio` | início do período | data de **disponibilização**, não de publicação |
| `dataDisponibilizacaoFim` | fim do período | idem |
| `numeroProcesso` | filtra um processo | a testar |
| `siglaTribunal` | filtra o tribunal (ex.: `TJSP`) | a testar |
| `pagina` | página | |
| `itensPorPagina` | tamanho da página | só aceita 5 ou 100 |

Limites relatados: no máximo 10.000 resultados por pesquisa; em resposta 429, aguardar 1 minuto antes de tentar de novo. Não rodar consultas em paralelo nem trocar de IP para contornar limite.

### OABs monitoradas (CLAUDE.md, seção 5)

| Advogado | `numeroOab` | `ufOab` |
|---|---|---|
| Henrique Borges Rodrigues | `509289` | `SP` |
| Alex Sandro Gomes Altimari | `177936` | `SP` |

### Exemplo (httpx)

```python
import httpx

URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"

def buscar_comunicacoes(oab: str, uf: str, inicio: str, fim: str, pagina: int = 1) -> dict:
    params = {
        "numeroOab": oab,
        "ufOab": uf,
        "dataDisponibilizacaoInicio": inicio,  # AAAA-MM-DD
        "dataDisponibilizacaoFim": fim,
        "pagina": pagina,
        "itensPorPagina": 100,
    }
    resposta = httpx.get(URL, params=params, timeout=30)
    resposta.raise_for_status()
    return resposta.json()
```

### O que guardar de cada comunicação

A estrutura da resposta ainda **não foi conferida** contra a API real. Na primeira chamada, registrar os nomes exatos dos campos e fixar um modelo pydantic. O mínimo a guardar:

- identificador da comunicação: chave de idempotência (princípio 5);
- data de disponibilização: entrada de `calcular_prazo`;
- número do processo: entra em `interpretar_numero_cnj`, que dá o foro e a comarca;
- sigla do tribunal, órgão julgador e tipo de comunicação;
- texto integral e link;
- destinatários e advogados intimados: confirmam se a OAB é do GAA.

### Regras do projeto

- O prazo é sempre calculado pelo `dominio/prazos.py`, nunca pela data que a API ou o modelo informarem.
- Publicação repetida (mesmo identificador): registrar e ignorar.
- Falha da API: nova tentativa com espera e, persistindo, alerta a Henrique (CLAUDE.md, seção 8.7).

## 3. DataJud: andamentos por número de processo

### Acesso (conferido no código do pydatajud)

| Item | Valor |
|---|---|
| Endpoint | `https://api-publica.datajud.cnj.jus.br/api_publica_<tribunal>/_search` (TJSP: `api_publica_tjsp`) |
| Método | `POST`, corpo em JSON no formato de busca do Elasticsearch |
| Cabeçalho | `Authorization: APIKey <chave>` |
| Chave | pública, publicada pelo CNJ em https://datajud-wiki.cnj.jus.br/api-publica/acesso/ e trocada sem aviso |

A chave vai no `.env` (`DATAJUD_API_KEY`), nunca no código. Resposta 401 ou 403 indica chave trocada: o adaptador deve alertar.

### Consultas úteis

Um processo:

```json
{"size": 10, "query": {"match": {"numeroProcesso": "12345672320258260344"}}}
```

O número vai só com dígitos (20 dígitos), como devolve `NumeroCnj.digitos`.

Vários processos que tiveram andamento depois de uma data (com o pydatajud, decisão 0002):

```python
from pydatajud import DataJudClient

cliente = DataJudClient(api_key=chave)
cortes = {
    "1234567-23.2025.8.26.0344": "2026-11-01T00:00:00.000Z",
}
situacao = cliente.search_movements_delta_batch(cortes, mode="status")
for numero, s in situacao.items():
    if s.has_new_movements:
        ...  # processo andou: buscar detalhes
```

A biblioteca agrupa os processos por tribunal e faz uma requisição por tribunal. `mode="movements"` devolve também as movimentações novas.

### Limites

- Os movimentos do DataJud podem vir resumidos e com atraso em relação ao tribunal. Servem para detectar andamento, não substituem a leitura dos autos nem a publicação.
- Limite de requisições: não documentado nas fontes lidas; conferir na wiki do CNJ.

## 4. Anthropic (Claude): classificação e redação

### Modelos (conferido na referência da API em 12/11/2026)

| Uso no projeto | Modelo | ID | Preço por milhão de tokens (entrada / saída) |
|---|---|---|---|
| Classificar publicação, extrair dados | Claude Haiku 5.5 | `claude-haiku-5-5` | US$ 0,10 / 0,50 (até 100 mil tokens de entrada) |
| Estratégia e minuta | Claude Opus 5.5 | `claude-opus-5-5` | US$ 4 / 20 |

O CLAUDE.md (seção 3) manda usar o modelo leve onde ele resolve. Se a classificação com Haiku errar na base de teste, sobe para `claude-sonnet-5-5` (US$ 2 / 10) antes de ir ao Opus.

### Classificação com saída validada (pydantic)

```python
from enum import StrEnum

import anthropic
from pydantic import BaseModel


class Polo(StrEnum):
    CREDOR = "credor"
    DEVEDOR = "devedor"
    INDEFINIDO = "indefinido"


class Classificacao(BaseModel):
    classe: str          # execução, cumprimento de sentença, monitória...
    polo_cliente: Polo
    ato: str             # citação negativa, bloqueio infrutífero, embargos...
    prazo_legal_dias: int | None   # sugestão; a contagem é sempre do domínio
    justificativa: str


cliente = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente

resposta = cliente.messages.parse(
    model="claude-haiku-5-5",
    max_tokens=2048,
    output_config={"effort": "low"},
    system=[{"type": "text", "text": INSTRUCOES_FIXAS, "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": texto_da_publicacao}],
    output_format=Classificacao,
)
if resposta.stop_reason == "refusal":
    ...  # registrar e mandar para revisão manual
classificacao = resposta.parsed_output
```

Pontos de atenção:
- `messages.parse(..., output_format=Modelo)` devolve `parsed_output` já validado.
- Sempre conferir `stop_reason` antes de ler o resultado. `refusal` vai para revisão manual.
- No Opus 5.5 e no Haiku 5.5 o esforço padrão é `medium`. Para classificação, `low`; para estratégia, `high`.
- Nos modelos atuais não se usa `budget_tokens` nem "prefill" da resposta: os dois dão erro 400.
- Para a estratégia com Opus 5.5, ligar o recurso de fallback em caso de recusa: `betas=["server-side-fallback-2026-07-01"]` com `fallbacks="default"`.

### Economia

- **Cache de prompt:** as instruções fixas (taxonomia de atos, regras do GAA) ficam no `system` com `cache_control`. A parte variável (a publicação) fica no fim. O cache só funciona a partir de um tamanho mínimo de prompt, que varia de 512 a 4.096 tokens conforme o modelo.
- **Lote (Message Batches):** a coleta diária não é urgente. Enviar as publicações do dia em lote custa 50% menos. Os resultados chegam fora de ordem: amarrar cada um pelo `custom_id`, usando o identificador da comunicação do DJEN.

### Dados e sigilo (princípio 8)

- Mandar ao modelo só o texto da publicação e o necessário para classificar. CPF, endereço e valores só quando a etapa precisar.
- Logs não guardam a resposta inteira: guardar a classificação e o `_request_id`.

## 5. dados-publicos-mcp: investigação do devedor

Servidor MCP externo, instalado no computador de Henrique (Bun 1.3+), decisão 0003. Licença AGPL: usar como servidor separado, sem copiar código.

### Ferramentas (conferido no código-fonte)

| Ferramenta | Para quê |
|---|---|
| `fontes` | lista as fontes, tabelas e colunas disponíveis |
| `buscar` | busca textual em qualquer tabela; tolera erro de digitação |
| `consultar_sql` | uma consulta `SELECT` ou `WITH`, só leitura, até 1.000 linhas, 5 segundos |
| `indexar` | baixa e indexa uma fonte leve |
| `acervo_buscar`, `acervo_localizar`, `acervo_ler` | leis e precedentes em Markdown (inclui súmulas e IRDRs do TJSP) |
| `guia` | instruções de uso |

### Fontes para recuperação de crédito

| Fonte | Tabelas | Uso | Peso |
|---|---|---|---|
| `receita-cnpj` | `empresa`, `estabelecimento`, `socio`, `simples` | quadro societário, endereços, grupo econômico, IDPJ | pesada |
| `pgfn` | `pgfn_divida` | dívida ativa previdenciária e FGTS por CNPJ | leve |
| `pgfn-nao-previdenciario` | `pgfn_divida_nao_previdenciaria` | demais débitos inscritos | pesada |
| `querido-diario` | diários oficiais municipais | editais, leilões, outras execuções | pesada |
| `precedentes` | acervo Licitei/precedentes | súmulas e teses para a verificação de citações | leve |

As fontes pesadas são indexadas pela linha de comando:

```bash
bun src/index.ts index receita-cnpj
```

### Regra de uso (LGPD, decisão 0003)

O dado de pessoa só é consultado e guardado vinculado ao crédito ou processo que motivou a busca, enquanto durar a cobrança e o prazo prescricional. Não se monta cadastro geral de pessoas.

## 6. Configuração

Variáveis no `.env` (nunca no Git):

```
ANTHROPIC_API_KEY=
DATAJUD_API_KEY=
DJEN_OABS=509289/SP,177936/SP
```

Rede: a sessão de desenvolvimento na nuvem bloqueia hosts que não estejam liberados. Antes da primeira chamada real será preciso liberar `comunicaapi.pje.jus.br` e `api-publica.datajud.cnj.jus.br`. No computador de Henrique não há esse bloqueio.

## 7. Pendências

1. Testar a API do DJEN com a OAB 509.289/SP e fixar os nomes dos campos da resposta.
2. Conferir na wiki do CNJ a chave vigente e os limites do DataJud.
3. Montar a base de teste da classificação com publicações reais anonimizadas antes de escolher o modelo em definitivo.

## Fontes

- DJEN: [Portal CNJ, Comunicações Processuais](https://www.cnj.jus.br/programas-e-acoes/processo-judicial-eletronico-pje/comunicacoes-processuais/); [Orientações aos Tribunais](https://www.cnj.jus.br/programas-e-acoes/processo-judicial-eletronico-pje/comunicacoes-processuais/orientacoes-aos-tribunais/); [cliente vbarcelosbt/API_DJEN](https://github.com/vbarcelosbt/API_DJEN); [haderalva/consulta-pje](https://github.com/haderalva/consulta-pje); [Transitado, publicações no DJEN](https://transitado.com.br/artigos/publicacoes-djen); [Chat Jurídico, API do DJEN](https://chatjuridico.com.br/api-do-djen-consulta-oficial-cnj/)
- DataJud: código do pydatajud 0.2.0 (github.com/Filipe-Araujo0/pydatajud); [wiki do DataJud](https://datajud-wiki.cnj.jus.br/api-publica/acesso/)
- Anthropic: referência da API e do SDK Python, consultada em 12/11/2026
- dados-publicos-mcp: código-fonte 0.1.0 (github.com/Licitei/dados-publicos-mcp)
