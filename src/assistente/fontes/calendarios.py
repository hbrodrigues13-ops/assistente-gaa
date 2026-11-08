"""Carrega a tabela versionada de calendário forense (somente leitura).

Os dados ficam em `fontes/dados/<tribunal>/<ano>.toml`, versionados no Git.
"""

import tomllib
from datetime import date, timedelta
from importlib import resources
from typing import Any

from assistente.dominio.calendario import (
    Calendario,
    Evento,
    TipoEvento,
    dias_sem_expediente_lei_federal,
)

_PACOTE = "assistente.fontes.dados"


class CalendarioIndisponivel(LookupError):
    """Não há tabela de calendário para o ano ou tribunal pedido."""


def _ler(tribunal: str, arquivo: str) -> dict[str, Any] | None:
    caminho = resources.files(_PACOTE).joinpath(tribunal, arquivo)
    if not caminho.is_file():
        return None
    return tomllib.loads(caminho.read_text(encoding="utf-8"))


def comarca_do_foro(foro: str, tribunal: str = "tjsp") -> str | None:
    dados = _ler(tribunal, "comarcas.toml") or {}
    comarca = dados.get("foros", {}).get(foro)
    return str(comarca) if comarca is not None else None


def _expandir(registro: dict[str, Any]) -> list[Evento]:
    inicio: date = registro["inicio"]
    fim: date = registro.get("fim", inicio)
    if fim < inicio:
        raise ValueError(f"evento com fim antes do início: {registro}")
    eventos = []
    dia = inicio
    while dia <= fim:
        eventos.append(
            Evento(
                data=dia,
                tipo=TipoEvento(registro["tipo"]),
                descricao=registro["descricao"],
                fonte=registro["fonte"],
                comarca=registro.get("comarca"),
            )
        )
        dia += timedelta(days=1)
    return eventos


def carregar_calendario(ano: int, foro: str, tribunal: str = "tjsp") -> Calendario:
    """Calendário do ano, e do seguinte se houver tabela, para o foro do número CNJ.

    Inclui os dias sem expediente por lei federal e a tabela do tribunal.
    Foro sem comarca cadastrada usa só os eventos gerais do tribunal, com aviso
    de calendário não conferido. O prazo que passar do último ano com tabela
    sai com aviso.
    """
    tabelas = []
    for atual in (ano, ano + 1):
        dados = _ler(tribunal, f"{atual}.toml")
        if dados is None:
            break
        tabelas.append((atual, dados))
    if not tabelas:
        raise CalendarioIndisponivel(f"sem tabela de calendário {tribunal.upper()} para {ano}")

    comarca = comarca_do_foro(foro, tribunal)
    eventos: list[Evento] = []
    for atual, dados in tabelas:
        eventos.extend(dias_sem_expediente_lei_federal(atual))
        for registro in dados.get("eventos", []):
            eventos.extend(_expandir(registro))
    conferido = comarca is not None and all(bool(d.get("conferido")) for _, d in tabelas)
    ultimo_ano = tabelas[-1][0]
    return Calendario(
        eventos,
        comarca=comarca,
        conferido=conferido,
        cobertura_ate=date(ultimo_ano, 12, 31),
    )
