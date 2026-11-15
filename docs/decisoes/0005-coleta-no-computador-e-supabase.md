# Decisão 0005: coleta do DJEN no computador de Henrique, gravação no Supabase

Data: 15/11/2026. Aprovada por Henrique Borges Rodrigues.

## Contexto

- A API do DJEN recusa acesso de fora do Brasil (403 do CloudFront, testado em 13/11/2026). A sessão de desenvolvimento na nuvem roda fora do Brasil.
- Henrique não quer acumular dados no próprio computador.
- O CLAUDE.md proíbe dados de clientes no Git (seção 8.5) e prevê o Supabase como banco (seção 3).

## Decisão

1. **Onde roda a coleta:** no computador de Henrique, no Brasil, agendada no Windows (docs/operacao/coleta-djen-windows.md), enquanto o Fluxo 1 estiver em modo sombra.
2. **Onde ficam os dados:** no Supabase, projeto `assistente-gaa`, região `sa-east-1` (São Paulo), separado de outros projetos. Tabelas `comunicacoes` e `coletas`, com RLS ligado e sem políticas: só a chave secreta acessa. Esquema versionado em `supabase/migrations/`.
3. **Chave secreta:** só no `.env` do computador de Henrique; nunca em código, log, chat ou commit (princípio 7).
4. **Computador desligado:** a coleta seguinte busca desde a última coleta bem-sucedida; repetidas são ignoradas pelo identificador do DJEN (princípio 5).
5. **Migração para a nuvem:** na passagem para o modo ativo, a coleta vai para uma nuvem com região no Brasil (preferência: Google Cloud, Cloud Run Jobs em São Paulo), depois de testar que o DJEN aceita o acesso de lá.

## Alternativas descartadas

- Gravar no GitHub: histórico permanente, sem consulta, contrário ao sigilo e à LGPD.
- Banco local no computador: Henrique não quer dados no computador, e o banco morreria com a máquina.
- Apps Script do Google: região não escolhida (provável bloqueio do DJEN) e código em JavaScript fora do sistema testado.
