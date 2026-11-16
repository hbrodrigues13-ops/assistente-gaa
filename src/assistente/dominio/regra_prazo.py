"""Quantos dias de prazo adotar para cada publicação (regra pura e conservadora).

O modelo de linguagem só classifica o ato e aponta o trecho em que o prazo
aparece; quem decide o número de dias é esta função (princípio 1). Na dúvida,
o prazo menor, com aviso.
"""

import re
from dataclasses import dataclass

from assistente.dominio.prazos import DIAS_MERA_CIENCIA

DIAS_SUPLETIVO = 5  # CPC, art. 218, § 3º
DIAS_EMBARGOS_DECLARACAO = 5  # CPC, art. 1.023
DIAS_RESPOSTA_EMBARGOS_EXECUCAO = 15  # CPC, art. 920, I


@dataclass(frozen=True, slots=True)
class DecisaoPrazo:
    dias: int
    fundamento: str
    avisos: tuple[str, ...] = ()


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip().lower()


def trecho_confere(texto: str, trecho: str | None) -> bool:
    """O trecho citado pelo modelo existe de fato no texto da publicação?"""
    if not trecho or not trecho.strip():
        return False
    return _normalizar(trecho) in _normalizar(texto)


def definir_prazo(ato: str, prazo_fixado_dias: int | None, trecho_confirmado: bool) -> DecisaoPrazo:
    if ato == "sentenca":
        return DecisaoPrazo(
            DIAS_EMBARGOS_DECLARACAO,
            "Sentença: embargos de declaração em 5 dias (CPC, art. 1.023)",
            ("Apelação e contrarrazões em 15 dias (CPC, art. 1.003, § 5º).",),
        )
    if prazo_fixado_dias and trecho_confirmado:
        return DecisaoPrazo(prazo_fixado_dias, "Prazo fixado no próprio ato, trecho conferido")
    avisos: list[str] = []
    if prazo_fixado_dias and not trecho_confirmado:
        avisos.append(
            f"O modelo indicou {prazo_fixado_dias} dias, mas o trecho não confirmado no texto."
        )
    if ato == "embargos":
        return DecisaoPrazo(
            DIAS_RESPOSTA_EMBARGOS_EXECUCAO,
            "Embargos à execução recebidos: resposta em 15 dias (CPC, art. 920, I)",
            tuple(avisos),
        )
    if ato == "mera_ciencia":
        return DecisaoPrazo(
            DIAS_MERA_CIENCIA,
            "Mera ciência: 3 dias úteis por convenção interna (CPC, art. 218, § 3º, prevê 5)",
            tuple(avisos),
        )
    avisos.append("Prazo não identificado no texto: conferir na publicação.")
    return DecisaoPrazo(
        DIAS_SUPLETIVO,
        "Sem prazo legal ou judicial identificado: 5 dias (CPC, art. 218, § 3º)",
        tuple(avisos),
    )
