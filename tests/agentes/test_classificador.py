"""Testes do classificador (cliente da Anthropic simulado, sem rede)."""

from types import SimpleNamespace
from typing import Any

import pytest

from assistente.agentes.classificador import (
    MODELO_CLASSIFICACAO,
    ClassificacaoPublicacao,
    ClassificacaoRecusada,
    ClassificadorClaude,
)


class MensagensFalsas:
    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta
        self.chamadas: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.chamadas.append(kwargs)
        return self.resposta


def _cliente(resposta: Any) -> Any:
    return SimpleNamespace(messages=MensagensFalsas(resposta))


EXEMPLO = ClassificacaoPublicacao(
    classe="execucao",
    polo_cliente="credor",
    ato="citacao_negativa",
    prazo_fixado_dias=15,
    trecho_prazo="no prazo de 15 dias",
    resumo="Citação negativa; indicar novo endereço.",
)


def test_classifica_com_modelo_leve_e_saida_validada() -> None:
    cliente = _cliente(SimpleNamespace(stop_reason="end_turn", parsed_output=EXEMPLO))
    resultado = ClassificadorClaude(cliente).classificar(
        "Texto da publicação", "EXECUÇÃO DE TÍTULO EXTRAJUDICIAL", "Intimação"
    )
    assert resultado == EXEMPLO
    chamada = cliente.messages.chamadas[0]
    assert chamada["model"] == MODELO_CLASSIFICACAO == "claude-haiku-5-5"
    assert chamada["output_format"] is ClassificacaoPublicacao
    assert chamada["output_config"] == {"effort": "low"}
    assert chamada["system"][0]["cache_control"] == {"type": "ephemeral"}
    conteudo = chamada["messages"][0]["content"]
    assert "Texto da publicação" in conteudo and "EXECUÇÃO" in conteudo


def test_recusa_vira_erro_explicito() -> None:
    cliente = _cliente(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(ClassificacaoRecusada):
        ClassificadorClaude(cliente).classificar("x", None, None)


def test_resumo_limitado() -> None:
    with pytest.raises(ValueError):
        ClassificacaoPublicacao(
            classe="execucao",
            polo_cliente="credor",
            ato="outro",
            prazo_fixado_dias=None,
            trecho_prazo=None,
            resumo="x" * 400,
        )
