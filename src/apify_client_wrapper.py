"""
apify_client_wrapper.py
Wrapper fino em torno do SDK oficial `apify-client` para rodar os actors
de scraping do Webmotors e iCarros e devolver os dados já em lista de dicts.

IMPORTANTE - antes de usar:
1. Crie uma conta em https://apify.com e gere um API token em
   Settings > Integrations.
2. Escolha os actors específicos que você vai usar (existem várias opções
   na Apify Store para Webmotors e iCarros - busque "webmotors" e "icarros").
   Cada actor tem seu PRÓPRIO input schema (nomes de campos de busca,
   filtros de marca/modelo/estado, etc.) - ajuste o dict `run_input` no
   `.actor().call()` de acordo com o schema do actor escolhido.
3. Preencha ACTOR_ID_WEBMOTORS e ACTOR_ID_ICARROS abaixo (formato:
   "username/nome-do-actor", visível na URL do actor na Apify Store).

Este arquivo assume que os campos de saída de cada actor podem variar.
Por isso o mapeamento de campos (o "de-para" entre o que o actor retorna
e o schema comum do nosso pipeline) fica isolado em `normalize.py` -
depois de rodar uma vez, olhe o output real no Apify Console e ajuste o
mapeamento lá.
"""

from __future__ import annotations

import os
from typing import Any

from apify_client import ApifyClient

def _obter_config(nome: str, padrao: str = "") -> str:
    """
    Busca uma configuração primeiro nas variáveis de ambiente (uso local /
    scripts) e, se não encontrar, nos Secrets do Streamlit Cloud (uso do
    site publicado). Isso permite que o mesmo código funcione tanto rodando
    localmente quanto publicado no Streamlit Community Cloud.
    """
    valor = os.environ.get(nome, "")
    if valor:
        return valor
    try:
        import streamlit as st

        return st.secrets.get(nome, padrao)
    except Exception:
        return padrao


APIFY_TOKEN = _obter_config("APIFY_TOKEN")

# Preencha com os actors que você escolher na Apify Store.
# Exemplos encontrados publicamente (confirme o nome exato antes de usar,
# a Apify Store muda com frequência):
#   - "stealth_mode/webmotors-auto-search-scraper"
#   - "ribtools/webmotors-scraper"
# Para iCarros, busque "icarros" na Apify Store - há opções equivalentes.
ACTOR_ID_WEBMOTORS = _obter_config("APIFY_ACTOR_WEBMOTORS")
ACTOR_ID_ICARROS = _obter_config("APIFY_ACTOR_ICARROS")


class MarketplaceScraperClient:
    def __init__(self, token: str = APIFY_TOKEN):
        if not token:
            raise ValueError(
                "APIFY_TOKEN não configurado. Defina a variável de ambiente "
                "APIFY_TOKEN com o seu token da conta Apify."
            )
        self.client = ApifyClient(token)

    def _run_actor_and_fetch(self, actor_id: str, run_input: dict[str, Any]) -> list[dict]:
        """Roda o actor de forma síncrona e retorna todos os itens do dataset."""
        if not actor_id:
            raise ValueError(
                "actor_id vazio. Configure ACTOR_ID_WEBMOTORS / ACTOR_ID_ICARROS "
                "com o actor escolhido na Apify Store."
            )
        run = self.client.actor(actor_id).call(run_input=run_input)
        dataset_id = run["defaultDatasetId"]
        items = list(self.client.dataset(dataset_id).iterate_items())
        return items

    def buscar_webmotors(
        self,
        marca: str,
        modelo: str,
        estado: str = "sp",
        max_paginas: int = 5,
    ) -> list[dict]:
        """
        Busca anúncios no Webmotors para uma marca/modelo/estado.
        AJUSTE os nomes dos campos de `run_input` conforme o input schema
        real do actor escolhido (veja a aba "Input" do actor na Apify Store).
        """
        run_input = {
            "marca": marca,
            "modelo": modelo,
            "estado": estado,
            "maxPages": max_paginas,
        }
        return self._run_actor_and_fetch(ACTOR_ID_WEBMOTORS, run_input)

    def buscar_icarros(
        self,
        marca: str,
        modelo: str,
        estado: str = "sp",
        max_paginas: int = 5,
    ) -> list[dict]:
        """Busca anúncios no iCarros para uma marca/modelo/estado. Mesma observação acima."""
        run_input = {
            "marca": marca,
            "modelo": modelo,
            "estado": estado,
            "maxPages": max_paginas,
        }
        return self._run_actor_and_fetch(ACTOR_ID_ICARROS, run_input)


if __name__ == "__main__":
    # Teste manual (requer APIFY_TOKEN configurado e internet - não roda no sandbox)
    scraper = MarketplaceScraperClient()
    anuncios = scraper.buscar_webmotors(marca="chevrolet", modelo="tracker", estado="sc")
    print(f"{len(anuncios)} anúncios encontrados. Ex.: {anuncios[:1]}")
