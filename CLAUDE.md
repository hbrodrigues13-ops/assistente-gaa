# CLAUDE.md: Assistente GAA

Leia este arquivo inteiro antes de qualquer tarefa neste repositório. Ele é a fonte de verdade do projeto. Em conflito entre este arquivo e um pedido pontual, pergunte antes de agir.

## 1. O que é o projeto

Assistente jurídico pessoal de Henrique Borges Rodrigues (OAB/SP 509.289), advogado do Gomes Altimari Advogados (GAA), Marília/SP. O objetivo é um sistema robusto que lê publicações, entende o processo, propõe estratégia, redige a minuta no padrão do escritório e lança o prazo no Legal One, sempre com aprovação humana antes de qualquer ação externa.

Foco: **recuperação de crédito em geral**, em todo o ciclo do crédito inadimplido:
- pré-judicial: notificação, protesto, negativação e acordo;
- judicial: execução de título extrajudicial, cumprimento de sentença, ação monitória (CPC, art. 700), busca e apreensão (Decreto-Lei 911/1969) e cobrança;
- constrição: SISBAJUD, RENAJUD, INFOJUD, CNIB, penhora, IDPJ e fraude à execução;
- expropriação e satisfação: adjudicação, alienação, leilão judicial, levantamento e acordo.

O agronegócio (CPR, cédulas rurais, notas de leilão de gado) é uma especialidade dentro do foco, não um limite. Credores típicos: empresas, fintechs e SCDs, securitizadoras, locadoras de equipamentos, cooperativas, leiloeiros e pessoas físicas. Não é contencioso de massa: a vantagem está na profundidade da estratégia e nos dados de recuperação.

O desenvolvimento é feito por fluxos verticais completos. Só se abre o fluxo seguinte quando o anterior atinge as metas da seção 7.

## 2. Princípios inegociáveis

1. **Prazo é código determinístico, nunca saída de modelo.** O modelo de linguagem apenas classifica o ato processual e sugere o prazo legal aplicável. A contagem (dias úteis, feriados, suspensões) é feita por funções Python puras, cobertas por testes. Na dúvida entre duas datas, use sempre a mais conservadora (prazo menor) e sinalize a divergência.
2. **Nenhuma ação externa sem aprovação de Henrique.** Lançar tarefa no Legal One, enviar mensagem, enviar e-mail ou protocolar exigem aprovação explícita registrada. O sistema prepara; o humano decide.
3. **Nenhuma citação sem verificação.** Artigo de lei, súmula, tema ou julgado só entra na minuta depois de conferido na fonte oficial (número, órgão, relator, data e trecho). Julgado não verificado fica fora da peça e vai para a lista "a verificar".
4. **Todo fato aponta para a prova.** Cada afirmação de fato da minuta registra a origem (documento, Id. dos autos, página).
5. **Idempotência.** A chave de cada publicação é o identificador da comunicação no DJEN. Reprocessar nunca pode duplicar tarefa, minuta ou mensagem.
6. **Modo sombra antes de modo ativo.** Todo fluxo novo roda primeiro em paralelo ao trabalho manual, sem lançar nada, apenas comparando resultados. A promoção para ativo é decisão de Henrique.
7. **Segredos fora do código.** Chaves e senhas ficam em `.env` (fora do Git) ou no Cofre de Credenciais do Windows via `keyring`. A chave `service_role` do Supabase nunca vai para frontend, log ou commit.
8. **Minimização de dados (LGPD e sigilo profissional).** Envie ao modelo só o necessário para a etapa. Logs não guardam conteúdo integral de peças nem dados pessoais desnecessários. Toda tabela do Supabase com RLS ativo.
9. **Ferramenta do advogado, nunca advocacia sem advogado.** O sistema apoia o advogado; a decisão jurídica, a estratégia final e a assinatura são sempre de advogado inscrito na OAB (Recomendação CFOAB 001/2024). Nenhuma funcionalidade pode entregar peça ou estratégia diretamente a cliente ou empresa sem passar por advogado.
10. **Registro de supervisão.** Toda minuta guarda trilha auditável: versão gerada, quem revisou, o que foi alterado, quem aprovou, data e hora. Sem esse registro, a minuta não pode ser marcada como aprovada.

