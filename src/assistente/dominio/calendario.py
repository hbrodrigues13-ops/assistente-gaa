"""Calendário forense: dias com expediente e dias em que o prazo corre.

Regras puras, sem I/O. Os feriados e suspensões de cada tribunal e comarca
vêm de tabela versionada, carregada por `assistente.fontes.calendarios`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class TipoEvento(StrEnum):
    FERIADO = "feriado"
    """Sem expediente; o prazo não corre."""
    SUSPENSAO_EXPEDIENTE = "suspensao_expediente"
    """Sem expediente por ato do tribunal; o prazo não corre."""
    SUSPENSAO_PRAZO = "suspensao_prazo"
    """Há expediente, mas o prazo não corre."""
    EXPEDIENTE_IRREGULAR = "expediente_irregular"
    """Expediente encerrado antes ou iniciado depois da hora normal (CPC, art. 224, § 1º)."""
    INDISPONIBILIDADE = "indisponibilidade"
    """Indisponibilidade da comunicação eletrônica (CPC, art. 224, § 1º)."""


SEM_EXPEDIENTE = frozenset({TipoEvento.FERIADO, TipoEvento.SUSPENSAO_EXPEDIENTE})
PRORROGAM = frozenset({TipoEvento.EXPEDIENTE_IRREGULAR, TipoEvento.INDISPONIBILIDADE})


@dataclass(frozen=True, slots=True)
class Evento:
    data: date
    tipo: TipoEvento
    descricao: str
    fonte: str
    comarca: str | None = None
    """None vale para todo o tribunal."""


def pascoa(ano: int) -> date:
    """Domingo de Páscoa no calendário gregoriano (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes, dia = divmod(h + m - 7 * n + 114, 31)
    return date(ano, mes, dia + 1)


def datas_moveis(ano: int) -> dict[str, date]:
    p = pascoa(ano)
    return {
        "segunda_carnaval": p - timedelta(days=48),
        "terca_carnaval": p - timedelta(days=47),
        "quarta_cinzas": p - timedelta(days=46),
        "quinta_santa": p - timedelta(days=3),
        "sexta_santa": p - timedelta(days=2),
        "corpus_christi": p + timedelta(days=60),
    }


_LEI_662 = "Lei 662/1949, art. 1º (redação da Lei 10.607/2002)"
_FERIADOS_FIXOS: tuple[tuple[int, int, str, str], ...] = (
    (1, 1, "Confraternização Universal", _LEI_662),
    (4, 21, "Tiradentes", _LEI_662),
    (5, 1, "Dia do Trabalho", _LEI_662),
    (9, 7, "Independência", _LEI_662),
    (10, 12, "Nossa Senhora Aparecida", "Lei 6.802/1980, art. 1º"),
    (11, 2, "Finados", _LEI_662),
    (11, 15, "Proclamação da República", _LEI_662),
    (11, 20, "Dia Nacional de Zumbi e da Consciência Negra", "Lei 14.759/2023"),
    (12, 25, "Natal", _LEI_662),
)


def dias_sem_expediente_lei_federal(ano: int) -> list[Evento]:
    """Feriados nacionais, terça-feira de Carnaval e Sexta-feira Santa (Lei 1.408/1951, art. 5º).

    O "Dia da Justiça" e os dias de lei estadual ficam na tabela do tribunal.
    """
    eventos = [
        Evento(date(ano, mes, dia), TipoEvento.FERIADO, descricao, fonte)
        for mes, dia, descricao, fonte in _FERIADOS_FIXOS
    ]
    moveis = datas_moveis(ano)
    eventos.append(
        Evento(
            moveis["terca_carnaval"],
            TipoEvento.FERIADO,
            "Terça-feira de Carnaval",
            "Lei 1.408/1951, art. 5º",
        )
    )
    eventos.append(
        Evento(
            moveis["sexta_santa"],
            TipoEvento.FERIADO,
            "Sexta-feira Santa",
            "Lei 1.408/1951, art. 5º",
        )
    )
    return eventos


def em_recesso_art220(dia: date) -> bool:
    """De 20 de dezembro a 20 de janeiro, inclusive (CPC, art. 220)."""
    return (dia.month == 12 and dia.day >= 20) or (dia.month == 1 and dia.day <= 20)


class Calendario:
    def __init__(
        self,
        eventos: Iterable[Evento],
        comarca: str | None = None,
        conferido: bool = True,
        cobertura_ate: date | None = None,
    ) -> None:
        self.comarca = comarca
        self.conferido = conferido
        self.cobertura_ate = cobertura_ate
        """Último dia coberto pelas tabelas do tribunal; None quando não se aplica."""
        self.eventos = tuple(e for e in eventos if e.comarca is None or e.comarca == comarca)
        por_dia: dict[date, list[Evento]] = {}
        for evento in self.eventos:
            por_dia.setdefault(evento.data, []).append(evento)
        self._por_dia = {dia: tuple(lista) for dia, lista in por_dia.items()}

    def eventos_em(self, dia: date) -> tuple[Evento, ...]:
        return self._por_dia.get(dia, ())

    def _tem_tipo(self, dia: date, tipos: frozenset[TipoEvento]) -> bool:
        return any(e.tipo in tipos for e in self.eventos_em(dia))

    def tem_expediente(self, dia: date) -> bool:
        return dia.weekday() < 5 and not self._tem_tipo(dia, SEM_EXPEDIENTE)

    def corre_prazo(self, dia: date) -> bool:
        return (
            self.tem_expediente(dia)
            and not em_recesso_art220(dia)
            and not self._tem_tipo(dia, frozenset({TipoEvento.SUSPENSAO_PRAZO}))
        )

    def prorroga(self, dia: date) -> bool:
        return self._tem_tipo(dia, PRORROGAM)

    def proximo_dia_expediente(self, dia: date) -> date:
        seguinte = dia + timedelta(days=1)
        while not self.tem_expediente(seguinte):
            seguinte += timedelta(days=1)
        return seguinte

    def proximo_dia_prazo(self, dia: date) -> date:
        seguinte = dia + timedelta(days=1)
        while not self.corre_prazo(seguinte):
            seguinte += timedelta(days=1)
        return seguinte
