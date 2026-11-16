"""Relatório do modo sombra (Fluxo 1, etapas 2 e 3): classifica e calcula prazos.

Uso (no computador de Henrique):
    uv run --env-file .env python -m assistente.fluxos.modo_sombra [--desde AAAA-MM-DD]

Lê do Supabase as comunicações coletadas ainda não analisadas, descarta as fora
do escopo (sem chamar o modelo), classifica as demais com o modelo leve, decide
os dias pela regra do domínio, calcula as datas pelo calendário conferido e
grava a análise. Nada é lançado no Legal One: o relatório serve para comparar
com o controle manual (princípio 6).
"""

import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from assistente.agentes.classificador import (
    MODELO_CLASSIFICACAO,
    ClassificacaoPublicacao,
    ClassificacaoRecusada,
)
from assistente.dominio.escopo import motivo_fora_de_escopo
from assistente.dominio.numero_cnj import NumeroCnjInvalido, interpretar_numero_cnj
from assistente.dominio.prazos import calcular_prazo
from assistente.dominio.regra_prazo import definir_prazo, trecho_confere
from assistente.fontes.calendarios import CalendarioIndisponivel, carregar_calendario
from assistente.fontes.djen import FormatoInesperado, ler_comunicacao
from assistente.fontes.erros import FonteIndisponivel


class BancoSombra(Protocol):
    def comunicacoes_desde(self, desde: date) -> list[dict[str, Any]]: ...

    def ids_analisados(self, ids: list[str]) -> set[str]: ...

    def salvar_analise(self, analise: dict[str, Any]) -> None: ...


class Classificador(Protocol):
    def classificar(
        self, texto: str, classe_processual: str | None, tipo_comunicacao: str | None
    ) -> ClassificacaoPublicacao: ...


@dataclass(frozen=True)
class LinhaRelatorio:
    processo: str
    tribunal: str
    fora_de_escopo: str | None
    ato: str | None
    polo: str | None
    prazo_dias: int | None
    seguranca: date | None
    vencimento: date | None
    avisos: tuple[str, ...]
    erro: str | None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _calendario(tribunal: str | None, numero: str | None, ano: int) -> tuple[Any, str | None]:
    if (tribunal or "").upper() != "TJSP" or not numero:
        return None, f"Sem calendário cadastrado para {tribunal or 'tribunal desconhecido'}."
    try:
        foro = interpretar_numero_cnj(numero).origem
        return carregar_calendario(ano, foro), None
    except NumeroCnjInvalido:
        return None, "Número CNJ inválido: prazo não calculado."
    except CalendarioIndisponivel:
        return None, f"Sem tabela de calendário do TJSP para {ano}."


def analisar_um(
    linha: dict[str, Any], classificador: Classificador
) -> tuple[dict[str, Any], LinhaRelatorio]:
    bruto = linha["bruto"]
    c = ler_comunicacao(bruto)
    processo = str(bruto.get("numeroprocessocommascara") or c.numero_processo or "")
    tribunal = c.tribunal or ""
    analise: dict[str, Any] = {"comunicacao_id": c.id, "publicacao": None, "erro": None}

    motivo = motivo_fora_de_escopo(
        c.tribunal,
        c.numero_processo,
        bruto.get("tipoComunicacao"),
        bruto.get("ativo"),
        bruto.get("data_cancelamento"),
    )
    if motivo:
        analise.update({"fora_de_escopo": motivo, "avisos": []})
        vazia = LinhaRelatorio(processo, tribunal, motivo, None, None, None, None, None, (), None)
        return analise, vazia

    try:
        classif = classificador.classificar(
            c.texto, bruto.get("nomeClasse"), bruto.get("tipoComunicacao")
        )
    except ClassificacaoRecusada as erro:
        analise.update({"erro": str(erro), "avisos": [], "modelo": MODELO_CLASSIFICACAO})
        falha = LinhaRelatorio(
            processo, tribunal, None, None, None, None, None, None, (), str(erro)
        )
        return analise, falha

    confirmado = trecho_confere(c.texto, classif.trecho_prazo)
    decisao = definir_prazo(classif.ato, classif.prazo_fixado_dias, confirmado)
    avisos = list(decisao.avisos)
    if classif.polo_cliente == "devedor":
        avisos.append("Cliente no polo devedor: apenas alerta, fora da minuta.")
    if classif.polo_cliente == "indefinido":
        avisos.append("Polo do cliente indefinido: conferir.")

    calendario, aviso_cal = _calendario(c.tribunal, c.numero_processo, c.disponibilizacao.year)
    seguranca = vencimento = publicacao = inicio = None
    if calendario is None:
        avisos.append(aviso_cal or "Calendário indisponível.")
    else:
        prazo = calcular_prazo(c.disponibilizacao, decisao.dias, calendario)
        avisos.extend(prazo.avisos)
        publicacao, inicio = prazo.publicacao, prazo.inicio
        seguranca, vencimento = prazo.seguranca, prazo.vencimento

    analise.update(
        {
            "fora_de_escopo": None,
            "classe": classif.classe,
            "polo_cliente": classif.polo_cliente,
            "ato": classif.ato,
            "trecho_prazo": classif.trecho_prazo,
            "prazo_dias": decisao.dias,
            "fundamento_prazo": decisao.fundamento,
            "publicacao": _iso(publicacao),
            "inicio": _iso(inicio),
            "seguranca": _iso(seguranca),
            "vencimento": _iso(vencimento),
            "avisos": avisos,
            "resumo": classif.resumo,
            "modelo": MODELO_CLASSIFICACAO,
        }
    )
    linha_rel = LinhaRelatorio(
        processo,
        tribunal,
        None,
        classif.ato,
        classif.polo_cliente,
        decisao.dias,
        seguranca,
        vencimento,
        tuple(avisos),
        None,
    )
    return analise, linha_rel


