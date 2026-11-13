"""Testes da contagem de prazos (CPC, arts. 219, 220 e 224)."""

from datetime import date

import pytest

from assistente.dominio.calendario import Calendario, Evento, TipoEvento
from assistente.dominio.prazos import (
    DIAS_MERA_CIENCIA,
    calcular_prazo,
    calcular_prazo_mera_ciencia,
    dia_de_seguranca,
    mais_conservador,
)

SEM_FERIADOS = Calendario([])


def test_prazo_simples_de_15_dias() -> None:
    # disponibilizado segunda 02/03/2026; publicado 03/03; início 04/03
    prazo = calcular_prazo(date(2026, 3, 2), 15, SEM_FERIADOS)
    assert prazo.publicacao == date(2026, 3, 3)
    assert prazo.inicio == date(2026, 3, 4)
    assert prazo.vencimento == date(2026, 3, 24)
    assert prazo.seguranca == date(2026, 3, 12)
    assert prazo.avisos == ()


def test_disponibilizacao_na_sexta_publica_na_segunda() -> None:
    prazo = calcular_prazo(date(2026, 3, 6), 5, SEM_FERIADOS)
    assert prazo.publicacao == date(2026, 3, 9)
    assert prazo.inicio == date(2026, 3, 10)
    assert prazo.vencimento == date(2026, 3, 16)


def test_disponibilizacao_no_sabado() -> None:
    prazo = calcular_prazo(date(2026, 3, 7), 5, SEM_FERIADOS)
    assert prazo.publicacao == date(2026, 3, 9)


def test_feriado_no_meio_do_prazo() -> None:
    cal = Calendario([Evento(date(2026, 3, 12), TipoEvento.FERIADO, "f", "teste")])
    prazo = calcular_prazo(date(2026, 3, 9), 5, cal)
    # início 11/03; conta 11, 13, 16, 17, 18
    assert prazo.inicio == date(2026, 3, 11)
    assert prazo.vencimento == date(2026, 3, 18)


def test_feriado_no_dia_seguinte_a_disponibilizacao() -> None:
    cal = Calendario([Evento(date(2026, 3, 10), TipoEvento.FERIADO, "f", "teste")])
    prazo = calcular_prazo(date(2026, 3, 9), 5, cal)
    assert prazo.publicacao == date(2026, 3, 11)
    assert prazo.inicio == date(2026, 3, 12)


def test_prazo_atravessa_o_recesso() -> None:
    prazo = calcular_prazo(date(2026, 12, 17), 5, SEM_FERIADOS)
    assert prazo.publicacao == date(2026, 12, 18)
    assert prazo.inicio == date(2027, 1, 21)
    assert prazo.vencimento == date(2027, 1, 27)
    assert prazo.avisos == ()


def test_publicacao_durante_o_recesso_gera_aviso() -> None:
    prazo = calcular_prazo(date(2027, 1, 8), 5, SEM_FERIADOS)
    assert prazo.publicacao == date(2027, 1, 11)
    assert prazo.inicio == date(2027, 1, 21)
    assert any("recesso" in a for a in prazo.avisos)


def test_vencimento_em_expediente_irregular_prorroga() -> None:
    cal = Calendario(
        [Evento(date(2026, 3, 16), TipoEvento.EXPEDIENTE_IRREGULAR, "a partir das 13h", "t")]
    )
    prazo = calcular_prazo(date(2026, 3, 6), 5, cal)
    assert prazo.vencimento == date(2026, 3, 17)
    assert any("224, § 1º" in a for a in prazo.avisos)


def test_inicio_em_indisponibilidade_prorroga() -> None:
    cal = Calendario([Evento(date(2026, 3, 10), TipoEvento.INDISPONIBILIDADE, "sistema", "t")])
    prazo = calcular_prazo(date(2026, 3, 6), 5, cal)
    assert prazo.inicio == date(2026, 3, 11)
    assert prazo.vencimento == date(2026, 3, 17)
    assert any("224, § 1º" in a for a in prazo.avisos)


@pytest.mark.parametrize(("dias", "esperado"), [(1, 1), (2, 1), (3, 1), (5, 2), (10, 5), (15, 7)])
def test_dia_de_seguranca_arredonda_para_baixo(dias: int, esperado: int) -> None:
    assert dia_de_seguranca(dias) == esperado


def test_prazo_de_um_dia() -> None:
    prazo = calcular_prazo(date(2026, 3, 2), 1, SEM_FERIADOS)
    assert prazo.inicio == prazo.vencimento == prazo.seguranca == date(2026, 3, 4)


@pytest.mark.parametrize("dias", [0, -1])
def test_rejeita_prazo_nao_positivo(dias: int) -> None:
    with pytest.raises(ValueError):
        calcular_prazo(date(2026, 3, 2), dias, SEM_FERIADOS)


def test_mera_ciencia_tem_3_dias_e_rotulo() -> None:
    prazo = calcular_prazo_mera_ciencia(date(2026, 3, 2), SEM_FERIADOS)
    assert DIAS_MERA_CIENCIA == 3
    assert prazo.dias == 3
    assert prazo.vencimento == date(2026, 3, 6)
    assert any("convenção interna" in a and "218, § 3º" in a for a in prazo.avisos)


def test_mais_conservador_escolhe_vencimento_mais_cedo() -> None:
    portal = calcular_prazo(date(2026, 3, 2), 15, SEM_FERIADOS)
    djen = calcular_prazo(date(2026, 3, 4), 15, SEM_FERIADOS)
    escolhido = mais_conservador(djen, portal)
    assert escolhido.vencimento == portal.vencimento
    assert any("divergência" in a for a in escolhido.avisos)


def test_mais_conservador_sem_divergencia_nao_avisa() -> None:
    a = calcular_prazo(date(2026, 3, 2), 15, SEM_FERIADOS)
    assert mais_conservador(a, a).avisos == ()


def test_mais_conservador_exige_ao_menos_um() -> None:
    with pytest.raises(ValueError):
        mais_conservador()


def test_calendario_pendente_de_conferencia_gera_aviso() -> None:
    cal = Calendario([], conferido=False)
    prazo = calcular_prazo(date(2026, 3, 2), 5, cal)
    assert any("pendente de conferência" in a for a in prazo.avisos)


def test_dentro_da_cobertura_nao_avisa() -> None:
    cal = Calendario([], cobertura_ate=date(2026, 12, 31))
    assert calcular_prazo(date(2026, 3, 2), 15, cal).avisos == ()
