"""Testes do filtro de escopo e da regra de prazo do Fluxo 1."""

import pytest

from assistente.dominio.escopo import motivo_fora_de_escopo
from assistente.dominio.regra_prazo import definir_prazo, trecho_confere


@pytest.mark.parametrize(
    ("tribunal", "processo", "tipo", "ativo", "cancelamento", "esperado"),
    [
        ("TJSP", "12345672320258260344", "Intimação", True, None, None),
        ("TRT15", "00012345620255150001", "Intimação", True, None, "trabalhista"),
        ("TST", None, "Intimação", True, None, "trabalhista"),
        ("TJSP", "00001000720235150001", "Intimação", True, None, "trabalhista"),  # J=5
        ("TJSP", "12345672320258260344", "Intimação", False, None, "cancelada"),
        ("TJSP", "12345672320258260344", "Intimação", True, "2026-11-10", "cancelada"),
        ("TJSP", "12345672320258260344", "Lista de distribuição", True, None, "sem prazo"),
        ("TJSP", "12345672320258260344", "Edital", True, None, None),
    ],
)
def test_motivo_fora_de_escopo(
    tribunal: str,
    processo: str | None,
    tipo: str,
    ativo: bool,
    cancelamento: str | None,
    esperado: str | None,
) -> None:
    motivo = motivo_fora_de_escopo(tribunal, processo, tipo, ativo, cancelamento)
    if esperado is None:
        assert motivo is None
    else:
        assert motivo is not None and esperado in motivo


def test_trecho_confere_ignora_espacos_e_maiusculas() -> None:
    texto = "Manifeste-se o exequente,   no prazo de 15 (quinze) dias, sobre a certidão."
    assert trecho_confere(texto, "no prazo de 15 (QUINZE) dias")
    assert not trecho_confere(texto, "no prazo de 10 dias")
    assert not trecho_confere(texto, "")


def test_prazo_fixado_no_ato_com_trecho_confirmado() -> None:
    d = definir_prazo("intimacao_para_andamento", 15, trecho_confirmado=True)
    assert d.dias == 15 and "fixado" in d.fundamento and d.avisos == ()


def test_prazo_fixado_sem_trecho_confirmado_nao_vale() -> None:
    d = definir_prazo("intimacao_para_andamento", 15, trecho_confirmado=False)
    assert d.dias == 5
    assert "218" in d.fundamento
    assert any("não confirmado" in a for a in d.avisos)


def test_sentenca_adota_embargos_de_declaracao() -> None:
    d = definir_prazo("sentenca", None, trecho_confirmado=False)
    assert d.dias == 5 and "1.023" in d.fundamento
    assert any("1.003" in a for a in d.avisos)


def test_embargos_a_execucao() -> None:
    d = definir_prazo("embargos", None, trecho_confirmado=False)
    assert d.dias == 15 and "920" in d.fundamento


def test_mera_ciencia_convencao_interna() -> None:
    d = definir_prazo("mera_ciencia", None, trecho_confirmado=False)
    assert d.dias == 3 and "convenção interna" in d.fundamento


def test_sem_prazo_identificado_usa_218_e_avisa() -> None:
    d = definir_prazo("citacao_negativa", None, trecho_confirmado=False)
    assert d.dias == 5 and "218, § 3º" in d.fundamento
    assert any("conferir" in a for a in d.avisos)


def test_prazo_fixado_maior_que_legal_da_sentenca_nao_vence_o_conservador() -> None:
    # sentença com "apelação em 15 dias" citada: ainda assim 5 (embargos de declaração)
    d = definir_prazo("sentenca", 15, trecho_confirmado=True)
    assert d.dias == 5
