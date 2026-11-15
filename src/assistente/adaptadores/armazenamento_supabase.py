"""Armazenamento das comunicações e das coletas no Supabase (API REST/PostgREST).

Projeto: assistente-gaa, região sa-east-1 (São Paulo). Tabelas com RLS ligado
e sem políticas: só a chave secreta (service_role ou sb_secret_...) acessa.
A chave fica no .env do computador de Henrique; nunca em código ou log
(princípio 7). Esquema: supabase/migrations/.
"""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import httpx

from assistente.dominio.comunicacao import Comunicacao
from assistente.fontes.erros import FonteIndisponivel


class ArmazenamentoSupabase:
    def __init__(self, url: str, chave: str, cliente_http: httpx.Client | None = None) -> None:
        self._base = url.rstrip("/") + "/rest/v1"
        cabecalhos = {"apikey": chave, "Content-Type": "application/json"}
        if chave.startswith("eyJ"):  # chave legada em JWT também vai no Authorization
            cabecalhos["Authorization"] = f"Bearer {chave}"
        self._http = cliente_http or httpx.Client(timeout=60)
        self._cabecalhos = cabecalhos

    def _requisitar(self, metodo: str, tabela: str, **kwargs: Any) -> httpx.Response:
        cabecalhos = {**self._cabecalhos, **kwargs.pop("headers", {})}
        try:
            resposta = self._http.request(
                metodo, f"{self._base}/{tabela}", headers=cabecalhos, **kwargs
            )
        except httpx.HTTPError as erro:
            raise FonteIndisponivel(
                f"Supabase {tabela}: erro de conexão ({type(erro).__name__})"
            ) from None
        if resposta.status_code >= 400:
            raise FonteIndisponivel(
                f"Supabase {tabela}: HTTP {resposta.status_code} {resposta.text[:200]}"
            )
        return resposta

    def salvar(self, oab: str, comunicacoes: Iterable[Comunicacao]) -> tuple[int, int]:
        """Grava as comunicações novas e devolve (novas, repetidas)."""
        lista = list(comunicacoes)
        if not lista:
            return 0, 0
        unicas: dict[str, Comunicacao] = {}
        for c in lista:
            unicas.setdefault(c.id, c)
        linhas = [
            {
                "id": c.id,
                "oab": oab,
                "disponibilizacao": c.disponibilizacao.isoformat(),
                "numero_processo": c.numero_processo,
                "tribunal": c.tribunal,
                "bruto": c.bruto,
            }
            for c in unicas.values()
        ]
        resposta = self._requisitar(
            "POST",
            "comunicacoes",
            params={"on_conflict": "id", "select": "id"},
            headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
            json=linhas,
        )
        novas = len(resposta.json())
        return novas, len(lista) - novas

    def registrar_coleta(
        self, oab: str, inicio: date, fim: date, executada_em: datetime, erro: str | None
    ) -> None:
        self._requisitar(
            "POST",
            "coletas",
            headers={"Prefer": "return=minimal"},
            json={
                "oab": oab,
                "inicio": inicio.isoformat(),
                "fim": fim.isoformat(),
                "executada_em": executada_em.isoformat(),
                "erro": erro,
            },
        )

    def ultima_coleta_ok(self, oab: str) -> date | None:
        resposta = self._requisitar(
            "GET",
            "coletas",
            params={
                "select": "fim",
                "oab": f"eq.{oab}",
                "erro": "is.null",
                "order": "fim.desc",
                "limit": "1",
            },
        )
        linhas = resposta.json()
        return date.fromisoformat(linhas[0]["fim"]) if linhas else None
