"""Coleta diária do DJEN por OAB (Fluxo 1, etapa 1), em modo sombra.

Uso (no computador de Henrique, no Brasil):
    uv run --env-file .env python -m assistente.fluxos.coleta_djen
    uv run --env-file .env python -m assistente.fluxos.coleta_djen --diagnostico

Variáveis do .env: DJEN_OABS (ex.: 509289/SP,177936/SP), SUPABASE_URL e
SUPABASE_SERVICE_ROLE_KEY. Grava no Supabase (projeto assistente-gaa, São
Paulo); nada de cliente fica no computador. Sai com código 1 se alguma OAB
falhar ou a coleta estiver atrasada: nada falha em silêncio.
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from assistente.adaptadores.armazenamento_supabase import ArmazenamentoSupabase
from assistente.dominio.comunicacao import Comunicacao, coleta_atrasada, intervalo_de_coleta
from assistente.fontes.djen import ClienteDjen, FormatoInesperado, ler_comunicacao
from assistente.fontes.erros import FonteIndisponivel


class FonteDjen(Protocol):
    def comunicacoes(self, oab: str, uf: str, inicio: Any, fim: Any) -> list[dict[str, Any]]: ...


class Armazenamento(Protocol):
    def salvar(self, oab: str, comunicacoes: list[Comunicacao]) -> tuple[int, int]: ...

    def registrar_coleta(
        self, oab: str, inicio: date, fim: date, executada_em: datetime, erro: str | None
    ) -> None: ...

    def ultima_coleta_ok(self, oab: str) -> date | None: ...


@dataclass
class ResultadoColeta:
    novas: int = 0
    repetidas: int = 0
    falhas: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    linhas: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.falhas and not self.alertas

    def texto(self) -> str:
        partes = [*self.linhas, f"Total: {self.novas} novas, {self.repetidas} repetidas."]
        partes += [f"FALHA: {f}" for f in self.falhas]
        partes += [f"ALERTA: {a}" for a in self.alertas]
        return "\n".join(partes)


def ler_oabs(texto: str) -> list[tuple[str, str]]:
    oabs = []
    for parte in texto.split(","):
        numero, _, uf = parte.strip().partition("/")
        if numero and uf:
            oabs.append((numero.strip(), uf.strip().upper()))
    return oabs


def coletar(
    oabs: list[tuple[str, str]],
    djen: FonteDjen,
    banco: Armazenamento,
    agora: datetime,
) -> ResultadoColeta:
    resultado = ResultadoColeta()
    hoje = agora.date()
    for numero, uf in oabs:
        chave = f"{numero}/{uf}"
        inicio, fim = intervalo_de_coleta(banco.ultima_coleta_ok(chave), hoje)
        try:
            brutos = djen.comunicacoes(numero, uf, inicio, fim)
            comunicacoes = [ler_comunicacao(b) for b in brutos]
        except (FonteIndisponivel, FormatoInesperado) as erro:
            banco.registrar_coleta(chave, inicio, fim, agora, str(erro))
            resultado.falhas.append(f"{chave}: {erro}")
        else:
            novas, repetidas = banco.salvar(chave, comunicacoes)
            banco.registrar_coleta(chave, inicio, fim, agora, None)
            resultado.novas += novas
            resultado.repetidas += repetidas
            resultado.linhas.append(
                f"{chave}: {inicio:%d/%m} a {fim:%d/%m}, {novas} novas, {repetidas} repetidas"
            )
        ultima = banco.ultima_coleta_ok(chave)
        if coleta_atrasada(ultima, hoje):
            desde = f"{ultima:%d/%m/%Y}" if ultima else "nunca"
            resultado.alertas.append(f"coleta atrasada para {chave} (última bem-sucedida: {desde})")
    return resultado


def resumo_diagnostico(brutos: list[dict[str, Any]]) -> str:
    """Mostra os nomes dos campos e um exemplo encurtado, para fixar o formato do DJEN."""
    if not brutos:
        return "DJEN respondeu, mas nenhuma comunicação no período."
    primeiro = brutos[0]
    linhas = [f"DJEN respondeu: {len(brutos)} comunicação(ões). Campos da primeira:"]
    for chave in sorted(primeiro):
        valor = str(primeiro[chave]).replace("\n", " ")
        linhas.append(f"  {chave} = {valor[:60]}")
    return "\n".join(linhas)[:1400]


def main() -> int:
    oabs = ler_oabs(os.environ.get("DJEN_OABS", ""))
    if not oabs:
        print("Defina DJEN_OABS no .env (ex.: 509289/SP,177936/SP).")
        return 2
    if "--diagnostico" in sys.argv[1:]:
        from datetime import timedelta

        hoje = datetime.now().date()
        numero, uf = oabs[0]
        print(resumo_diagnostico(ClienteDjen().comunicacoes(numero, uf, hoje - timedelta(7), hoje)))
        return 0
    url = os.environ.get("SUPABASE_URL", "")
    chave = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not chave:
        print("Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.")
        return 2
    banco = ArmazenamentoSupabase(url, chave)
    try:
        resultado = coletar(oabs, ClienteDjen(), banco, datetime.now())
    except FonteIndisponivel as erro:  # Supabase fora do ar: nada gravado, nada perdido
        print(f"FALHA: {erro}")
        return 1
    print(resultado.texto())
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    sys.exit(main())
