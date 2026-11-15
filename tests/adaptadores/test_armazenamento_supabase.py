"""Testes do armazenamento no Supabase com a API simulada (httpx.MockTransport)."""

import json
from datetime import date, datetime
from typing import Any

import httpx
import pytest

from assistente.adaptadores.armazenamento_supabase import ArmazenamentoSupabase
from assistente.dominio.comunicacao import Comunicacao
from assistente.fontes.erros import FonteIndisponivel


class SupabaseFalso:
    """Imita o PostgREST: tabelas em memória, ON CONFLICT DO NOTHING e filtros simples."""

    def __init__(self) -> None:
        self.comunicacoes: dict[str, dict[str, Any]] = {}
        self.coletas: list[dict[str, Any]] = []
        self.cabecalhos: list[httpx.Headers] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.cabecalhos.append(req.headers)
        tabela = req.url.path.rsplit("/", 1)[-1]
        if req.method == "POST" and tabela == "comunicacoes":
            assert req.url.params["on_conflict"] == "id"
            assert "resolution=ignore-duplicates" in req.headers["prefer"]
            inseridas = []
            for linha in json.loads(req.content):
                if linha["id"] not in self.comunicacoes:
                    self.comunicacoes[linha["id"]] = linha
                    inseridas.append({"id": linha["id"]})
            return httpx.Response(201, json=inseridas)
        if req.method == "POST" and tabela == "coletas":
            self.coletas.append(json.loads(req.content))
            return httpx.Response(201)
        if req.method == "GET" and tabela == "coletas":
            oab = req.url.params["oab"].removeprefix("eq.")
            fins = sorted(
                (c["fim"] for c in self.coletas if c["oab"] == oab and c["erro"] is None),
                reverse=True,
            )
            return httpx.Response(200, json=[{"fim": f} for f in fins[:1]])
        return httpx.Response(404)


def _banco(falso: SupabaseFalso, chave: str = "sb_secret_teste") -> ArmazenamentoSupabase:
    http = httpx.Client(transport=httpx.MockTransport(falso))
    return ArmazenamentoSupabase("https://exemplo.supabase.co", chave, http)


def _c(id_: str) -> Comunicacao:
    return Comunicacao(id_, date(2026, 11, 12), "123", "TJSP", "texto", {"id": id_})


def test_salva_e_ignora_repetidas_inclusive_no_mesmo_lote() -> None:
    falso = SupabaseFalso()
    banco = _banco(falso)
    assert banco.salvar("509289/SP", [_c("1"), _c("2"), _c("2")]) == (2, 1)
    assert banco.salvar("509289/SP", [_c("2"), _c("3")]) == (1, 1)
    assert set(falso.comunicacoes) == {"1", "2", "3"}
    assert falso.comunicacoes["1"]["bruto"] == {"id": "1"}
    assert falso.comunicacoes["1"]["disponibilizacao"] == "2026-11-12"


def test_lote_vazio_nao_chama_a_api() -> None:
    falso = SupabaseFalso()
    assert _banco(falso).salvar("509289/SP", []) == (0, 0)
    assert falso.cabecalhos == []


def test_registra_coletas_e_devolve_a_ultima_bem_sucedida() -> None:
    falso = SupabaseFalso()
    banco = _banco(falso)
    agora = datetime(2026, 11, 16, 7, 30)
    assert banco.ultima_coleta_ok("509289/SP") is None
    banco.registrar_coleta("509289/SP", date(2026, 11, 9), date(2026, 11, 13), agora, None)
    banco.registrar_coleta("509289/SP", date(2026, 11, 12), date(2026, 11, 16), agora, "falhou")
    assert banco.ultima_coleta_ok("509289/SP") == date(2026, 11, 13)


def test_chave_nova_vai_so_no_apikey_e_chave_jwt_tambem_no_bearer() -> None:
    falso = SupabaseFalso()
    _banco(falso, "sb_secret_abc").ultima_coleta_ok("x")
    assert falso.cabecalhos[-1]["apikey"] == "sb_secret_abc"
    assert "authorization" not in falso.cabecalhos[-1]
    _banco(falso, "eyJhbGciOi.teste").ultima_coleta_ok("x")
    assert falso.cabecalhos[-1]["authorization"] == "Bearer eyJhbGciOi.teste"


def test_erro_do_supabase_e_falha_explicita_sem_mostrar_a_chave() -> None:
    def recusar(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid API key"})

    banco = ArmazenamentoSupabase(
        "https://exemplo.supabase.co",
        "sb_secret_nao_vazar",
        httpx.Client(transport=httpx.MockTransport(recusar)),
    )
    with pytest.raises(FonteIndisponivel) as erro:
        banco.ultima_coleta_ok("509289/SP")
    assert "401" in str(erro.value)
    assert "sb_secret_nao_vazar" not in str(erro.value)
