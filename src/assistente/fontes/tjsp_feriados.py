"""Conferência do calendário com a consulta oficial de feriados do TJSP (somente leitura).

Fonte: página "Expediente Forense/Suspensão de Prazo" do TJSP
(www.tjsp.jus.br/CanaisComunicacao/Feriados/ExpedienteForense), que consulta
por município os feriados e as suspensões de cada ano.

A conferência nunca altera a tabela versionada: ela produz um relatório de
divergências e o trecho TOML sugerido, para Henrique aprovar (princípio 2).
Só dias úteis entram na comparação; feriado em fim de semana não muda prazo.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

import httpx

from assistente.dominio.calendario import SEM_EXPEDIENTE, Calendario, em_recesso_art220
from assistente.fontes.calendarios import ler_dados

URL_BASE = "https://www.tjsp.jus.br/CanaisComunicacao/Feriados"
MARCA_GERAL = "PROVIMENTO"
MARCA_COMUNICADO = "COMUNICADO"


class FonteIndisponivel(RuntimeError):
    """A consulta do TJSP falhou mesmo depois das novas tentativas."""


class ConsultaTjsp(Protocol):
    def feriados(self, municipio: str, ano: int) -> list[dict[str, Any]]: ...

    def suspensoes(self, municipio: str, ano: int) -> list[dict[str, Any]]: ...


class ClienteTjsp:
    """Cliente real. Nova tentativa com espera; persistindo a falha, levanta FonteIndisponivel."""

    def __init__(
        self,
        cliente_http: httpx.Client | None = None,
        tentativas: int = 3,
        esperar: Callable[[float], None] = time.sleep,
        pausa: float = 0.0,
    ) -> None:
        self._http = cliente_http or httpx.Client(timeout=40)
        self._tentativas = tentativas
        self._esperar = esperar
        self._pausa = pausa

    def _consultar(self, recurso: str, municipio: str, ano: int) -> list[dict[str, Any]]:
        params = {"nomeMunicipio": municipio, "codigoMunicipio": "0", "ano": str(ano)}
        ultimo_erro: Exception | None = None
        vazia = False
        for tentativa in range(self._tentativas):
            if self._pausa:
                self._esperar(self._pausa)
            try:
                resposta = self._http.get(f"{URL_BASE}/{recurso}", params=params)
                resposta.raise_for_status()
                dados = resposta.json().get("data")
                if not isinstance(dados, list):
                    raise ValueError("resposta sem lista 'data'")
                if dados:
                    return dados
                # Lista vazia pode ser limitação momentânea do TJSP: tenta de novo.
                vazia = True
            except (httpx.HTTPError, ValueError) as erro:
                ultimo_erro = erro
            if tentativa + 1 < self._tentativas:
                self._esperar(2.0 * 2**tentativa)
        if vazia and ultimo_erro is None:
            return []
        raise FonteIndisponivel(f"TJSP {recurso} {municipio}/{ano}: {ultimo_erro}")

    def feriados(self, municipio: str, ano: int) -> list[dict[str, Any]]:
        return self._consultar("PesquisarFeriados", municipio, ano)

    def suspensoes(self, municipio: str, ano: int) -> list[dict[str, Any]]:
        return self._consultar("PesquisarSuspensoes", municipio, ano)


@dataclass(frozen=True, slots=True)
class FeriadoOficial:
    data: date
    descricao: str
    municipal: bool


@dataclass(frozen=True, slots=True)
class SuspensaoOficial:
    periodo: str
    inicio: date
    fim: date
    descricao: str
    de_vara: bool

    def dias(self) -> list[date]:
        return [self.inicio + timedelta(days=n) for n in range((self.fim - self.inicio).days + 1)]


@dataclass(frozen=True, slots=True)
class EventosOficiais:
    feriados: tuple[FeriadoOficial, ...]
    suspensoes_gerais: tuple[SuspensaoOficial, ...]
    suspensoes_de_vara: tuple[SuspensaoOficial, ...]

    @property
    def sem_expediente(self) -> frozenset[date]:
        dias = {f.data for f in self.feriados}
        for s in self.suspensoes_gerais:
            if "RECESSO" in s.descricao.upper():
                dias.update(s.dias())
        return frozenset(dias)


@dataclass(frozen=True, slots=True)
class Divergencia:
    data: date
    descricao: str
    municipal: bool = False


@dataclass(frozen=True, slots=True)
class ResultadoConferencia:
    municipio: str
    ano: int
    faltando_na_tabela: tuple[Divergencia, ...]
    sobrando_na_tabela: tuple[Divergencia, ...]
    suspensoes_de_vara: tuple[SuspensaoOficial, ...]
    consulta_incompleta: bool = False

    @property
    def sem_divergencia(self) -> bool:
        return (
            not self.consulta_incompleta
            and not self.faltando_na_tabela
            and not self.sobrando_na_tabela
        )

    def toml_sugerido(self, comarca: str) -> str:
        blocos = []
        for d in self.faltando_na_tabela:
            tipo = "suspensao_expediente" if "SUSPENSÃO" in d.descricao.upper() else "feriado"
            linhas = [
                "[[eventos]]",
                f"inicio = {d.data.isoformat()}",
                f'tipo = "{tipo}"',
                f'descricao = "{d.descricao}"',
                f'fonte = "TJSP, Expediente Forense, consulta de {date.today():%d/%m/%Y}"',
            ]
            if d.municipal:
                linhas.append(f'comarca = "{comarca}"')
            blocos.append("\n".join(linhas))
        return "\n\n".join(blocos)

    def relatorio(self) -> str:
        linhas = [f"## {self.municipio} ({self.ano})", ""]
        if self.consulta_incompleta:
            linhas += [
                "Atenção: o TJSP devolveu lista vazia de feriados ou de suspensões.",
                "Nada foi dado como sobrando na tabela; conferir manualmente.",
                "",
            ]
        if self.sem_divergencia:
            linhas.append("Tabela confere com o TJSP em todos os dias úteis.")
        for titulo, itens in (
            ("No TJSP e fora da tabela", self.faltando_na_tabela),
            ("Na tabela e fora do TJSP", self.sobrando_na_tabela),
        ):
            if itens:
                linhas.append(f"{titulo}:")
                linhas += [f"- {d.data:%d/%m/%Y}: {d.descricao}" for d in itens]
                linhas.append("")
        if self.suspensoes_de_vara:
            linhas.append("Suspensões restritas a varas (não entram na tabela da comarca):")
            linhas += [f"- {s.periodo}: {s.descricao[:300]}" for s in self.suspensoes_de_vara]
        return "\n".join(linhas).rstrip() + "\n"


def _data(texto: str) -> date:
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def _suspensao(registro: dict[str, Any]) -> SuspensaoOficial:
    periodo = str(registro["Data"]).strip()
    partes = [p.strip() for p in periodo.split(" a ")]
    inicio = _data(partes[0])
    fim = _data(partes[-1])
    descricao = " ".join(str(registro.get("Descricao", "")).split())
    return SuspensaoOficial(
        periodo=periodo,
        inicio=inicio,
        fim=fim,
        descricao=descricao,
        de_vara=MARCA_COMUNICADO in descricao.upper(),
    )


def eventos_oficiais(tjsp: ConsultaTjsp, municipio: str, ano: int) -> EventosOficiais:
    feriados = tuple(
        FeriadoOficial(
            data=_data(str(r["Data"])),
            descricao=" ".join(str(r.get("Descricao", "")).split()),
            municipal=MARCA_GERAL not in str(r.get("Descricao", "")).upper(),
        )
        for r in tjsp.feriados(municipio, ano)
    )
    suspensoes = [_suspensao(r) for r in tjsp.suspensoes(municipio, ano)]
    return EventosOficiais(
        feriados=feriados,
        suspensoes_gerais=tuple(s for s in suspensoes if not s.de_vara),
        suspensoes_de_vara=tuple(s for s in suspensoes if s.de_vara),
    )


def municipio_da_comarca(comarca: str, tribunal: str = "tjsp") -> str | None:
    dados = ler_dados(tribunal, "comarcas.toml") or {}
    nome = dados.get("comarcas", {}).get(comarca, {}).get("municipio")
    return str(nome) if nome else None


def _dias_sem_expediente_na_tabela(calendario: Calendario, ano: int) -> dict[date, str]:
    dias: dict[date, str] = {}
    for evento in calendario.eventos:
        if evento.data.year == ano and evento.tipo in SEM_EXPEDIENTE:
            dias.setdefault(evento.data, evento.descricao)
    return dias


def conferir_calendario(
    tjsp: ConsultaTjsp, calendario: Calendario, municipio: str, ano: int
) -> ResultadoConferencia:
    oficiais = eventos_oficiais(tjsp, municipio, ano)
    na_tabela = _dias_sem_expediente_na_tabela(calendario, ano)
    incompleta = not oficiais.feriados or not (
        oficiais.suspensoes_gerais or oficiais.suspensoes_de_vara
    )

    descricao_oficial: dict[date, tuple[str, bool]] = {}
    for f in oficiais.feriados:
        descricao_oficial.setdefault(f.data, (f.descricao, f.municipal))
    for s in oficiais.suspensoes_gerais:
        for dia in s.dias():
            if "RECESSO" in s.descricao.upper():
                descricao_oficial.setdefault(dia, (s.descricao, False))

    faltando = [
        Divergencia(dia, descricao, municipal)
        for dia, (descricao, municipal) in sorted(descricao_oficial.items())
        if dia.weekday() < 5 and dia not in na_tabela
    ]
    # Suspensão geral de prazos fora do recesso do art. 220 também precisa entrar.
    for s in oficiais.suspensoes_gerais:
        if "RECESSO" in s.descricao.upper():
            continue
        for dia in s.dias():
            if dia.weekday() < 5 and not em_recesso_art220(dia) and dia not in na_tabela:
                faltando.append(Divergencia(dia, f"Suspensão de prazos: {s.descricao}"))

    # Com consulta incompleta, ausência no TJSP não prova nada: não acusa sobra.
    sobrando = (
        []
        if incompleta
        else [
            Divergencia(dia, descricao)
            for dia, descricao in sorted(na_tabela.items())
            if dia.weekday() < 5 and dia not in oficiais.sem_expediente
        ]
    )
    return ResultadoConferencia(
        municipio=municipio,
        ano=ano,
        faltando_na_tabela=tuple(sorted(faltando, key=lambda d: d.data)),
        sobrando_na_tabela=tuple(sobrando),
        suspensoes_de_vara=oficiais.suspensoes_de_vara,
        consulta_incompleta=incompleta,
    )
