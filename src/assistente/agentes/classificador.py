"""Classificação da publicação com o modelo leve (CLAUDE.md, seção 3 e Fluxo 1, etapa 2).

Saída estruturada e validada por pydantic. O modelo não decide prazo: só
indica o ato e, se houver, o trecho em que o prazo aparece; a regra de prazo é
`assistente.dominio.regra_prazo`. Envia ao modelo só o texto da publicação, a
classe processual e o tipo de comunicação (princípio 8).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

MODELO_CLASSIFICACAO = "claude-haiku-5-5"

INSTRUCOES = """\
Você classifica publicações judiciais para um escritório de advocacia que atua \
na recuperação de crédito, normalmente pelo credor. Leia a publicação e responda \
apenas no formato pedido.

- classe: execucao, cumprimento_de_sentenca, monitoria, busca_e_apreensao, \
cobranca ou outra.
- polo_cliente: credor, devedor ou indefinido. Na dúvida, indefinido.
- ato: citacao_negativa, bloqueio_infrutifero, intimacao_para_andamento, \
embargos (embargos à execução recebidos), impugnacao, sentenca, mera_ciencia \
(ato que não exige providência) ou outro.
- prazo_fixado_dias: número de dias que o próprio texto fixa para a parte agir. \
Se o texto não fixar prazo expressamente, null. Não deduza prazo legal.
- trecho_prazo: cópia literal do trecho do texto que fixa o prazo, ou null.
- resumo: uma frase, em português, com a providência esperada.
"""


class ClassificacaoPublicacao(BaseModel):
    classe: Literal[
        "execucao", "cumprimento_de_sentenca", "monitoria", "busca_e_apreensao", "cobranca", "outra"
    ]
    polo_cliente: Literal["credor", "devedor", "indefinido"]
    ato: Literal[
        "citacao_negativa",
        "bloqueio_infrutifero",
        "intimacao_para_andamento",
        "embargos",
        "impugnacao",
        "sentenca",
        "mera_ciencia",
        "outro",
    ]
    prazo_fixado_dias: int | None = Field(default=None, ge=1, le=365)
    trecho_prazo: str | None = Field(default=None, max_length=300)
    resumo: str = Field(max_length=300)


class ClassificacaoRecusada(RuntimeError):
    """O modelo recusou ou não devolveu classificação: vai para revisão manual."""


class ClassificadorClaude:
    def __init__(self, cliente: Any | None = None, modelo: str = MODELO_CLASSIFICACAO) -> None:
        if cliente is None:
            import anthropic

            cliente = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
        self._cliente = cliente
        self._modelo = modelo

    def classificar(
        self, texto: str, classe_processual: str | None, tipo_comunicacao: str | None
    ) -> ClassificacaoPublicacao:
        conteudo = (
            f"Classe processual: {classe_processual or 'não informada'}\n"
            f"Tipo de comunicação: {tipo_comunicacao or 'não informado'}\n\n"
            f"Publicação:\n{texto}"
        )
        resposta = self._cliente.messages.parse(
            model=self._modelo,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=[{"type": "text", "text": INSTRUCOES, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": conteudo}],
            output_format=ClassificacaoPublicacao,
        )
        if resposta.stop_reason == "refusal" or resposta.parsed_output is None:
            raise ClassificacaoRecusada(f"classificação não devolvida ({resposta.stop_reason})")
        resultado: ClassificacaoPublicacao = resposta.parsed_output
        return resultado
