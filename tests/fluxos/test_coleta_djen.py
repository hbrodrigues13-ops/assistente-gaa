"""Testes do fluxo de coleta com DJEN falso e banco temporário."""

from datetime import date, datetime
from pathlib import Path
from typing import Any

from assistente.adaptadores.armazenamento_sqlite import ArmazenamentoSqlite
from assistente.fluxos.coleta_djen import coletar, ler_oabs
from assistente.fontes.tjsp_feriados import FonteIndisponivel


class DjenFalso:
    def __init__(self, itens: list[dict[str, Any]], falhar_para: str | None = None) -> None:
        self.itens = itens
        self.falhar_para = falhar_para
        self.chamadas: list[tuple[str, str, date, date]] = []

    def comunicacoes(self, oab: str, uf: str, inicio: date, fim: date) -> list[dict[str, Any]]:
        self.chamadas.append((oab, uf, inicio, fim))
        if oab == self.falhar_para:
            raise FonteIndisponivel("403 bloqueado")
        return self.itens


def _item(id_: int) -> dict[str, Any]:
    return {"id": id_, "data_disponibilizacao": "2026-11-12", "texto": "x"}


def test_ler_oabs() -> None:
    assert ler_oabs("509289/SP, 177936/SP") == [("509289", "SP"), ("177936", "SP")]


def test_primeira_coleta_e_repeticao_sem_duplicar(tmp_path: Path) -> None:
    banco = ArmazenamentoSqlite(tmp_path / "a.db")
    djen = DjenFalso([_item(1), _item(2)])
    agora = datetime(2026, 11, 16, 7, 30)
    r1 = coletar([("509289", "SP")], djen, banco, agora)
    assert r1.ok and r1.novas == 2
    assert djen.chamadas[0][2:] == (date(2026, 11, 9), date(2026, 11, 16))
    r2 = coletar([("509289", "SP")], djen, banco, datetime(2026, 11, 17, 7, 30))
    assert r2.novas == 0 and r2.repetidas == 2
    assert djen.chamadas[1][2:] == (date(2026, 11, 15), date(2026, 11, 17))


def test_falha_de_uma_oab_nao_avanca_a_data_e_nao_some(tmp_path: Path) -> None:
    banco = ArmazenamentoSqlite(tmp_path / "a.db")
    djen = DjenFalso([_item(1)], falhar_para="177936")
    r = coletar([("509289", "SP"), ("177936", "SP")], djen, banco, datetime(2026, 11, 16, 7, 30))
    assert not r.ok
    assert any("177936/SP" in f and "403" in f for f in r.falhas)
    assert banco.ultima_coleta_ok("509289/SP") == date(2026, 11, 16)
    assert banco.ultima_coleta_ok("177936/SP") is None
    assert "177936/SP" in r.texto()


def test_alerta_de_coleta_atrasada(tmp_path: Path) -> None:
    banco = ArmazenamentoSqlite(tmp_path / "a.db")
    coletar([("509289", "SP")], DjenFalso([]), banco, datetime(2026, 11, 11, 7, 30))
    djen = DjenFalso([], falhar_para="509289")
    r = coletar([("509289", "SP")], djen, banco, datetime(2026, 11, 16, 7, 30))
    assert any("atrasada" in a for a in r.alertas)


def test_resumo_diagnostico_mostra_campos_sem_gravar() -> None:
    from assistente.fluxos.coleta_djen import resumo_diagnostico

    brutos = [{"id": 7, "data_disponibilizacao": "2026-11-12", "texto": "Intimação " + "x" * 300}]
    texto = resumo_diagnostico(brutos)
    assert "1 comunicação" in texto
    assert "data_disponibilizacao" in texto and "id" in texto
    assert len(texto) < 1500


def test_resumo_diagnostico_vazio() -> None:
    from assistente.fluxos.coleta_djen import resumo_diagnostico

    assert "nenhuma comunicação" in resumo_diagnostico([])