## 3. Stack

- Python 3.12, gerenciado com `uv` (`uv add`, `uv run`). Não usar pip direto.
- Agente: `claude-agent-sdk` (Python). Em desenvolvimento, as etapas também existem como skills em `.claude/skills/`.
- Modelos por custo: classificação e extração com modelo leve; estratégia e redação com modelo forte. Nunca usar o modelo forte onde o leve resolve.
- HTTP: `httpx`. Validação de dados: `pydantic`.
- Documentos: `pdfplumber` (leitura de autos), `python-docx` (minutas a partir do .docx-modelo do GAA).
- Automação de sistemas sem API (Legal One, e-SAJ): `playwright`, isolada em adaptadores.
- Banco: Supabase (Postgres + pgvector).
- Legislação: leis-mcp como servidor MCP externo (`.mcp.json`), só para triagem; conferência final no link oficial (docs/decisoes/0001-leis-mcp.md).
- Qualidade: `pytest`, `ruff` (lint e formatação), `mypy` nos módulos de domínio.
- Agendamento local: `apscheduler`. Canal de mensagens: WhatsApp Business Platform (API oficial), em fase posterior.

## 4. Estrutura do repositório

```
assistente-gaa/
├── CLAUDE.md
├── .env.example            # nomes das variáveis, sem valores
├── pyproject.toml
├── docs/                   # especificações detalhadas (fluxos, decisões)
│   └── playbooks/          # estratégia por tipo de crédito, escrita por Henrique
├── src/assistente/
│   ├── dominio/            # regras puras, sem I/O: prazos, calendário, classificação de atos
│   ├── fontes/             # DJEN, DataJud, tribunais, pasta GAA (somente leitura)
│   ├── adaptadores/        # Legal One, Supabase, WhatsApp (I/O isolado e substituível)
│   ├── agentes/            # orquestração com o Agent SDK, prompts versionados
│   ├── pecas/              # montagem de minutas no .docx-modelo
│   └── fluxos/             # fluxos ponta a ponta (fluxo_01_execucao.py ...)
├── tests/
│   ├── dominio/            # testes de prazo e calendário (cobertura máxima)
│   └── casos/              # base de casos reais anonimizados para avaliação
└── .claude/skills/         # skills das etapas
```

Regra de dependência: `dominio` não importa nada de `fontes`, `adaptadores` ou `agentes`. Identificadores em português sem acento (ex.: `calcular_prazo`, `Publicacao`).

## 5. Fluxo 1: publicação em execução até prazo no Legal One

**OABs monitoradas:** 509.289/SP (Henrique) e 177.936/SP (Dr. Alex Sandro Gomes Altimari).
**Escopo de minuta:** apenas processos em que Henrique é responsável na pasta do Legal One. Nos demais, o sistema só gera alerta com o responsável da pasta.

### 5.1 Etapas

Escopo do Fluxo 1: qualquer processo de recuperação de crédito (execução, cumprimento de sentença, monitória, busca e apreensão, cobrança) em que o cliente do GAA seja o credor.

1. **Coleta:** consulta diária à API de comunicações do DJEN por OAB. Persistir a publicação bruta. Deduplicar pelo identificador da comunicação. Publicação repetida: registrar e ignorar.
2. **Classificação:** identificar a classe (execução, cumprimento de sentença, monitória, busca e apreensão, cobrança), o polo do cliente (credor ou devedor; se devedor, apenas alerta) e o ato (citação negativa, bloqueio infrutífero, intimação para andamento, embargos, impugnação, sentença, outro). Saída estruturada e validada por `pydantic`.
3. **Prazo (código determinístico):**
   - Contagem em dias úteis (CPC, art. 219).
   - Publicação no DJEN: considera-se publicada no primeiro dia útil seguinte à disponibilização; o prazo começa no primeiro dia útil seguinte à publicação (CPC, art. 224, §§ 2º e 3º; Lei 11.419/2006, art. 4º, §§ 3º e 4º). Dia do começo ou do vencimento com expediente irregular ou indisponibilidade da comunicação eletrônica é prorrogado para o primeiro dia útil seguinte (CPC, art. 224, § 1º). Pendente de conferência: Resolução CNJ 455/2022.
   - Suspensão de 20 de dezembro a 20 de janeiro (CPC, art. 220).
   - Feriados nacionais, estaduais, municipais da comarca e suspensões do tribunal, em tabela versionada.
   - Se houver intimação pelo portal e pelo DJEN do mesmo ato, sinalizar e adotar a data mais conservadora.
   - Publicação de mera ciência sem prazo fixado: base de 3 dias úteis. É convenção interna, mais conservadora que os 5 dias do CPC, art. 218, § 3º, e deve aparecer assim rotulada.
   - **Prazo de segurança:** metade do prazo antes do término. Prazo ímpar arredonda para baixo (ex.: 15 dias úteis, segurança no 7º dia útil).
