"""Armazenamento local das comunicações e das coletas (SQLite, só biblioteca padrão).

Usado nos testes e como alternativa sem rede; em produção a coleta grava no Supabase
(decisão 0005). O arquivo fica sempre fora do repositório.
"""

import json
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from assistente.dominio.comunicacao import Comunicacao

ESQUEMA = """
CREATE TABLE IF NOT EXISTS comunicacoes (
    id TEXT PRIMARY KEY,
    oab TEXT NOT NULL,
    disponibilizacao TEXT NOT NULL,
    numero_processo TEXT,
    tribunal TEXT,
    bruto TEXT NOT NULL,
    coletada_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coletas (
    oab TEXT NOT NULL,
    inicio TEXT NOT NULL,
    fim TEXT NOT NULL,
    executada_em TEXT NOT NULL,
    erro TEXT
);
"""


class ArmazenamentoSqlite:
    def __init__(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(caminho)
        self._con.executescript(ESQUEMA)

    def salvar(self, oab: str, comunicacoes: Iterable[Comunicacao]) -> tuple[int, int]:
        """Grava as comunicações novas e devolve (novas, repetidas)."""
        novas = repetidas = 0
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con:
            for c in comunicacoes:
                cursor = self._con.execute(
                    "INSERT OR IGNORE INTO comunicacoes VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        c.id,
                        oab,
                        c.disponibilizacao.isoformat(),
                        c.numero_processo,
                        c.tribunal,
                        json.dumps(c.bruto, ensure_ascii=False),
                        agora,
                    ),
                )
                if cursor.rowcount:
                    novas += 1
                else:
                    repetidas += 1
        return novas, repetidas

    def registrar_coleta(
        self, oab: str, inicio: date, fim: date, executada_em: datetime, erro: str | None
    ) -> None:
        with self._con:
            self._con.execute(
                "INSERT INTO coletas VALUES (?, ?, ?, ?, ?)",
                (oab, inicio.isoformat(), fim.isoformat(), executada_em.isoformat(), erro),
            )

    def ultima_coleta_ok(self, oab: str) -> date | None:
        linha = self._con.execute(
            "SELECT MAX(fim) FROM coletas WHERE oab = ? AND erro IS NULL", (oab,)
        ).fetchone()
        return date.fromisoformat(linha[0]) if linha and linha[0] else None

    def total_comunicacoes(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM comunicacoes").fetchone()[0])
