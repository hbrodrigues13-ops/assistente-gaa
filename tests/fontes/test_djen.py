"""Testes do cliente do DJEN (sem rede, com httpx.MockTransport)."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from assistente.fontes.djen import ClienteDjen, FormatoInesperado, ler_comunicacao
from assistente.fontes.tjsp_feriados import FonteIndisponivel


def _item(n: int, **extra: Any) -> dict[str, Any]:
    base = {
        "id": 1000 + n,
        "data_disponibilizacao": "2026-11-12",
        "numero_processo": "12345672320258260344",
        "siglaTribunal": "TJSP",
        "texto": f"Intimação {n}",
    }
    base.update(extra)
    return base


def test_le_comunicacao_com_nomes_conhecidos() -> None:
    c = ler_comunicacao(_item(1))
    assert c.id == "1001"
    assert c.disponibilizacao == date(2026, 11, 12)
    assert c.numero_processo == "12345672320258260344"
    assert c.tribunal == "TJSP"
    assert c.texto == "Intimação 1"


def test_le_variacoes_de_nome_e_data_brasileira() -> None:
    bruto = {
        "id": "abc",
        "dataDisponibilizacao": "12/11/2026",
        "numeroprocessocommascara": "1234567-23.2025.8.26.0344",
        "sigla_tribunal": "TJSP",
        "texto": "x",
    }
    c = ler_comunicacao(bruto)
    assert c.disponibilizacao == date(2026, 11, 12)
    assert c.numero_processo == "1234567-23.2025.8.26.0344"


# Formato real da resposta, conferido no --diagnostico de 15/11/2026 (OAB 509289/SP).
# A fixture é sintética: só os nomes dos campos e os tipos vêm da API.
RESPOSTA_REAL = Path(__file__).parent / "dados" / "djen_resposta.json"

CAMPOS_REAIS: dict[str, tuple[type, ...]] = {
    "ativo": (bool,),
    "codigoClasse": (str,),
    "data_cancelamento": (type(None), str),
    "data_disponibilizacao": (str,),
    "datadisponibilizacao": (str,),
    "destinatarioadvogados": (list,),
    "destinatarios": (list,),
    "hash": (str,),
    "id": (int,),
    "idOrgao": (int,),
    "link": (type(None), str),
    "meio": (str,),
    "meiocompleto": (str,),
    "motivo_cancelamento": (type(None), str),
    "nomeClasse": (str,),
    "nomeOrgao": (str,),
    "numeroComunicacao": (int,),
    "numero_processo": (str,),
    "numeroprocessocommascara": (str,),
    "siglaTribunal": (str,),
    "status": (str,),
    "texto": (str,),
    "tipoComunicacao": (str,),
    "tipoDocumento": (str,),
}
CAMPOS_DESTINATARIO = {"comunicacao_id", "nome", "polo"}
CAMPOS_DESTINATARIO_ADVOGADO = {
    "id",
    "comunicacao_id",
    "advogado_id",
    "advogado",
    "created_at",
    "updated_at",
}
CAMPOS_ADVOGADO = {"id", "nome", "numero_oab", "uf_oab"}


def _resposta_real() -> dict[str, Any]:
    corpo: dict[str, Any] = json.loads(RESPOSTA_REAL.read_text(encoding="utf-8"))
    return corpo


def test_fixture_tem_os_campos_e_tipos_do_formato_real() -> None:
    corpo = _resposta_real()
    assert set(corpo) == {"status", "message", "count", "items"}
    for item in corpo["items"]:
        assert set(item) == set(CAMPOS_REAIS)
        for campo, tipos in CAMPOS_REAIS.items():
            assert isinstance(item[campo], tipos), campo
        for destinatario in item["destinatarios"]:
            assert set(destinatario) == CAMPOS_DESTINATARIO
        for intimado in item["destinatarioadvogados"]:
            assert set(intimado) == CAMPOS_DESTINATARIO_ADVOGADO
            assert set(intimado["advogado"]) == CAMPOS_ADVOGADO


def test_le_comunicacao_no_formato_real() -> None:
    bruto = _resposta_real()["items"][0]
    c = ler_comunicacao(bruto)
    assert c.id == "900000001"  # id vem como inteiro; a chave de idempotência é texto
    assert c.disponibilizacao == date(2026, 11, 13)  # data_disponibilizacao (ISO) tem preferência
    assert c.numero_processo == "12345672320258260344"  # numero_processo vem sem máscara
    assert c.tribunal == "TJSP"
    assert c.texto.startswith("Texto fictício")
    assert c.bruto is bruto  # o bruto guarda o resto: órgão, classe, destinatários, status


def test_le_comunicacao_real_sem_link() -> None:
    bruto = _resposta_real()["items"][1]
    assert bruto["link"] is None
    assert ler_comunicacao(bruto).tribunal == "TJPR"


def test_cliente_le_o_envelope_real() -> None:
    esperas: list[float] = []
    vistas: list[httpx.Request] = []
    cliente = _cliente([httpx.Response(200, json=_resposta_real())], esperas, vistas)
    itens = cliente.comunicacoes("509289", "SP", date(2026, 11, 9), date(2026, 11, 16))
    assert [ler_comunicacao(i).id for i in itens] == ["900000001", "900000002"]


@pytest.mark.parametrize("faltando", ["id", "data_disponibilizacao"])
def test_formato_inesperado_para_com_erro(faltando: str) -> None:
    bruto = _item(1)
    del bruto[faltando]
    with pytest.raises(FormatoInesperado):
        ler_comunicacao(bruto)


def _cliente(paginas: list[httpx.Response], esperas: list[float], vistas: list[httpx.Request]):
    fila = list(paginas)

    def responder(req: httpx.Request) -> httpx.Response:
        vistas.append(req)
        return fila.pop(0)

    http = httpx.Client(transport=httpx.MockTransport(responder))
    return ClienteDjen(http, tentativas=3, esperar=esperas.append)


def test_pagina_ate_vir_menos_que_100() -> None:
    esperas: list[float] = []
    vistas: list[httpx.Request] = []
    pagina1 = {"status": "success", "items": [_item(n) for n in range(100)]}
    pagina2 = {"status": "success", "items": [_item(n) for n in range(100, 103)]}
    cliente = _cliente(
        [httpx.Response(200, json=pagina1), httpx.Response(200, json=pagina2)], esperas, vistas
    )
    itens = cliente.comunicacoes("509289", "SP", date(2026, 11, 9), date(2026, 11, 16))
    assert len(itens) == 103
    params = vistas[0].url.params
    assert params["numeroOab"] == "509289"
    assert params["ufOab"] == "SP"
    assert params["dataDisponibilizacaoInicio"] == "2026-11-09"
    assert params["dataDisponibilizacaoFim"] == "2026-11-16"
    assert params["itensPorPagina"] == "100"
    assert [r.url.params["pagina"] for r in vistas] == ["1", "2"]


def test_429_espera_um_minuto_e_tenta_de_novo() -> None:
    esperas: list[float] = []
    vistas: list[httpx.Request] = []
    cliente = _cliente(
        [httpx.Response(429), httpx.Response(200, json={"items": [_item(1)]})], esperas, vistas
    )
    assert len(cliente.comunicacoes("509289", "SP", date(2026, 11, 9), date(2026, 11, 16))) == 1
    assert esperas == [60.0]


def test_bloqueio_por_pais_e_falha_explicita() -> None:
    esperas: list[float] = []
    vistas: list[httpx.Request] = []
    cliente = _cliente([httpx.Response(403, text="CloudFront")] * 3, esperas, vistas)
    with pytest.raises(FonteIndisponivel, match="403"):
        cliente.comunicacoes("509289", "SP", date(2026, 11, 9), date(2026, 11, 16))


def test_resposta_sem_items_e_formato_inesperado() -> None:
    esperas: list[float] = []
    vistas: list[httpx.Request] = []
    cliente = _cliente([httpx.Response(200, json={"outra": []})], esperas, vistas)
    with pytest.raises(FormatoInesperado):
        cliente.comunicacoes("509289", "SP", date(2026, 11, 9), date(2026, 11, 16))


# Formato real da resposta do DJEN, conferido na primeira coleta (15/11/2026, 410
# comunicações). Valores fictícios; só os nomes e os tipos dos campos são reais.
COMUNICACAO_REAL = {
    "id": 412345678,
    "data_disponibilizacao": "2026-11-09",
    "datadisponibilizacao": "09/11/2026",
    "siglaTribunal": "TJSP",
    "tipoComunicacao": "Intimação",
    "nomeOrgao": "1ª Vara Cível",
    "idOrgao": 1234,
    "texto": "Intimação fictícia para teste.",
    "numero_processo": "12345672320258260344",
    "numeroprocessocommascara": "1234567-23.2025.8.26.0344",
    "meio": "D",
    "meiocompleto": "Diário de Justiça Eletrônico Nacional",
    "link": "https://exemplo.invalido/documento",
    "tipoDocumento": "Despacho",
    "nomeClasse": "EXECUÇÃO DE TÍTULO EXTRAJUDICIAL",
    "codigoClasse": "12154",
    "numeroComunicacao": 1,
    "hash": "abc123",
    "status": "P",
    "ativo": True,
    "data_cancelamento": None,
    "motivo_cancelamento": None,
    "destinatarios": [{"nome": "PARTE FICTÍCIA", "polo": "A", "comunicacao_id": 412345678}],
    "destinatarioadvogados": [
        {
            "id": 1,
            "comunicacao_id": 412345678,
            "advogado_id": 2,
            "created_at": "2026-11-08T10:00:00",
            "updated_at": "2026-11-08T10:00:00",
            "advogado": {
                "id": 2,
                "nome": "ADVOGADO FICTÍCIO",
                "numero_oab": "999999",
                "uf_oab": "SP",
            },
        }
    ],
}


def test_formato_real_do_djen() -> None:
    c = ler_comunicacao(COMUNICACAO_REAL)
    assert c.id == "412345678"  # id numérico vira texto
    assert c.disponibilizacao == date(2026, 11, 9)
    assert c.numero_processo == "12345672320258260344"  # só dígitos, como no número CNJ
    assert c.tribunal == "TJSP"
    assert c.texto == "Intimação fictícia para teste."
    assert c.bruto is COMUNICACAO_REAL