def analisar_pendentes(
    banco: BancoSombra, classificador: Classificador, desde: date
) -> list[LinhaRelatorio]:
    linhas = banco.comunicacoes_desde(desde)
    ja = banco.ids_analisados([str(r["id"]) for r in linhas])
    resultado = []
    for linha in linhas:
        if str(linha["id"]) in ja:
            continue
        try:
            analise, rel = analisar_um(linha, classificador)
        except FormatoInesperado as erro:
            analise = {"comunicacao_id": str(linha["id"]), "erro": str(erro), "avisos": []}
            rel = LinhaRelatorio(
                str(linha["id"]), "", None, None, None, None, None, None, (), str(erro)
            )
        banco.salvar_analise(analise)
        resultado.append(rel)
    return resultado


def _br(d: date | None) -> str:
    return f"{d:%d/%m/%Y}" if d else "-"


def relatorio(linhas: list[LinhaRelatorio]) -> str:
    dentro = [linha for linha in linhas if not linha.fora_de_escopo and not linha.erro]
    erros = [linha for linha in linhas if linha.erro]
    fora = [linha for linha in linhas if linha.fora_de_escopo]
    dentro.sort(key=lambda linha: (linha.seguranca or date.max, linha.processo))
    partes = [
        f"# Modo sombra: {len(dentro)} publicações analisadas",
        "",
        "| Segurança | Vencimento | Processo | Trib. | Ato | Polo | Dias | Avisos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for linha in dentro:
        avisos = "; ".join(linha.avisos) if linha.avisos else ""
        partes.append(
            f"| {_br(linha.seguranca)} | {_br(linha.vencimento)} | {linha.processo} | "
            f"{linha.tribunal} | {linha.ato} | {linha.polo} | {linha.prazo_dias} | {avisos} |"
        )
    partes += ["", f"Fora do escopo: {len(fora)}"]
    motivos: dict[str, int] = {}
    for linha in fora:
        chave = linha.fora_de_escopo or ""
        motivos[chave] = motivos.get(chave, 0) + 1
    partes += [f"- {motivo}: {qtd}" for motivo, qtd in sorted(motivos.items())]
    if erros:
        partes += ["", f"Com erro (revisar manualmente): {len(erros)}"]
        partes += [f"- {linha.processo}: {linha.erro}" for linha in erros]
    return "\n".join(partes) + "\n"


def main() -> int:
    from assistente.adaptadores.armazenamento_supabase import ArmazenamentoSupabase
    from assistente.agentes.classificador import ClassificadorClaude

    url = os.environ.get("SUPABASE_URL", "")
    chave = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not chave or not os.environ.get("ANTHROPIC_API_KEY"):
        print("Defina SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY e ANTHROPIC_API_KEY no .env.")
        return 2
    args = sys.argv[1:]
    desde = date.today() - timedelta(days=7)
    if "--desde" in args:
        desde = datetime.strptime(args[args.index("--desde") + 1], "%Y-%m-%d").date()
    try:
        linhas = analisar_pendentes(ArmazenamentoSupabase(url, chave), ClassificadorClaude(), desde)
    except FonteIndisponivel as erro:
        print(f"FALHA: {erro}")
        return 1
    print(relatorio(linhas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
