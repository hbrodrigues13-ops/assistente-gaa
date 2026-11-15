"""Testes do calendário forense."""

from datetime import date

import pytest

from assistente.dominio.calendario import (
    Calendario,
    Evento,
    TipoEvento,
    datas_moveis,
    dias_sem_expediente_lei_federal,
    em_recesso_art220,
    pascoa,
)


@pytest.mark.parametrize(
    ("ano", "esperada"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_pascoa(ano: int, esperada: date) -> None:
    assert pascoa(ano) == esperada


def test_datas_moveis_2026() -> None:
    moveis = datas_moveis(2026)
    assert moveis["segunda_carnaval"] == date(2026, 2, 16)
    assert moveis["terca_carnaval"] == date(2026, 2, 17)
    assert moveis["quarta_cinzas"] == date(2026, 2, 18)
    assert moveis["quinta_santa"] == date(2026, 4, 2)
    assert moveis["sexta_santa"] == date(2026, 4, 3)
    assert moveis["corpus_christi"] == date(2026, 6, 4)


def test_dias_sem_expediente_lei_federal_2026() -> None:
    datas = {e.data for e in dias_sem_expediente_lei_federal(2026)}
    esperadas = {
        date(2026, 1, 1),
        date(2026, 2, 17),
        date(2026, 4, 3),
        date(2026, 4, 21),
        date(2026, 5, 1),
        date(2026, 9, 7),
        date(2026, 10, 12),
        date(2026, 11, 2),
        date(2026, 11, 15),
        date(2026, 11, 20),
        date(2026, 12, 25),
    }
    assert datas == esperadas


def test_todo_evento_federal_tem_fonte() -> None:
    assert all(e.fonte for e in dias_sem_expediente_lei_federal(2026))


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (date(2026, 12, 19), False),
        (date(2026, 12, 20), True),
        (date(2026, 12, 31), True),
        (date(2027, 1, 1), True),
        (date(2027, 1, 20), True),
        (date(2027, 1, 21), False),
    ],
)
def test_recesso_art220_inclusive(dia: date, esperado: bool) -> None:
    assert em_recesso_art220(dia) is esperado


def test_fim_de_semana_nao_tem_expediente() -> None:
    cal = Calendario([])
    assert not cal.tem_expediente(date(2026, 3, 7))  # sábado
    assert not cal.tem_expediente(date(2026, 3, 8))  # domingo
    assert cal.tem_expediente(date(2026, 3, 9))


def test_recesso_tem_expediente_mas_prazo_nao_corre() -> None:
    cal = Calendario([])
    dia = date(2027, 1, 12)
    assert cal.tem_expediente(dia)
    assert not cal.corre_prazo(dia)


def test_suspensao_de_prazo_com_expediente() -> None:
    dia = date(2026, 3, 10)
    cal = Calendario([Evento(dia, TipoEvento.SUSPENSAO_PRAZO, "suspensão", "teste")])
    assert cal.tem_expediente(dia)
    assert not cal.corre_prazo(dia)


def test_expediente_irregular_conta_mas_prorroga() -> None:
    dia = date(2026, 3, 10)
    cal = Calendario([Evento(dia, TipoEvento.EXPEDIENTE_IRREGULAR, "a partir das 13h", "teste")])
    assert cal.corre_prazo(dia)
    assert cal.prorroga(dia)


def test_evento_de_comarca_so_vale_na_comarca() -> None:
    dia = date(2026, 3, 10)
    evento = Evento(dia, TipoEvento.FERIADO, "municipal", "teste", comarca="marilia")
    assert not Calendario([evento], comarca="marilia").tem_expediente(dia)
    assert Calendario([evento], comarca="bauru").tem_expediente(dia)
    assert Calendario([evento]).tem_expediente(dia)


def test_proximos_dias() -> None:
    cal = Calendario([Evento(date(2026, 3, 9), TipoEvento.FERIADO, "f", "teste")])
    assert cal.proximo_dia_expediente(date(2026, 3, 6)) == date(2026, 3, 10)
    assert cal.proximo_dia_prazo(date(2027, 1, 8)) == date(2027, 1, 21)


def test_eventos_em() -> None:
    dia = date(2026, 3, 10)
    evento = Evento(dia, TipoEvento.FERIADO, "f", "teste")
    assert Calendario([evento]).eventos_em(dia) == (evento,)
