# Decisão 0002: pydatajud para número CNJ e DataJud

Data: 07/11/2026. Aprovada por Henrique Borges Rodrigues.

## Contexto

O pydatajud 0.2.0 (Unlicense, github.com/Filipe-Araujo0/pydatajud) faz duas coisas úteis ao Fluxo 1:

1. valida e separa o número CNJ sem rede (Resolução CNJ 65/2008, módulo 97);
2. consulta a API pública do DataJud em lote, indicando quais processos tiveram movimentação desde uma data de corte, com uma requisição por tribunal.

## Decisão

1. **Fase 1:** a validação do número CNJ foi reimplementada no domínio (`src/assistente/dominio/numero_cnj.py`), sem dependência, com testes próprios. O cálculo foi conferido contra o do pydatajud. O foro de origem (`OOOO`) servirá para escolher o calendário de feriados da comarca.
2. **Fase 2:** o adaptador `src/assistente/fontes/datajud.py` usará o pydatajud como dependência para os andamentos complementares e para o modo sombra, com versão falsa nos testes.

## Ressalvas

- O pydatajud usa `requests`; o projeto padroniza `httpx`. Aceito por ficar isolado no adaptador.
- A chave pública do DataJud muda sem aviso. Ela fica no `.env` (`DATAJUD_API_KEY`) e o adaptador alerta quando receber 401/403.
- O próprio DataJud avisa que as movimentações podem ser resumidas. Ele serve para detectar andamento, não substitui a leitura dos autos.
- A tabela de foro do TJSP para comarca não vem no pacote e terá de ser montada a partir de fonte oficial.
