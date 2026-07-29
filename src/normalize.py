"""
normalize.py
Normaliza os anúncios do Webmotors (ribtools/webmotors-scraper) e da OLX
(israeloriente/olx-cars-scraper) para um schema comum, e cruza com o valor
FIPE oficial (via fipe_client) para calcular o gap de preço.

Os nomes de campo abaixo (CAMPOS_WEBMOTORS / CAMPOS_OLX) foram confirmados
na documentação pública de cada actor em julho/2026. Se a Apify Store
mudar o output desses actors no futuro, ajuste só os dicts de mapeamento
aqui - o resto do pipeline não muda.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from fipe_client import FipeClient, ValorFipe


@dataclass
class AnuncioNormalizado:
    portal: str  # "webmotors" ou "olx"
    marca: str
    modelo: str
    versao: str
    ano_modelo: int
    km: int | None
    preco: float
    url: str
    fipe_do_anuncio: float | None = None  # valor FIPE que o próprio portal já mostra (quando disponível)
    valor_fipe: float | None = None  # valor FIPE oficial, cruzado por nós via fipe_client
    gap_percentual: float | None = None  # (preco - valor_fipe) / valor_fipe * 100


# Nomes de campo confirmados na aba "Output" do actor ribtools/webmotors-scraper
CAMPOS_WEBMOTORS = {
    "make": "marca",
    "model": "modelo",
    "version": "versao",
    "model_year": "ano_modelo",
    "km": "km",
    "price": "preco",
    "url": "url",
    "fipe_price": "fipe_do_anuncio",
}

# Nomes de campo confirmados no README do actor israeloriente/olx-cars-scraper
CAMPOS_OLX = {
    "brand": "marca",
    "model": "modelo",
    "year": "ano_modelo",
    "mileage": "km",
    "price": "preco",
    "url": "url",
    "fipe_price": "fipe_do_anuncio",
}


def _mapear_campos(item_bruto: dict, mapeamento: dict[str, str], portal: str) -> AnuncioNormalizado:
    dados: dict = {}
    for campo_origem, campo_destino in mapeamento.items():
        dados[campo_destino] = item_bruto.get(campo_origem)

    def _int_seguro(valor) -> int | None:
        try:
            return int(valor) if valor not in (None, "") else None
        except (ValueError, TypeError):
            return None

    def _float_seguro(valor) -> float | None:
        try:
            return float(valor) if valor not in (None, "") else None
        except (ValueError, TypeError):
            return None

    return AnuncioNormalizado(
        portal=portal,
        marca=str(dados.get("marca", "") or "").strip(),
        modelo=str(dados.get("modelo", "") or "").strip(),
        versao=str(dados.get("versao", "") or "").strip(),
        ano_modelo=_int_seguro(dados.get("ano_modelo")) or 0,
        km=_int_seguro(dados.get("km")),
        preco=_float_seguro(dados.get("preco")) or 0.0,
        url=str(dados.get("url", "") or "").strip(),
        fipe_do_anuncio=_float_seguro(dados.get("fipe_do_anuncio")),
    )


def normalizar_webmotors(itens_brutos: list[dict]) -> list[AnuncioNormalizado]:
    return [_mapear_campos(item, CAMPOS_WEBMOTORS, "webmotors") for item in itens_brutos]


def normalizar_olx(itens_brutos: list[dict]) -> list[AnuncioNormalizado]:
    return [_mapear_campos(item, CAMPOS_OLX, "olx") for item in itens_brutos]


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
    `fipe_client` para os modelos de interesse - ver main.py/consultar_veiculo.py).

    Se o anúncio já veio com `fipe_do_anuncio` (Webmotors e OLX às vezes
    mostram isso direto) e não achamos um match melhor na nossa tabela,
    caímos de volta nesse valor.
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

        if melhor_match is not None and melhor_score >= 0.55:
            anuncio.valor_fipe = melhor_match.valor
        elif anuncio.fipe_do_anuncio:
            anuncio.valor_fipe = anuncio.fipe_do_anuncio

        if anuncio.valor_fipe:
            anuncio.gap_percentual = round(
                (anuncio.preco - anuncio.valor_fipe) / anuncio.valor_fipe * 100, 2
            )

    return anuncios
