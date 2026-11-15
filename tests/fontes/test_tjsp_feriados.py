"""Testes da conferência do calendário com a consulta oficial do TJSP (sem rede)."""

from datetime import date
from typing import Any

import httpx
import pytest

from assistente.fontes.calendarios import carregar_calendario
from assistente.fontes.tjsp_feriados import (
    ClienteTjsp,
    FonteIndisponivel,
    conferir_calendario,
    eventos_oficiais,
    municipio_da_comarca,
)

PROV = "(PROVIMENTO CSM Nº 2.813/2025)"


class TjspFalso:
    def __init__(self, feriados: list[dict[str, Any]], suspensoes: list[dict[str, Any]]) -> None:
        self._feriados = feriados
        self._suspensoes = suspensoes
        self.consultas: list[tuple[str, str, int]] = []

    def feriados(self, municipio: str, ano: int) -> list[dict[str, Any]]:
        self.consultas.append(("feriados", municipio, ano))
        return self._feriados

    def suspensoes(self, municipio: str, ano: int) -> list[dict[str, Any]]:
        self.consultas.append(("suspensoes", municipio, ano))
        return self._suspensoes


def _feriados_oficiais_2026_marilia() -> list[dict[str, Any]]:
    gerais = [
        ("16/02/2026", "CARNAVAL"),
        ("17/02/2026", "CARNAVAL"),
        ("02/04/2026", "ENDOENÇAS"),
        ("03/04/2026", "SEXTA-FEIRA DA PAIXÃO"),
        ("20/04/2026", "SUSPENSÃO DO EXPEDIENTE"),
        ("21/04/2026", "TIRADENTES"),
        ("01/05/2026", "DIA DO TRABALHO"),
        ("04/06/2026", "CORPUS-CHRISTI"),
        ("05/06/2026", "SUSPENSÃO DO EXPEDIENTE"),
        ("09/07/2026", "DATA MAGNA DO ESTADO DE SÃO PAULO"),
        ("10/07/2026", "SUSPENSÃO DO EXPEDIENTE"),
        ("07/09/2026", "INDEPENDÊNCIA DO BRASIL"),
        ("12/10/2026", "NOSSA SENHORA APARECIDA"),
        ("30/10/2026", "DIA DO SERVIDOR PÚBLICO"),
        ("02/11/2026", "FINADOS"),
        ("20/11/2026", "DIA NACIONAL DE ZUMBI E DA CONSCIÊNCIA NEGRA"),
        ("07/12/2026", "SUSPENSÃO DO EXPEDIENTE"),
        ("08/12/2026", "DIA DA JUSTIÇA"),
    ]
    lista = [{"Data": d, "Descricao": f"{t} {PROV}"} for d, t in gerais]
    lista += [
        {"Data": "04/04/2026", "Descricao": "ANIVERSÁRIO DA CIDADE"},
        {"Data": "11/07/2026", "Descricao": "SÃO BENTO - PADROEIRO"},
    ]
    return lista


SUSPENSOES_2026 = [
    {"Descricao": "Recesso Forense - Art. 116, §2º do RITJSP", "Data": "01/01/2026 a 06/01/2026"},
    {"Descricao": "Suspensão dos prazos processuais", "Data": "07/01/2026 a 20/01/2026"},
    {
        "Descricao": "COMUNICADO CONJUNTO Nº 837/2026 ... Foro de Marília: Vara da Fazenda Pública",
        "Data": "19/10/2026 a 23/10/2026",
    },
    {"Descricao": "Recesso Forense - Art. 116, §2º do RITJSP", "Data": "20/12/2026 a 31/12/2026"},
]


def test_municipio_da_comarca() -> None:
    assert municipio_da_comarca("marilia") == "Marília"
    assert municipio_da_comarca("sao_paulo") == "São Paulo"
    assert municipio_da_comarca("inexistente") is None


def test_eventos_oficiais_separa_gerais_de_municipais() -> None:
    tjsp = TjspFalso(_feriados_oficiais_2026_marilia(), SUSPENSOES_2026)
    oficiais = eventos_oficiais(tjsp, "Marília", 2026)
    municipais = {e.data for e in oficiais.feriados if e.municipal}
    assert municipais == {date(2026, 4, 4), date(2026, 7, 11)}
    assert date(2026, 1, 3) in oficiais.sem_expediente
    assert date(2026, 12, 31) in oficiais.sem_expediente
    assert [s.periodo for s in oficiais.suspensoes_de_vara] == ["19/10/2026 a 23/10/2026"]
    assert tjsp.consultas == [("feriados", "Marília", 2026), ("suspensoes", "Marília", 2026)]


def test_tabela_igual_a_oficial_nao_tem_divergencia() -> None:
    tjsp = TjspFalso(_feriados_oficiais_2026_marilia(), SUSPENSOES_2026)
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    assert resultado.faltando_na_tabela == ()
    assert resultado.sobrando_na_tabela == ()
    assert resultado.sem_divergencia
    assert len(resultado.suspensoes_de_vara) == 1


