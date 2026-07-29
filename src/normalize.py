"""
normalize.py
Normaliza os anúncios vindos do Webmotors/iCarros (via Apify) para um schema
comum, e cruza com o valor FIPE correspondente para calcular o gap de preço.

O schema comum usado no resto do pipeline é o dict `AnuncioNormalizado`
(veja abaixo). Ajuste o dict `CAMPOS_*` de acordo com os nomes reais de
campo que o actor da Apify devolver (confira no Apify Console após a
primeira rodada de teste).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from fipe_client import FipeClient, ValorFipe


@dataclass
class AnuncioNormalizado:
    portal: str  # "webmotors" ou "icarros"
    anunciante: str  # nome da revenda/vendedor
    marca: str
    modelo: str
    versao: str
    ano_modelo: int
    km: int | None
    preco: float
    cidade: str
    estado: str
    url: str
    valor_fipe: float | None = None
    gap_percentual: float | None = None  # (preco - fipe) / fipe * 100
    eh_benet: bool = False


# Mapeamento "de-para": ajuste as CHAVES DA ESQUERDA para bater com os nomes
# de campo reais que o actor escolhido devolve. Os valores da direita são
# os nomes usados no schema comum acima e não devem mudar.
CAMPOS_WEBMOTORS = {
    "sellerName": "anunciante",
    "brand": "marca",
    "model": "modelo",
    "version": "versao",
    "modelYear": "ano_modelo",
    "mileage": "km",
    "price": "preco",
    "city": "cidade",
    "state": "estado",
    "url": "url",
}

CAMPOS_ICARROS = {
    "seller_name": "anunciante",
    "brand": "marca",
    "model": "modelo",
    "version": "versao",
    "year": "ano_modelo",
    "mileage": "km",
    "price": "preco",
    "city": "cidade",
    "state": "estado",
    "url": "url",
}

NOMES_BENET = {"benet", "benet veiculos", "benet veículos"}


def _mapear_campos(item_bruto: dict, mapeamento: dict[str, str], portal: str) -> AnuncioNormalizado:
    dados: dict = {"portal": portal}
    for campo_origem, campo_destino in mapeamento.items():
        dados[campo_destino] = item_bruto.get(campo_origem)

    anunciante = str(dados.get("anunciante", "")).strip()
    return AnuncioNormalizado(
        portal=portal,
        anunciante=anunciante,
        marca=str(dados.get("marca", "")).strip(),
        modelo=str(dados.get("modelo", "")).strip(),
        versao=str(dados.get("versao", "") or "").strip(),
        ano_modelo=int(dados.get("ano_modelo") or 0),
        km=int(dados["km"]) if dados.get("km") not in (None, "") else None,
        preco=float(dados.get("preco") or 0),
        cidade=str(dados.get("cidade", "")).strip(),
        estado=str(dados.get("estado", "")).strip(),
        url=str(dados.get("url", "")).strip(),
        eh_benet=anunciante.lower() in NOMES_BENET,
    )


def normalizar_webmotors(itens_brutos: list[dict]) -> list[AnuncioNormalizado]:
    return [_mapear_campos(item, CAMPOS_WEBMOTORS, "webmotors") for item in itens_brutos]


def normalizar_icarros(itens_brutos: list[dict]) -> list[AnuncioNormalizado]:
    return [_mapear_campos(item, CAMPOS_ICARROS, "icarros") for item in itens_brutos]


def _similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def cruzar_com_fipe(
    anuncios: list[AnuncioNormalizado],
    fipe_client: FipeClient,
    tabela_fipe_local: list[ValorFipe],
) -> list[AnuncioNormalizado]:
    """
    Casa cada anúncio com o valor FIPE mais próximo por similaridade de
    marca+modelo+ano (a tabela FIPE local deve ser pré-carregada via
    `fipe_client` para os modelos de interesse - ver main.py).
    """
    for anuncio in anuncios:
        melhor_match: ValorFipe | None = None
        melhor_score = 0.0
        for valor_fipe in tabela_fipe_local:
            if valor_fipe.ano_modelo != anuncio.ano_modelo:
                continue
            score = _similaridade(
                f"{valor_fipe.marca} {valor_fipe.modelo}",
                f"{anuncio.marca} {anuncio.modelo} {anuncio.versao}",
            )
            if score > melhor_score:
                melhor_score = score
                melhor_match = valor_fipe

        # 0.55 é um limiar conservador - ajuste conforme a qualidade dos
        # nomes de modelo retornados pelo actor (veja notas no README).
        if melhor_match is not None and melhor_score >= 0.55:
            anuncio.valor_fipe = melhor_match.valor
            anuncio.gap_percentual = round(
                (anuncio.preco - melhor_match.valor) / melhor_match.valor * 100, 2
            )

    return anuncios
