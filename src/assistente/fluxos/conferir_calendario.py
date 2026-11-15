"""Confere a tabela de calendário com a consulta oficial do TJSP e imprime o relatório.

Uso: uv run python -m assistente.fluxos.conferir_calendario 2027

Somente leitura: não altera nenhuma tabela. As divergências e o TOML
sugerido vão para Henrique aprovar antes de qualquer mudança (princípio 2).
"""

import sys

from assistente.dominio.calendario import Calendario, dias_sem_expediente_lei_federal
from assistente.fontes.calendarios import CalendarioIndisponivel, carregar_calendario, ler_dados
from assistente.fontes.tjsp_feriados import (
    ClienteTjsp,
    ConsultaTjsp,
    conferir_calendario,
    municipio_da_comarca,
)


def _um_foro_por_comarca() -> dict[str, str]:
    foros = (ler_dados("tjsp", "comarcas.toml") or {}).get("foros", {})
    resultado: dict[str, str] = {}
    for foro, comarca in sorted(foros.items()):
        resultado.setdefault(str(comarca), str(foro))
    return resultado


def conferir_todas(ano: int, tjsp: ConsultaTjsp) -> tuple[str, bool]:
    partes = [f"# Conferência do calendário TJSP {ano}", ""]
    tudo_confere = True
    for comarca, foro in _um_foro_por_comarca().items():
        municipio = municipio_da_comarca(comarca)
        if municipio is None:
            partes.append(f"## {comarca}: sem nome de município cadastrado\n")
            tudo_confere = False
            continue
        sem_tabela = False
        try:
            calendario = carregar_calendario(ano, foro)
        except CalendarioIndisponivel:
            sem_tabela = True
            calendario = Calendario(dias_sem_expediente_lei_federal(ano), comarca=comarca)
        resultado = conferir_calendario(tjsp, calendario, municipio, ano)
        tudo_confere = tudo_confere and resultado.sem_divergencia and not sem_tabela
        partes.append(resultado.relatorio())
        if sem_tabela:
            partes.append(f"(sem tabela de {ano}: comparação só com as datas de lei federal)\n")
        if resultado.faltando_na_tabela:
            partes += ["TOML sugerido:", "```toml", resultado.toml_sugerido(comarca), "```", ""]
    return "\n".join(partes), tudo_confere


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    ano = int(args[0])
    texto, tudo_confere = conferir_todas(ano, ClienteTjsp(pausa=1.0))
    print(texto)
    return 0 if tudo_confere else 1


if __name__ == "__main__":
    raise SystemExit(main())
