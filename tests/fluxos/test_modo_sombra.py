"""Testes do relatório do modo sombra (banco e classificador falsos, sem rede)."""

from datetime import date
from typing import Any

from assistente.agentes.classificador import ClassificacaoPublicacao, ClassificacaoRecusada
from assistente.fluxos.modo_sombra import analisar_pendentes, relatorio


class BancoFalso:
    def __init__(self, linhas: list[dict[str, Any]]) -> None:
        self.linhas = linhas
        self.analises: dict[str, dict[str, Any]] = {}

    def comunicacoes_desde(self, desde: date) -> list[dict[str, Any]]:
        return [r for r in self.linhas if r["disponibilizacao"] >= desde.isoformat()]

    def ids_analisados(self, ids: list[str]) -> set[str]:
        return {i for i in ids if i in self.analises}

    def salvar_analise(self, analise: dict[str, Any]) -> None:
        self.analises[analise["comunicacao_id"]] = analise


class ClassificadorFalso:
    def __init__(self, resposta: ClassificacaoPublicacao | Exception) -> None:
        self.resposta = resposta
        self.chamadas = 0

    def classificar(
        self, texto: str, classe: str | None, tipo: str | None
    ) -> ClassificacaoPublicacao:
        self.chamadas += 1
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


def _linha(
    id_: str, tribunal: str, processo: str, texto: str, data: str = "2026-11-03"
) -> dict[str, Any]:
    bruto = {
        "id": int(id_),
        "data_disponibilizacao": data,
        "numero_processo": processo,
        "numeroprocessocommascara": processo,
        "siglaTribunal": tribunal,
        "tipoComunicacao": "Intimação",
        "nomeClasse": "EXECUÇÃO DE TÍTULO EXTRAJUDICIAL",
        "texto": texto,
        "ativo": True,
        "data_cancelamento": None,
    }
    return {"id": id_, "oab": "509289/SP", "disponibilizacao": data, "bruto": bruto}


MARILIA = "12345672320258260344"
TEXTO = "Manifeste-se o exequente sobre a certidão negativa, no prazo de 15 dias."


def _classificacao(**extra: Any) -> ClassificacaoPublicacao:
    base: dict[str, Any] = {
        "classe": "execucao",
        "polo_cliente": "credor",
        "ato": "citacao_negativa",
        "prazo_fixado_dias": 15,
        "trecho_prazo": "no prazo de 15 dias",
        "resumo": "Indicar novo endereço.",
    }
    base.update(extra)
    return ClassificacaoPublicacao(**base)


def test_trabalhista_e_descartada_sem_chamar_o_modelo() -> None:
    banco = BancoFalso([_linha("1", "TRT15", "00012345620255150001", "x")])
    classificador = ClassificadorFalso(_classificacao())
    linhas = analisar_pendentes(banco, classificador, date(2026, 11, 1))
    assert classificador.chamadas == 0
    assert "trabalhista" in banco.analises["1"]["fora_de_escopo"]
    assert linhas[0].fora_de_escopo


def test_publicacao_do_tjsp_classificada_com_prazo_calculado() -> None:
    banco = BancoFalso([_linha("2", "TJSP", MARILIA, TEXTO)])
    analisar_pendentes(banco, ClassificadorFalso(_classificacao()), date(2026, 11, 1))
    a = banco.analises["2"]
    # disponibilizado ter 03/11; publicado qua 04/11; início qui 05/11; 15 dias úteis
    assert a["prazo_dias"] == 15
    assert a["publicacao"] == "2026-11-04"
    assert a["inicio"] == "2026-11-05"
    assert a["seguranca"] == "2026-11-13"  # 7º dia útil
    assert a["vencimento"] == "2026-11-26"  # 20/11 feriado
    assert a["modelo"] == "claude-haiku-5-5"
    assert a["erro"] is None


def test_segunda_rodada_nao_repete() -> None:
    banco = BancoFalso([_linha("2", "TJSP", MARILIA, TEXTO)])
    classificador = ClassificadorFalso(_classificacao())
    analisar_pendentes(banco, classificador, date(2026, 11, 1))
    analisar_pendentes(banco, classificador, date(2026, 11, 1))
    assert classificador.chamadas == 1


def test_trecho_inventado_nao_vale() -> None:
    banco = BancoFalso([_linha("3", "TJSP", MARILIA, "Certidão negativa do oficial.")])
    analisar_pendentes(banco, ClassificadorFalso(_classificacao()), date(2026, 11, 1))
    a = banco.analises["3"]
    assert a["prazo_dias"] == 5
    assert any("não confirmado" in x for x in a["avisos"])


def test_cliente_devedor_gera_alerta() -> None:
    banco = BancoFalso([_linha("4", "TJSP", MARILIA, TEXTO)])
    analisar_pendentes(
        banco, ClassificadorFalso(_classificacao(polo_cliente="devedor")), date(2026, 11, 1)
    )
    assert any("devedor" in x for x in banco.analises["4"]["avisos"])


def test_tribunal_sem_calendario_nao_calcula_e_avisa() -> None:
    banco = BancoFalso([_linha("5", "TJPR", "00042303520268160105", TEXTO)])
    analisar_pendentes(banco, ClassificadorFalso(_classificacao()), date(2026, 11, 1))
    a = banco.analises["5"]
    assert a["vencimento"] is None
    assert any("calendário" in x for x in a["avisos"])


def test_recusa_do_modelo_fica_registrada_como_erro() -> None:
    banco = BancoFalso([_linha("6", "TJSP", MARILIA, TEXTO)])
    analisar_pendentes(
        banco, ClassificadorFalso(ClassificacaoRecusada("refusal")), date(2026, 11, 1)
    )
    assert "refusal" in banco.analises["6"]["erro"]


def test_relatorio_ordena_por_seguranca_e_conta_descartes() -> None:
    banco = BancoFalso(
        [
            _linha("1", "TRT15", "00012345620255150001", "x"),
            _linha("2", "TJSP", MARILIA, TEXTO),
        ]
    )
    linhas = analisar_pendentes(banco, ClassificadorFalso(_classificacao()), date(2026, 11, 1))
    texto = relatorio(linhas)
    assert "13/11/2026" in texto and "26/11/2026" in texto
    assert "Fora do escopo: 1" in texto
    assert "citacao_negativa" in texto
