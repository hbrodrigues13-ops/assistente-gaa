"""Cliente da API de comunicações do DJEN (Comunica PJe/CNJ), somente leitura.

Endpoint e parâmetros: docs/apis/consulta-processos.md. A API recusa acesso
de fora do Brasil (403 do CloudFront): a coleta roda no computador de Henrique.

Os nomes dos campos da resposta foram conferidos na API real em 15/11/2026
(--diagnostico com a OAB 509289/SP) e estão fixados em
tests/fontes/dados/djen_resposta.json: id (inteiro), data_disponibilizacao
(AAAA-MM-DD), numero_processo (20 dígitos, sem máscara), siglaTribunal e texto.
O leitor ainda aceita variações de nome e, sem identificador ou data de
disponibilização, para com FormatoInesperado em vez de seguir em silêncio.
"""

import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import httpx

from assistente.dominio.comunicacao import Comunicacao
from assistente.fontes.erros import FonteIndisponivel

URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
ITENS_POR_PAGINA = 100  # a API só aceita 5 ou 100
LIMITE_PAGINAS = 100  # 100 x 100 = teto de 10.000 resultados por pesquisa
ESPERA_429 = 60.0

CAMPOS_ID = ("id",)
CAMPOS_DATA = ("data_disponibilizacao", "dataDisponibilizacao", "datadisponibilizacao")
CAMPOS_PROCESSO = ("numero_processo", "numeroprocessocommascara", "numeroProcesso")
CAMPOS_TRIBUNAL = ("siglaTribunal", "sigla_tribunal", "tribunal")
CAMPOS_TEXTO = ("texto",)


class FormatoInesperado(ValueError):
    """A resposta do DJEN não tem o formato esperado: conferir antes de seguir."""


def _primeiro(bruto: dict[str, Any], campos: tuple[str, ...]) -> Any:
    for campo in campos:
        valor = bruto.get(campo)
        if valor not in (None, ""):
            return valor
    return None


def _data(valor: Any) -> date:
    texto = str(valor).strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise FormatoInesperado(f"data de disponibilização ilegível: {valor!r}")


def ler_comunicacao(bruto: dict[str, Any]) -> Comunicacao:
    identificador = _primeiro(bruto, CAMPOS_ID)
    data = _primeiro(bruto, CAMPOS_DATA)
    if identificador is None or data is None:
        chaves = ", ".join(sorted(bruto))
        raise FormatoInesperado(f"comunicação sem id ou data de disponibilização; chaves: {chaves}")
    processo = _primeiro(bruto, CAMPOS_PROCESSO)
    tribunal = _primeiro(bruto, CAMPOS_TRIBUNAL)
    return Comunicacao(
        id=str(identificador),
        disponibilizacao=_data(data),
        numero_processo=str(processo) if processo is not None else None,
        tribunal=str(tribunal) if tribunal is not None else None,
        texto=str(_primeiro(bruto, CAMPOS_TEXTO) or ""),
        bruto=bruto,
    )


class ClienteDjen:
    def __init__(
        self,
        cliente_http: httpx.Client | None = None,
        tentativas: int = 3,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = cliente_http or httpx.Client(timeout=60)
        self._tentativas = tentativas
        self._esperar = esperar

    def _pagina(self, params: dict[str, str]) -> list[dict[str, Any]]:
        ultimo = ""
        for tentativa in range(self._tentativas):
            try:
                resposta = self._http.get(URL, params=params)
            except httpx.HTTPError as erro:
                ultimo = f"erro de conexão: {erro}"
            else:
                if resposta.status_code == 200:
                    corpo = resposta.json()
                    itens = corpo.get("items") if isinstance(corpo, dict) else None
                    if not isinstance(itens, list):
                        raise FormatoInesperado("resposta do DJEN sem a lista 'items'")
                    return itens
                ultimo = f"HTTP {resposta.status_code}: {resposta.text[:200]}"
                if resposta.status_code == 429:
                    self._esperar(ESPERA_429)
                    continue
            if tentativa + 1 < self._tentativas:
                self._esperar(2.0 * 2**tentativa)
        raise FonteIndisponivel(f"DJEN {params.get('numeroOab')}/{params.get('ufOab')}: {ultimo}")

    def comunicacoes(self, oab: str, uf: str, inicio: date, fim: date) -> list[dict[str, Any]]:
        itens: list[dict[str, Any]] = []
        for pagina in range(1, LIMITE_PAGINAS + 1):
            params = {
                "numeroOab": oab,
                "ufOab": uf,
                "dataDisponibilizacaoInicio": inicio.isoformat(),
                "dataDisponibilizacaoFim": fim.isoformat(),
                "pagina": str(pagina),
                "itensPorPagina": str(ITENS_POR_PAGINA),
            }
            lote = self._pagina(params)
            itens.extend(lote)
            if len(lote) < ITENS_POR_PAGINA:
                return itens
        raise FonteIndisponivel(f"DJEN {oab}/{uf}: mais de 10.000 resultados; reduzir o período")
