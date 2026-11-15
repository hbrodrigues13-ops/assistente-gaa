"""Testes das regras puras da coleta do DJEN."""

from datetime import date

import pytest

from assistente.dominio.comunicacao import coleta_atrasada, intervalo_de_coleta


def test_primeira_coleta_busca_os_ultimos_7_dias() -> None:
    assert intervalo_de_coleta(None, date(2026, 11, 16)) == (date(2026, 11, 9), date(2026, 11, 16))


def test_coleta_seguinte_repete_o_ultimo_dia_coletado() -> None:
    # sobreposição de 1 dia: publicação disponibilizada tarde no último dia não se perde
    assert intervalo_de_coleta(date(2026, 11, 13), date(2026, 11, 16)) == (
        date(2026, 11, 12),
        date(2026, 11, 16),
    )


def test_computador_desligado_uma_semana_busca_o_periodo_todo() -> None:
    inicio, fim = intervalo_de_coleta(date(2026, 11, 2), date(2026, 11, 16))
    assert (inicio, fim) == (date(2026, 11, 1), date(2026, 11, 16))


def test_ultima_coleta_no_futuro_e_erro() -> None:
    with pytest.raises(ValueError):
        intervalo_de_coleta(date(2026, 11, 20), date(2026, 11, 16))


@pytest.mark.parametrize(
    ("ultima", "hoje", "atrasada"),
    [
        (None, date(2026, 11, 16), True),
        (date(2026, 11, 16), date(2026, 11, 16), False),
        (date(2026, 11, 13), date(2026, 11, 16), False),  # sexta -> segunda: 1 dia útil
        (date(2026, 11, 12), date(2026, 11, 16), True),  # quinta -> segunda: 2 dias úteis
        (date(2026, 11, 11), date(2026, 11, 13), True),
    ],
)
def test_coleta_atrasada_depois_de_um_dia_util(
    ultima: date | None, hoje: date, atrasada: bool
) -> None:
    assert coleta_atrasada(ultima, hoje) is atrasada