4. **Contexto:**
   - Pasta do Legal One (cliente, valor, envolvidos, histórico).
   - Autos, lidos nos sistemas dos tribunais (e-SAJ, PJe, eproc, Projudi) por adaptadores próprios; andamentos complementares pelo DataJud.
   - Dados do cliente na pasta GAA: título executivo, nota de leilão, contrato, CPR ou cédula, comprovantes, último cálculo e histórico de contato com o devedor.
   - **Devedor contumaz:** cruzar CPF/CNPJ do executado com todos os processos e clientes da base; se houver outras execuções, informar na análise (bens já penhorados, endereços, medidas que funcionaram ou falharam).
5. **Estratégia:** seguir o playbook do tipo de crédito (seção 5.2) e propor a medida cabível com fundamento (ex.: SISBAJUD, RENAJUD, INFOJUD, art. 854; penhora de safra ou semoventes; CNIB; protesto e negativação, arts. 517 e 782, § 3º; IDPJ, art. 133; citação por edital, art. 256; suspensão, art. 921) e atualizar o débito (padrão: IPCA, juros de 1% ao mês, multa de 2%, ou Tabela Prática do TJSP em débito judicial).
6. **Minuta:** no padrão GAA da seção 6.
7. **Revisão:** verificação de citações sempre. Revisão adversarial (parte contrária e juiz a frio) apenas em peças de maior peso, para não gastar tokens em petição simples.
8. **Aprovação e lançamento:** Henrique aprova ou corrige, com registro de supervisão (princípio 10). Só então a tarefa é lançada no Legal One. Em lote, gerar antes uma tabela de validação com a coluna do cliente.
9. **Aprendizado:** guardar a diferença entre a minuta do sistema e a versão final de Henrique. Correções recorrentes viram regra no playbook.
10. **Resultado:** quando a medida tiver desfecho (ex.: SISBAJUD positivo ou negativo, bem penhorado, acordo, valor levantado), registrar na tabela de resultados (seção 5.3).

### 5.2 Playbooks

- Ficam em `docs/playbooks/`, um arquivo por tipo de crédito, por exemplo: cheque, nota promissória e duplicata; cédula de crédito bancário (CCB); contrato com alienação fiduciária (busca e apreensão); contrato de locação de bens e equipamentos; contrato de prestação de serviços; nota de leilão; CPR e cédula de crédito rural; crédito sem título executivo (monitória ou cobrança); cumprimento de sentença.
- Cada playbook define: requisitos do título, ordem preferencial de medidas, peças-modelo, riscos típicos de defesa do executado e quando escalar para Henrique.
- O playbook é escrito e aprovado por Henrique. O sistema propõe alterações com base nos resultados, mas nunca altera playbook sozinho.

### 5.3 Resultados e jurimetria própria

- Tabela de resultados por medida: processo, tipo de crédito, comarca, perfil do devedor (PF, PJ, produtor rural), medida adotada, data do pedido, data da decisão, resultado, valor recuperado.
- Uso: ranquear, por comarca e perfil de devedor, as medidas que efetivamente recuperam crédito e o tempo médio até a satisfação. Esses números alimentam a estratégia da etapa 5 e as revisões de playbook.
- Esta base é ativo estratégico do projeto: tratar com o mesmo cuidado de segurança dos dados de clientes.

