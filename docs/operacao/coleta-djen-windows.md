# Coleta do DJEN no computador de Henrique (Windows)

A API do DJEN só aceita acesso a partir do Brasil, por isso a coleta roda neste computador (decisão de 15/11/2026). Fase atual: **modo sombra**. A coleta só grava as publicações num banco local; nada é lançado no Legal One e o controle manual de prazos continua valendo.

Tempo estimado: 15 minutos, uma vez só.

## 1. Instalar o uv (gerenciador do Python)

Abra o **PowerShell** (menu Iniciar, digite "PowerShell") e rode:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Feche e abra o PowerShell de novo.

## 2. Baixar o repositório

1. Instale o **GitHub Desktop** (desktop.github.com) e entre com a conta `hbrodrigues13-ops`.
2. *File > Clone repository*, escolha `hbrodrigues13-ops/assistente-gaa` e a pasta `C:\assistente-gaa`.

## 3. Criar o .env

Na pasta `C:\assistente-gaa`, copie o arquivo `.env.example` e renomeie a cópia para `.env`. Para a coleta, os valores que já vêm preenchidos bastam (`DJEN_OABS` e `PYTHONUTF8`). O `.env` nunca vai para o GitHub.

## 4. Teste de diagnóstico

No PowerShell:

```powershell
cd C:\assistente-gaa
uv sync
uv run --env-file .env python -m assistente.fluxos.coleta_djen --diagnostico
```

O resultado mostra quantas comunicações o DJEN devolveu nos últimos 7 dias e os nomes dos campos. **Mande essa saída para o Claude**: com ela, o formato da resposta fica fixado nos testes.

## 5. Primeira coleta

```powershell
uv run --env-file .env python -m assistente.fluxos.coleta_djen
```

Saída esperada: uma linha por OAB, com o período, as comunicações novas e as repetidas. O banco fica em `C:\Users\<seu usuário>\assistente-gaa-dados\assistente.db`, fora do repositório.

## 6. Agendar a coleta diária

1. Menu Iniciar, abra o **Agendador de Tarefas** e clique em **Criar Tarefa** (não "Criar Tarefa Básica").
2. **Geral:** nome `GAA Coleta DJEN`; marque "Executar estando o usuário conectado ou não".
3. **Disparadores:** Novo, Diariamente, 07:30.
4. **Ações:** Novo, Iniciar um programa.
   - Programa: `powershell.exe`
   - Argumentos (uma linha só):
     ```
     -NoProfile -Command "cd C:\assistente-gaa; & $env:USERPROFILE\.local\bin\uv.exe run --env-file .env python -m assistente.fluxos.coleta_djen *>> $env:USERPROFILE\assistente-gaa-dados\coleta.log"
     ```
5. **Condições:** marque "Despertar o computador para executar esta tarefa".
6. **Configurações:** marque "Executar a tarefa o mais cedo possível após uma inicialização agendada ser perdida".

Faça a etapa 5 (primeira coleta) antes de agendar: ela cria a pasta do log.

## Como acompanhar

- O log fica em `C:\Users\<seu usuário>\assistente-gaa-dados\coleta.log`.
- Linhas com **FALHA** ou **ALERTA** pedem atenção. ALERTA de "coleta atrasada" aparece quando passa mais de um dia útil sem coleta bem-sucedida.
- No Agendador, "Último resultado da execução" diferente de `0x0` indica falha ou alerta.
- Computador desligado não perde publicação: a coleta seguinte busca todo o período desde a última coleta bem-sucedida, e as repetidas são ignoradas.

O aviso ativo (e-mail ou WhatsApp) entra em fase posterior. Até lá, o acompanhamento é pelo log.
