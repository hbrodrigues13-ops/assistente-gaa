"""Filtro de escopo do Fluxo 1 (regra pura).

Fora do escopo: publicações trabalhistas (CLAUDE.md, seção 5.4), comunicações
canceladas e tipos de comunicação que não abrem prazo.
"""

from assistente.dominio.numero_cnj import NumeroCnjInvalido, interpretar_numero_cnj

JUSTICA_DO_TRABALHO = "5"
TIPOS_SEM_PRAZO = frozenset({"lista de distribuição"})


def motivo_fora_de_escopo(
    tribunal: str | None,
    numero_processo: str | None,
    tipo_comunicacao: str | None,
    ativo: bool | None,
    data_cancelamento: str | None,
) -> str | None:
    """Devolve o motivo de exclusão, ou None se a publicação entra no Fluxo 1."""
    sigla = (tribunal or "").upper()
    if sigla.startswith(("TRT", "TST")):
        return "trabalhista (fora do Fluxo 1)"
    if numero_processo:
        try:
            if interpretar_numero_cnj(numero_processo).justica == JUSTICA_DO_TRABALHO:
                return "trabalhista pelo número CNJ (fora do Fluxo 1)"
        except NumeroCnjInvalido:
            pass  # número irregular não exclui: segue para revisão humana
    if ativo is False or data_cancelamento:
        return "comunicação cancelada no DJEN"
    if (tipo_comunicacao or "").strip().lower() in TIPOS_SEM_PRAZO:
        return f"tipo sem prazo ({tipo_comunicacao})"
    return None
