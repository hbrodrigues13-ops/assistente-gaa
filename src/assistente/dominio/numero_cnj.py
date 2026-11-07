"""Numeração única de processos judiciais (Resolução CNJ 65/2008).

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
- NNNNNNN: número sequencial do processo no ano;
- DD: dígito verificador (módulo 97, ISO 7064);
- AAAA: ano do ajuizamento;
- J: segmento do Judiciário (8 = Justiça Estadual);
- TR: tribunal (na Justiça Estadual, 26 = TJSP);
- OOOO: unidade de origem (no TJSP, o foro; ex.: 0344 = Marília).

O cálculo foi conferido contra o do pydatajud (Unlicense,
github.com/Filipe-Araujo0/pydatajud). Ver docs/decisoes/0002-pydatajud.md.
Função pura, sem I/O.
"""

import re
from dataclasses import dataclass

_FORMATADO = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")
_SO_DIGITOS = re.compile(r"^\d{20}$")
JUSTICA_ESTADUAL = "8"


class NumeroCnjInvalido(ValueError):
    """Número de processo fora do padrão CNJ ou com dígito verificador errado."""


@dataclass(frozen=True, slots=True)
class NumeroCnj:
    sequencial: str
    digito: str
    ano: str
    justica: str
    tribunal: str
    origem: str

    @property
    def digitos(self) -> str:
        return f"{self.sequencial}{self.digito}{self.ano}{self.justica}{self.tribunal}{self.origem}"

    @property
    def formatado(self) -> str:
        return (
            f"{self.sequencial}-{self.digito}.{self.ano}."
            f"{self.justica}.{self.tribunal}.{self.origem}"
        )

    @property
    def justica_estadual(self) -> bool:
        return self.justica == JUSTICA_ESTADUAL


def calcular_digito_verificador(
    sequencial: str, ano: str, justica: str, tribunal: str, origem: str
) -> str:
    """Calcula o DD pelo módulo 97: 98 - (NNNNNNNAAAAJTROOOO00 mod 97)."""
    base = int(f"{sequencial}{ano}{justica}{tribunal}{origem}00")
    return f"{98 - base % 97:02d}"


def interpretar_numero_cnj(texto: str) -> NumeroCnj:
    """Valida e separa o número CNJ, formatado ou com 20 dígitos."""
    limpo = texto.strip()
    if _SO_DIGITOS.match(limpo):
        partes = (limpo[:7], limpo[7:9], limpo[9:13], limpo[13], limpo[14:16], limpo[16:])
    else:
        encontrado = _FORMATADO.match(limpo)
        if encontrado is None:
            raise NumeroCnjInvalido(
                f"formato inválido: {texto!r}; use NNNNNNN-DD.AAAA.J.TR.OOOO ou 20 dígitos"
            )
        g = encontrado.group
        partes = (g(1), g(2), g(3), g(4), g(5), g(6))

    sequencial, digito, ano, justica, tribunal, origem = partes
    esperado = calcular_digito_verificador(sequencial, ano, justica, tribunal, origem)
    if digito != esperado:
        raise NumeroCnjInvalido(f"dígito verificador {digito} inválido, esperado {esperado}")
    return NumeroCnj(sequencial, digito, ano, justica, tribunal, origem)


def numero_cnj_valido(texto: str) -> bool:
    try:
        interpretar_numero_cnj(texto)
    except NumeroCnjInvalido:
        return False
    return True
