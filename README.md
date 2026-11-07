# assistente-gaa

Assistente jurídico de Henrique Borges Rodrigues (GAA) para recuperação de crédito. A fonte de verdade do projeto é o [CLAUDE.md](CLAUDE.md).

## Preparação

```bash
uv sync
uvx leis-mcp==0.2.0 index   # índice de legislação (~100 MB, só na primeira vez)
```

## Verificações antes de concluir qualquer tarefa

```bash
uv run ruff check
uv run ruff format
uv run mypy
uv run pytest
```
