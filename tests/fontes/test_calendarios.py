"""Testes da tabela versionada de calendário do TJSP."""

from datetime import date

import pytest

from assistente.dominio.calendario import TipoEvento
from assistente.dominio.prazos import calcular_prazo
from assistente.fontes.calendarios import (
    CalendarioIndisponivel,
    carregar_calendario,
    comarca_do_foro,
)


def test_foro_0344_e_marilia() -> None:
    assert comarca_do_foro("0344") == "marilia"


def test_foro_desconhecido() -> None:
    assert comarca_do_foro("9999") is None


def test_ano_sem_tabela() -> None:
    with pytest.raises(CalendarioIndisponivel):
        carregar_calendario(1999, "0344")


def test_tabela_2026_marilia() -> None:
    cal = carregar_calendario(2026, "0344")
    assert cal.comarca == "marilia"
    assert not cal.tem_expediente(date(2026, 7, 9))  # data magna de SP
    assert not cal.tem_expediente(date(2026, 7, 10))  # Prov. CSM 2.813/2025
    assert not cal.tem_expediente(date(2026, 10, 30))  # Prov. CSM 2.845/2026
    assert cal.tem_expediente(date(2026, 10, 28))  # expediente normal
    assert not cal.tem_expediente(date(2026, 11, 20))  # Lei 14.759/2023
    assert not cal.tem_expediente(date(2026, 12, 7))
    assert not cal.tem_expediente(date(2026, 12, 8))
    tipos = {e.tipo for e in cal.eventos_em(date(2026, 2, 18))}
    assert TipoEvento.EXPEDIENTE_IRREGULAR in tipos


def test_todo_evento_da_tabela_tem_fonte() -> None:
    cal = carregar_calendario(2026, "0344")
    assert all(e.fonte for e in cal.eventos)


def test_prazo_real_novembro_2026_marilia() -> None:
    cal = carregar_calendario(2026, "0344")
    # disponibilizado qui 19/11; 20/11 feriado; publicado seg 23/11; início ter 24/11
    prazo = calcular_prazo(date(2026, 11, 19), 15, cal)
    assert prazo.publicacao == date(2026, 11, 23)
    assert prazo.inicio == date(2026, 11, 24)
    assert prazo.seguranca == date(2026, 12, 2)
    assert prazo.vencimento == date(2026, 12, 16)


def test_prazo_real_dezembro_2026_marilia() -> None:
    cal = carregar_calendario(2026, "0344")
    # disponibilizado sex 04/12; 07/12 suspenso; 08/12 feriado; publicado qua 09/12
    prazo = calcular_prazo(date(2026, 12, 4), 5, cal)
    assert prazo.publicacao == date(2026, 12, 9)
    assert prazo.inicio == date(2026, 12, 10)
    assert prazo.vencimento == date(2026, 12, 16)


def test_prazo_que_passa_do_ano_sem_tabela_gera_aviso() -> None:
    cal = carregar_calendario(2026, "0344")
    assert cal.cobertura_ate == date(2026, 12, 31)
    prazo = calcular_prazo(date(2026, 12, 15), 15, cal)
    assert prazo.vencimento.year == 2027
    assert any("ano seguinte" in a for a in prazo.avisos)


def test_foro_sem_comarca_cadastrada_fica_nao_conferido() -> None:
    cal = carregar_calendario(2026, "9999")
    assert cal.comarca is None
    assert not cal.conferido
