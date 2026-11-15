"""Erros comuns das fontes externas."""


class FonteIndisponivel(RuntimeError):
    """A fonte externa falhou mesmo depois das novas tentativas (CLAUDE.md, seção 8.7)."""