### 5.4 Regras da tarefa no Legal One

- Toda publicação gera tarefa, inclusive as de mera ciência.
- Lançar pela aba Publicações, botão "Adicionar" e depois "Nova tarefa". Nunca pelo botão "Agendar".
- Vínculo: somente a pasta do processo da publicação, com "Usar esse vínculo para a contagem de prazo" marcado.
- Envolvidos: Solicitante = Sócio Responsável pela Área (planilha "SÓCIO POR ÁREA", aba "Sócio por Advogado"); Executante = Responsável pelo Cliente; Responsável = Responsável principal da pasta.
- Descrição: até 250 caracteres, iniciada pelo primeiro nome do executante, texto corrido e imperativo, sem rótulo de categoria.
- Processos e publicações trabalhistas estão fora do escopo deste fluxo.

## 6. Padrão das peças GAA

- Sempre reaproveitar o próprio .docx-modelo do escritório (cabeçalho com logo GAA, rodapé www.gomesaltimari.com.br, estilos) e trocar só o corpo. Nunca montar formatação do zero.
- Century Schoolbook, espaçamento 1,5, parágrafos numerados sem recuo de primeira linha, uma linha em branco entre parágrafos e entre alíneas.
- Títulos de seção centralizados (algarismo romano em negrito + título em versalete). Nomes de pessoas em versalete com inicial maiúscula, nunca em caixa alta.
- Pedidos em alíneas a), b), c). Assinatura apenas de Henrique Borges Rodrigues, OAB/SP 509.289.
- Redação forense tradicional, sem marcas de texto gerado por IA: sem travessões, sem frases de efeito, sem "não apenas X, mas também Y", sem listas no corpo da argumentação.
- Direito claro, peça curta e objetiva. Tese difícil, fundamentação densa.

## 7. Qualidade e metas

- **Prazo correto em 100% dos casos da base de teste.** Critério eliminatório; qualquer erro bloqueia a promoção do fluxo.
- Percentual de minutas aprovadas sem edição (meta inicial: acompanhar e subir semana a semana).
- Tempo entre a publicação e a minuta pronta.
- A base `tests/casos/` (publicações antigas + peça efetivamente protocolada) roda a cada mudança relevante como teste de regressão.

## 8. Como trabalhar neste repositório

1. Antes de codar algo não trivial, apresente um plano curto e espere aprovação.
2. Domínio primeiro, com testes: escreva os testes de prazo antes da implementação.
3. Mudanças pequenas, um assunto por commit, mensagem em português.
4. Rode `uv run ruff check`, `uv run ruff format` e `uv run pytest` antes de dar a tarefa por concluída.
5. Nunca commite `.env`, credenciais, autos ou documentos de clientes. Casos de teste são anonimizados.
6. Adaptadores externos (Legal One, DJEN, Supabase, WhatsApp) devem ter versão falsa para testes, sem rede.
7. Falha de fonte externa (DJEN fora do ar, sessão do Legal One expirada) gera nova tentativa com espera e, persistindo, alerta a Henrique. Nada falha em silêncio.
8. Pergunte antes de adicionar dependência pesada ou mudar a arquitetura desta seção.
9. Responda em português.

## 9. Fases

- **Fase 0:** fundação (repositório, este arquivo, `pyproject`, estrutura, auditoria de RLS no Supabase existente).
- **Fase 1:** domínio de prazos e calendário com testes; coleta do DJEN; classificação; modo sombra.
- **Fase 2:** contexto (Legal One, pasta GAA, DataJud, leitura de autos no e-SAJ e demais tribunais), cruzamento de devedor contumaz e lançamento de tarefa com aprovação e registro de supervisão.
- **Fase 3:** playbooks, estratégia, cálculo e minuta no .docx-modelo; verificação de citações; tabela de resultados.
- **Fase 4:** canal WhatsApp oficial e alertas.
- **Fase 5:** novos fluxos: cobrança pré-judicial (notificação, protesto, negativação, proposta de acordo), distribuição de novas execuções a partir do título, análise de risco do devedor antes da concessão do crédito ou do leilão, e crédito rural.
