"""Teste do fluxo de conferência com o TJSP falso (sem rede)."""

from typing import Any

from assistente.fluxos.conferir_calendario import conferir_todas


class TjspVazio:
    def feriados(self, municipio: str, ano: int) -> list[dict[str, Any]]:
        return [{"Data": "15/01/2031", "Descricao": f"FERIADO DE {municipio.upper()}"}]

    def suspensoes(self, municipio: str, ano: int) -> list[dict[str, Any]]:
        return []


def test_ano_sem_tabela_gera_toml_sugerido_por_comarca() -> None:
    texto, tudo_confere = conferir_todas(2031, TjspVazio())
    assert not tudo_confere
    assert "sem tabela de 2031" in texto
    assert "FERIADO DE MARÍLIA" in texto
    assert 'comarca = "marilia"' in texto
    assert "inicio = 2031-01-15" in texto