def test_feriado_novo_no_tjsp_aparece_como_faltando() -> None:
    oficiais = [
        *_feriados_oficiais_2026_marilia(),
        {"Data": "15/09/2026", "Descricao": "FERIADO NOVO - INCLUÍDO PELO CSM"},
    ]
    tjsp = TjspFalso(oficiais, SUSPENSOES_2026)
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    assert [e.data for e in resultado.faltando_na_tabela] == [date(2026, 9, 15)]
    assert not resultado.sem_divergencia
    assert "inicio = 2026-09-15" in resultado.toml_sugerido("marilia")
    assert 'comarca = "marilia"' in resultado.toml_sugerido("marilia")


def test_data_retirada_pelo_tjsp_aparece_como_sobrando() -> None:
    oficiais = [f for f in _feriados_oficiais_2026_marilia() if f["Data"] != "07/12/2026"]
    tjsp = TjspFalso(oficiais, SUSPENSOES_2026)
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    assert [e.data for e in resultado.sobrando_na_tabela] == [date(2026, 12, 7)]


def test_suspensao_de_vara_nao_vira_divergencia() -> None:
    tjsp = TjspFalso(_feriados_oficiais_2026_marilia(), SUSPENSOES_2026)
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    assert all(
        e.data.month != 10 or e.data.day not in range(19, 24) for e in resultado.faltando_na_tabela
    )


def test_relatorio_em_texto() -> None:
    oficiais = [
        *_feriados_oficiais_2026_marilia(),
        {"Data": "15/09/2026", "Descricao": "FERIADO NOVO"},
    ]
    tjsp = TjspFalso(oficiais, SUSPENSOES_2026)
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    texto = resultado.relatorio()
    assert "Marília" in texto and "15/09/2026" in texto and "FERIADO NOVO" in texto
    assert "Vara da Fazenda" in texto


def _cliente(respostas: list[httpx.Response], esperas: list[float]) -> ClienteTjsp:
    fila = list(respostas)

    def responder(requisicao: httpx.Request) -> httpx.Response:
        assert requisicao.url.params["nomeMunicipio"] == "Marília"
        return fila.pop(0)

    http = httpx.Client(transport=httpx.MockTransport(responder))
    return ClienteTjsp(http, tentativas=3, esperar=esperas.append)


def test_cliente_real_le_a_lista() -> None:
    esperas: list[float] = []
    cliente = _cliente([httpx.Response(200, json={"data": [{"Data": "04/04/2026"}]})], esperas)
    assert cliente.feriados("Marília", 2026) == [{"Data": "04/04/2026"}]
    assert esperas == []


def test_cliente_real_tenta_de_novo_e_recupera() -> None:
    esperas: list[float] = []
    cliente = _cliente(
        [httpx.Response(503), httpx.Response(200, json={"data": [{"Data": "01/01/2026"}]})],
        esperas,
    )
    assert cliente.suspensoes("Marília", 2026) == [{"Data": "01/01/2026"}]
    assert esperas == [2.0]


def test_cliente_real_falha_alertando_depois_das_tentativas() -> None:
    esperas: list[float] = []
    cliente = _cliente([httpx.Response(503)] * 3, esperas)
    with pytest.raises(FonteIndisponivel):
        cliente.feriados("Marília", 2026)
    assert esperas == [2.0, 4.0]


def test_cliente_real_tenta_de_novo_quando_a_lista_vem_vazia() -> None:
    esperas: list[float] = []
    cliente = _cliente(
        [httpx.Response(200, json={"data": []}), httpx.Response(200, json={"data": [{"x": 1}]})],
        esperas,
    )
    assert cliente.feriados("Marília", 2026) == [{"x": 1}]
    assert esperas == [2.0]


def test_cliente_real_devolve_vazia_se_persistir() -> None:
    esperas: list[float] = []
    cliente = _cliente([httpx.Response(200, json={"data": []})] * 3, esperas)
    assert cliente.feriados("Marília", 2026) == []
    assert esperas == [2.0, 4.0]


def test_consulta_de_feriados_vazia_nao_gera_divergencia_falsa() -> None:
    tjsp = TjspFalso([], SUSPENSOES_2026)
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    assert resultado.consulta_incompleta
    assert resultado.sobrando_na_tabela == ()
    assert not resultado.sem_divergencia
    assert "conferir manualmente" in resultado.relatorio()


def test_consulta_de_suspensoes_vazia_nao_acusa_o_recesso() -> None:
    tjsp = TjspFalso(_feriados_oficiais_2026_marilia(), [])
    resultado = conferir_calendario(tjsp, carregar_calendario(2026, "0344"), "Marília", 2026)
    assert resultado.consulta_incompleta
    assert resultado.sobrando_na_tabela == ()
