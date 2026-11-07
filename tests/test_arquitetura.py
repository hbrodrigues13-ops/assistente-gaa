"""Garante a regra de dependência da seção 4 do CLAUDE.md."""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "src" / "assistente"
PROIBIDOS_NO_DOMINIO = ("fontes", "adaptadores", "agentes", "pecas", "fluxos")


def _imports(arquivo: Path) -> list[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.extend(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                # import relativo: resolve a partir do pacote dominio
                base = "assistente.dominio" if no.level == 1 else "assistente"
                nomes.append(f"{base}.{no.module}" if no.module else base)
            elif no.module:
                nomes.append(no.module)
    return nomes


def test_pacotes_da_estrutura_existem() -> None:
    for pacote in ("dominio", "fontes", "adaptadores", "agentes", "pecas", "fluxos"):
        assert (RAIZ / pacote / "__init__.py").is_file(), pacote


def test_dominio_nao_importa_camadas_de_io() -> None:
    violacoes = []
    for arquivo in (RAIZ / "dominio").rglob("*.py"):
        for nome in _imports(arquivo):
            partes = nome.split(".")
            if partes[0] == "assistente" and len(partes) > 1 and partes[1] in PROIBIDOS_NO_DOMINIO:
                violacoes.append(f"{arquivo.name}: {nome}")
    assert not violacoes, violacoes
