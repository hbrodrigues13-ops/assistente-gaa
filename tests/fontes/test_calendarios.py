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


def test_carnaval_2026_vencimento_na_quarta_de_cinzas_prorroga() -> None:
    cal = carregar_calendario(2026, "0344")
    # disponibilizado qua 04/02; publicado qui 05/02; início sex 06/02
    # conta 06, 09, 10, 11, 12, 13 (6), 18/02 seria o 7º: 16 e 17 sem expediente
    prazo = calcular_prazo(date(2026, 2, 4), 7, cal)
    assert prazo.inicio == date(2026, 2, 6)
    assert prazo.vencimento == date(2026, 2, 19)
    assert any("224, § 1º" in a for a in prazo.avisos)


def test_semana_santa_e_tiradentes_2026() -> None:
    cal = carregar_calendario(2026, "0344")
    # disponibilizado ter 31/03; publicado qua 01/04; 02 e 03/04 sem expediente
    # início seg 06/04; conta 06, 07, 08, 09, 10, 13, 14, 15, 16, 17 (10),
    # 20 e 21/04 sem expediente; 22, 23, 24, 27, 28 (15)
    prazo = calcular_prazo(date(2026, 3, 31), 15, cal)
    assert prazo.publicacao == date(2026, 4, 1)
    assert prazo.inicio == date(2026, 4, 6)
    assert prazo.seguranca == date(2026, 4, 14)
    assert prazo.vencimento == date(2026, 4, 28)


def test_tabela_com_fim_antes_do_inicio_e_rejeitada(monkeypatch: pytest.MonkeyPatch) -> None:
    from assistente.fontes import calendarios

    tabela = {
        "conferido": True,
        "eventos": [
            {
                "inicio": date(2030, 5, 10),
                "fim": date(2030, 5, 9),
                "tipo": "feriado",
                "descricao": "x",
                "fonte": "t",
            }
        ],
    }
    original = calendarios._ler
    monkeypatch.setattr(
        calendarios,
        "_ler",
        lambda tribunal, arquivo: tabela if arquivo == "2030.toml" else original(tribunal, arquivo),
    )
    with pytest.raises(ValueError, match="fim antes do início"):
        carregar_calendario(2030, "0344")


def test_carrega_dois_anos_quando_ha_tabela_seguinte(monkeypatch: pytest.MonkeyPatch) -> None:
    from assistente.fontes import calendarios

    tabelas = {
        "2030.toml": {"conferido": True, "eventos": []},
        "comarcas.toml": {
            "foros": {"0344": "marilia"},
            "comarcas": {"marilia": {"feriados_municipais_conferidos": True}},
        },
        "2031.toml": {
            "conferido": True,
            "eventos": [
                {
                    "inicio": date(2031, 2, 3),
                    "tipo": "suspensao_expediente",
                    "descricao": "x",
                    "fonte": "t",
                }
            ],
        },
    }
    original = calendarios._ler
    monkeypatch.setattr(
        calendarios,
        "_ler",
        lambda tribunal, arquivo: tabelas.get(arquivo) or original(tribunal, arquivo),
    )
    cal = carregar_calendario(2030, "0344")
    assert cal.conferido
    assert cal.cobertura_ate == date(2031, 12, 31)
    assert not cal.tem_expediente(date(2031, 2, 3))
    assert not cal.tem_expediente(date(2031, 1, 1))  # feriado federal do ano seguinte


@pytest.mark.parametrize(
    ("foro", "comarca"),
    [("0344", "marilia"), ("0100", "sao_paulo"), ("0020", "sao_paulo")],
)
def test_foros_cadastrados(foro: str, comarca: str) -> None:
    assert comarca_do_foro(foro) == comarca


def test_comarca_sem_feriados_municipais_conferidos_fica_nao_conferida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from assistente.fontes import calendarios

    dados = {
        "2030.toml": {"conferido": True, "eventos": []},
        "comarcas.toml": {
            "foros": {"0344": "marilia", "0100": "sao_paulo"},
            "comarcas": {
                "marilia": {"feriados_municipais_conferidos": True},
                "sao_paulo": {"feriados_municipais_conferidos": False},
            },
        },
    }
    monkeypatch.setattr(calendarios, "_ler", lambda tribunal, arquivo: dados.get(arquivo))
    assert carregar_calendario(2030, "0344").conferido
    assert not carregar_calendario(2030, "0100").conferido


def test_prazo_foro_central_novembro_2026() -> None:
    cal = carregar_calendario(2026, "0100")
    # disponibilizado ter 13/10; 30/10 (Dia do Servidor transferido) e 02/11 sem expediente
    prazo = calcular_prazo(date(2026, 10, 13), 15, cal)
    assert prazo.inicio == date(2026, 10, 15)
    assert prazo.seguranca == date(2026, 10, 23)
    assert prazo.vencimento == date(2026, 11, 6)
