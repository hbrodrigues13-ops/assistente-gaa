"""Testes da numeração única de processos (Resolução CNJ 65/2008).

Números sintéticos, com dígito verificador calculado por dois métodos
independentes (cálculo direto e cálculo encadeado do módulo 97).
"""

import pytest

from assistente.dominio.numero_cnj import (
    NumeroCnj,
    NumeroCnjInvalido,
    calcular_digito_verificador,
    interpretar_numero_cnj,
    numero_cnj_valido,
)

VALIDOS = [
    ("0000001-17.2099.8.26.0001", "00000011720998260001"),
    ("1234567-23.2025.8.26.0344", "12345672320258260344"),
    ("0001234-47.2026.8.26.0344", "00012344720268260344"),
    ("5000123-61.2024.4.04.7100", "50001236120244047100"),
    ("0000100-07.2023.5.15.0001", "00001000720235150001"),
]


@pytest.mark.parametrize(("formatado", "digitos"), VALIDOS)
def test_interpreta_numero_formatado(formatado: str, digitos: str) -> None:
    numero = interpretar_numero_cnj(formatado)
    assert numero.digitos == digitos
    assert numero.formatado == formatado


@pytest.mark.parametrize(("formatado", "digitos"), VALIDOS)
def test_interpreta_numero_so_com_digitos(formatado: str, digitos: str) -> None:
    assert interpretar_numero_cnj(digitos).formatado == formatado


def test_separa_os_segmentos() -> None:
    numero = interpretar_numero_cnj("1234567-23.2025.8.26.0344")
    assert numero == NumeroCnj(
        sequencial="1234567",
        digito="23",
        ano="2025",
        justica="8",
        tribunal="26",
        origem="0344",
    )


def test_identifica_tjsp_e_foro_de_origem() -> None:
    numero = interpretar_numero_cnj("1234567-23.2025.8.26.0344")
    assert numero.justica_estadual
    assert numero.tribunal == "26"
    assert numero.origem == "0344"


def test_aceita_espacos_nas_pontas() -> None:
    assert numero_cnj_valido("  1234567-23.2025.8.26.0344\n")


@pytest.mark.parametrize(
    ("sequencial", "ano", "justica", "tribunal", "origem", "esperado"),
    [
        ("0000001", "2099", "8", "26", "0001", "17"),
        ("1234567", "2025", "8", "26", "0344", "23"),
        ("0000100", "2023", "5", "15", "0001", "07"),
    ],
)
def test_calcula_digito_verificador(
    sequencial: str, ano: str, justica: str, tribunal: str, origem: str, esperado: str
) -> None:
    assert calcular_digito_verificador(sequencial, ano, justica, tribunal, origem) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        "1234567-24.2025.8.26.0344",  # dígito verificador errado
        "1234567-23.2025.8.26.0345",  # foro trocado
        "1234567-23.2024.8.26.0344",  # ano trocado
        "1234567-23.2025.8.26.034",  # segmento curto
        "123456723202582603440",  # 21 dígitos
        "1234567.23.2025.8.26.0344",  # separador errado
        "",
        "processo 1234567-23.2025.8.26.0344",
    ],
)
def test_rejeita_numero_invalido(entrada: str) -> None:
    assert not numero_cnj_valido(entrada)
    with pytest.raises(NumeroCnjInvalido):
        interpretar_numero_cnj(entrada)


def test_erro_e_value_error() -> None:
    assert issubclass(NumeroCnjInvalido, ValueError)


def test_erro_informa_o_digito_esperado() -> None:
    with pytest.raises(NumeroCnjInvalido, match="esperado 23"):
        interpretar_numero_cnj("1234567-24.2025.8.26.0344")
