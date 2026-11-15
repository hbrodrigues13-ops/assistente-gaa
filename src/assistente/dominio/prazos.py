"""Contagem de prazos processuais publicados no DJEN.

- Publicação: primeiro dia útil seguinte à disponibilização (CPC, art. 224, § 2º).
- Início: primeiro dia útil seguinte à publicação (CPC, art. 224, § 3º).
- Só dias úteis (CPC, art. 219); recesso de 20/12 a 20/01 (CPC, art. 220).
- Começo ou vencimento com expediente irregular ou indisponibilidade
  prorroga para o dia útil seguinte (CPC, art. 224, § 1º).
- Segurança: metade do prazo, arredondada para baixo (CLAUDE.md, seção 5.1).

Funções puras, sem I/O.
"""

from dataclasses import dataclass, replace
from datetime import date

from assistente.dominio.calendario import Calendario, em_recesso_art220

DIAS_MERA_CIENCIA = 3
AVISO_MERA_CIENCIA = (
    "Prazo de 3 dias úteis por convenção interna do GAA para mera ciência, "
    "mais conservador que os 5 dias do CPC, art. 218, § 3º."
)


@dataclass(frozen=True, slots=True)
class Prazo:
    disponibilizacao: date
    dias: int
    publicacao: date
    inicio: date
    seguranca: date
    vencimento: date
    avisos: tuple[str, ...] = ()


def dia_de_seguranca(dias: int) -> int:
    """Em que dia útil do prazo cai a segurança: metade, arredondada para baixo, no mínimo 1."""
    return max(1, dias // 2)


def _prorrogar(dia: date, calendario: Calendario, momento: str, avisos: list[str]) -> date:
    while calendario.prorroga(dia):
        motivo = "; ".join(e.descricao for e in calendario.eventos_em(dia))
        seguinte = calendario.proximo_dia_prazo(dia)
        avisos.append(
            f"{momento} em {dia:%d/%m/%Y} ({motivo}) prorrogado para "
            f"{seguinte:%d/%m/%Y} (CPC, art. 224, § 1º)."
        )
        dia = seguinte
    return dia


def calcular_prazo(disponibilizacao: date, dias: int, calendario: Calendario) -> Prazo:
    if dias < 1:
        raise ValueError(f"prazo deve ter ao menos 1 dia útil; recebido {dias}")

    avisos: list[str] = []
    if not calendario.conferido:
        avisos.append("Calendário pendente de conferência por Henrique: confirmar as datas.")

    publicacao = calendario.proximo_dia_expediente(disponibilizacao)
    if em_recesso_art220(publicacao):
        avisos.append(
            f"Publicação em {publicacao:%d/%m/%Y}, durante o recesso do CPC, art. 220: "
            "adotada a contagem mais conservadora, com início no primeiro dia útil após o recesso."
        )

    inicio = _prorrogar(calendario.proximo_dia_prazo(publicacao), calendario, "Início", avisos)

    alvo_seguranca = dia_de_seguranca(dias)
    dia = inicio
    seguranca = inicio
    for contados in range(1, dias + 1):
        if contados > 1:
            dia = calendario.proximo_dia_prazo(dia)
        if contados == alvo_seguranca:
            seguranca = dia

    vencimento = _prorrogar(dia, calendario, "Vencimento", avisos)
    if calendario.cobertura_ate is not None and vencimento > calendario.cobertura_ate:
        avisos.append(
            f"O prazo passa de {calendario.cobertura_ate:%d/%m/%Y}, último dia com tabela de "
            "feriados do tribunal: conferir o calendário do ano seguinte."
        )
    return Prazo(
        disponibilizacao=disponibilizacao,
        dias=dias,
        publicacao=publicacao,
        inicio=inicio,
        seguranca=seguranca,
        vencimento=vencimento,
        avisos=tuple(avisos),
    )


def calcular_prazo_mera_ciencia(disponibilizacao: date, calendario: Calendario) -> Prazo:
    prazo = calcular_prazo(disponibilizacao, DIAS_MERA_CIENCIA, calendario)
    return replace(prazo, avisos=(*prazo.avisos, AVISO_MERA_CIENCIA))


def mais_conservador(*prazos: Prazo) -> Prazo:
    """Entre intimações do mesmo ato (portal e DJEN), adota o vencimento mais cedo."""
    if not prazos:
        raise ValueError("informe ao menos um prazo")
    escolhido = min(prazos, key=lambda p: (p.vencimento, p.seguranca))
    vencimentos = sorted({p.vencimento for p in prazos})
    if len(vencimentos) == 1:
        return escolhido
    datas = ", ".join(f"{v:%d/%m/%Y}" for v in vencimentos)
    aviso = (
        f"Há divergência entre intimações do mesmo ato (vencimentos {datas}); "
        f"adotado o mais conservador, {escolhido.vencimento:%d/%m/%Y}."
    )
    return replace(escolhido, avisos=(*escolhido.avisos, aviso))
