"""
apify_client_wrapper.py
Wrapper em torno do SDK oficial `apify-client`, já configurado para os dois
actors escolhidos:

- Webmotors: ribtools/webmotors-scraper
  Input real: {"startUrls": [{"url": "..."}], "maxRequests": int}
  (confirmado na aba Input do actor em apify.com/ribtools/webmotors-scraper)

- OLX Brasil (carros): israeloriente/olx-cars-scraper
  Input real: {"state": "sp", "brand": "Toyota", "search": "corolla xei",
  "year_from": 2020, "year_to": 2024, "ads_limit": 100, ...}
  (confirmado no README do actor em apify.com/israeloriente/olx-cars-scraper)

Os dois schemas são bem diferentes entre si - por isso cada função de busca
monta o `run_input` do seu jeito específico.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Any

from apify_client import ApifyClient

# ----------------------------------------------------------------------
# Config (variáveis de ambiente locais ou Secrets do Streamlit Cloud)
# ----------------------------------------------------------------------
def _obter_config(nome: str, padrao: str = "") -> str:
    valor = os.environ.get(nome, "")
    if valor:
        return valor
    try:
        import streamlit as st

        return st.secrets.get(nome, padrao)
    except Exception:
        return padrao


APIFY_TOKEN = _obter_config("APIFY_TOKEN")
ACTOR_ID_WEBMOTORS = _obter_config("APIFY_ACTOR_WEBMOTORS", "ribtools/webmotors-scraper")
ACTOR_ID_OLX = _obter_config("APIFY_ACTOR_OLX", "israeloriente/olx-cars-scraper")


# ----------------------------------------------------------------------
# Tabela de capitais por UF (usada só para o Webmotors, que exige uma
# localização de referência na URL de busca - buscamos num raio amplo a
# partir da capital pra cobrir o estado inteiro).
# ----------------------------------------------------------------------
_CAPITAIS_UF = {
    "ac": ("Rio Branco", -9.9750, -67.8243), "al": ("Maceió", -9.6498, -35.7089),
    "ap": ("Macapá", 0.0349, -51.0694), "am": ("Manaus", -3.1190, -60.0217),
    "ba": ("Salvador", -12.9718, -38.5011), "ce": ("Fortaleza", -3.7172, -38.5433),
    "df": ("Brasília", -15.7939, -47.8828), "es": ("Vitória", -20.3155, -40.3128),
    "go": ("Goiânia", -16.6869, -49.2648), "ma": ("São Luís", -2.5307, -44.3068),
    "mt": ("Cuiabá", -15.6014, -56.0979), "ms": ("Campo Grande", -20.4697, -54.6201),
    "mg": ("Belo Horizonte", -19.9167, -43.9345), "pa": ("Belém", -1.4558, -48.4902),
    "pb": ("João Pessoa", -7.1195, -34.8450), "pr": ("Curitiba", -25.4284, -49.2733),
    "pe": ("Recife", -8.0476, -34.8770), "pi": ("Teresina", -5.0892, -42.8019),
    "rj": ("Rio de Janeiro", -22.9068, -43.1729), "rn": ("Natal", -5.7945, -35.2110),
    "rs": ("Porto Alegre", -30.0346, -51.2177), "ro": ("Porto Velho", -8.7619, -63.9039),
    "rr": ("Boa Vista", 2.8235, -60.6758), "sc": ("Florianópolis", -27.5954, -48.5480),
    "sp": ("São Paulo", -23.5505, -46.6333), "se": ("Aracaju", -10.9472, -37.0731),
    "to": ("Palmas", -10.1689, -48.3317),
}


def _slugificar(texto: str) -> str:
    """Remove acentos e espaços, deixa minúsculo (para montar paths de URL)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip().replace(" ", "-")


