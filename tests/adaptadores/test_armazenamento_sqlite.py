"""Testes do armazenamento local (SQLite em pasta temporária)."""

from datetime import date, datetime
from pathlib import Path

from assistente.adaptadores.armazenamento_sqlite import ArmazenamentoSqlite
from assistente.dominio.comunicacao import Comunicacao


def _c(id_: str) -> Comunicacao:
    return Comunicacao(id_, date(2026, 11, 12), "123", "TJSP", "texto", {"id": id_})


def test_salva_e_ignora_repetidas(tmp_path: Path) -> None:
    banco = ArmazenamentoSqlite(tmp_path / "a.db")
    assert banco.salvar("509289/SP", [_c("1"), _c("2")]) == (2, 0)
    assert banco.salvar("509289/SP", [_c("2"), _c("3")]) == (1, 1)
    assert banco.total_comunicacoes() == 3


def test_registra_coletas_e_devolve_a_ultima_bem_sucedida(tmp_path: Path) -> None:
    banco = ArmazenamentoSqlite(tmp_path / "a.db")
    assert banco.ultima_coleta_ok("509289/SP") is None
    agora = datetime(2026, 11, 16, 7, 30)
    banco.registrar_coleta("509289/SP", date(2026, 11, 9), date(2026, 11, 13), agora, None)
    banco.registrar_coleta("509289/SP", date(2026, 11, 12), date(2026, 11, 16), agora, "falhou")
    assert banco.ultima_coleta_ok("509289/SP") == date(2026, 11, 13)
    assert banco.ultima_coleta_ok("177936/SP") is None


def test_persiste_entre_aberturas(tmp_path: Path) -> None:
    caminho = tmp_path / "a.db"
    ArmazenamentoSqlite(caminho).salvar("509289/SP", [_c("1")])
    assert ArmazenamentoSqlite(caminho).total_comunicacoes() == 1
