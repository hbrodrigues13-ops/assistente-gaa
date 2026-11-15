"""Testes do cliente do DJEN (sem rede, com httpx.MockTransport)."""

from datetime import date
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