def _montar_url_busca_webmotors(marca: str, modelo: str, estado: str) -> str:
    """
    Monta uma URL de busca do Webmotors a partir de marca/modelo/estado.
    Busca num raio de 500km a partir da capital do estado (cobre o estado
    inteiro, e às vezes estados vizinhos - aceitável para pesquisa de
    mercado). Se os resultados vierem vazios ou errados, prefira copiar a
    URL de uma busca manual feita direto em webmotors.com.br e usar o
    parâmetro `url_manual` das funções abaixo.
    """
    uf = estado.lower()
    cidade, lat, lon = _CAPITAIS_UF.get(uf, _CAPITAIS_UF["sp"])
    marca_slug = _slugificar(marca)
    modelo_slug = _slugificar(modelo)
    cidade_param = cidade.replace(" ", "%20")
    return (
        f"https://www.webmotors.com.br/carros/{uf}-{_slugificar(cidade)}/{marca_slug}/{modelo_slug}"
        f"?tipoveiculo=carros&localizacao={lat},{lon}x500km"
        f"&estadocidade={cidade_param}&marca1={marca}&modelo1={modelo}&page=1"
    )


class MarketplaceScraperClient:
    def __init__(self, token: str = APIFY_TOKEN):
        if not token:
            raise ValueError(
                "APIFY_TOKEN não configurado. Defina a variável de ambiente "
                "(ou o Secret, no Streamlit Cloud) APIFY_TOKEN."
            )
        self.client = ApifyClient(token)

    def _run_actor_and_fetch(self, actor_id: str, run_input: dict[str, Any]) -> list[dict]:
        if not actor_id:
            raise ValueError("actor_id vazio. Configure APIFY_ACTOR_WEBMOTORS / APIFY_ACTOR_OLX.")
        run = self.client.actor(actor_id).call(run_input=run_input)
        dataset_id = run["defaultDatasetId"]
        return list(self.client.dataset(dataset_id).iterate_items())

    def buscar_webmotors(
        self,
        marca: str,
        modelo: str,
        estado: str = "sp",
        max_paginas: int = 3,
        url_manual: str | None = None,
    ) -> list[dict]:
        """
        Busca anúncios no Webmotors. `max_paginas` aqui vira `maxRequests`
        (nº de veículos, não páginas, nesse actor). Se `url_manual` for
        passado, usa ela em vez de montar a URL automaticamente (útil se a
        busca automática não achar o veículo certo).
        """
        url_busca = url_manual or _montar_url_busca_webmotors(marca, modelo, estado)
        run_input = {
            "startUrls": [{"url": url_busca}],
            "maxRequests": max_paginas * 10,
        }
        return self._run_actor_and_fetch(ACTOR_ID_WEBMOTORS, run_input)

    def buscar_olx(
        self,
        marca: str,
        modelo: str,
        estado: str = "sp",
        max_paginas: int = 3,
        ano_de: int | None = None,
        ano_ate: int | None = None,
    ) -> list[dict]:
        """
        Busca anúncios na OLX (actor israeloriente/olx-cars-scraper).
        `marca` é limpa de prefixos tipo "GM - " (comuns na nomenclatura da
        FIPE) antes de enviar, já que a OLX espera o nome "puro" da marca.
        """
        marca_limpa = marca.split(" - ")[-1].strip()
        run_input: dict[str, Any] = {
            "state": estado.lower(),
            "brand": marca_limpa,
            "search": modelo,
            "ads_limit": min(max_paginas * 30, 300),
        }
        if ano_de:
            run_input["year_from"] = ano_de
        if ano_ate:
            run_input["year_to"] = ano_ate
        return self._run_actor_and_fetch(ACTOR_ID_OLX, run_input)


if __name__ == "__main__":
    # Teste manual (requer APIFY_TOKEN configurado e internet - não roda no sandbox)
    scraper = MarketplaceScraperClient()
    anuncios = scraper.buscar_olx(marca="Chevrolet", modelo="Onix", estado="sp")
    print(f"{len(anuncios)} anúncios encontrados. Ex.: {anuncios[:1]}")
