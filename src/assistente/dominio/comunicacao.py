"""Comunicação processual do DJEN e regras puras da coleta.

Sem I/O. A leitura da API fica em `assistente.fontes.djen`.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

DIAS_PRIMEIRA_COLETA = 7
DIAS_SOBREPOSICAO = 1


@dataclass(frozen=True, slots=True)
class Comunicacao:
    id: str
    """Identificador da comunicação no DJEN: chave de idempotência (princípio 5)."""
    disponibilizacao: date
    numero_processo: str | None
    tribunal: str | None
    texto: str
    bruto: dict[str, Any] = field(compare=False, repr=False)


def intervalo_de_coleta(ultima_ok: date | None, hoje: date) -> tuple[date, date]:
    """Período a consultar: desde a última coleta bem-sucedida, com 1 dia de sobreposição.

    Computador desligado por dias não perde publicação: a coleta seguinte
    busca o período inteiro, e as repetidas são ignoradas pelo identificador.
    """
    if ultima_ok is None:
        return hoje - timedelta(days=DIAS_PRIMEIRA_COLETA), hoje
    if ultima_ok > hoje:
        raise ValueError(f"última coleta ({ultima_ok}) posterior a hoje ({hoje})")
    return ultima_ok - timedelta(days=DIAS_SOBREPOSICAO), hoje


def coleta_atrasada(ultima_ok: date | None, hoje: date) -> bool:
    """Atrasada quando passou mais de um dia útil (segunda a sexta) sem coleta bem-sucedida."""
    if ultima_ok is None:
        return True
    dias_uteis = sum(
        1
        for n in range(1, (hoje - ultima_ok).days + 1)
        if (ultima_ok + timedelta(days=n)).weekday() < 5
    )
    return dias_uteis > 1
