"""
main.py
Orquestra o pipeline completo de pesquisa de mercado da Benet:

1. Define a lista de modelos de interesse (estoque da Benet + concorrência).
2. Busca o valor FIPE de cada modelo/ano via `fipe_client`.
3. Busca anúncios no Webmotors e iCarros via `apify_client_wrapper`.
4. Normaliza e cruza os anúncios com o valor FIPE via `normalize`.
5. Gera dois relatórios em Excel:
   - posicionamento_preco.xlsx: gap % da Benet vs. mercado, por modelo.
   - mapa_concorrencia.xlsx: todos os anúncios de concorrentes, com preço,
     km, e gap vs. FIPE, ordenado por modelo.

Antes de rodar:
    export APIFY_TOKEN="seu_token_aqui"
    export APIFY_ACTOR_WEBMOTORS="usuario/nome-do-actor"
    export APIFY_ACTOR_ICARROS="usuario/nome-do-actor"
    pip install -r requirements.txt
    python src/main.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from apify_client_wrapper import MarketplaceScraperClient
from fipe_client import FipeClient
from normalize import cruzar_com_fipe, normalizar_icarros, normalizar_webmotors

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ----------------------------------------------------------------------
# 1. CONFIGURE AQUI os modelos que quer monitorar (estoque Benet +
#    modelos concorrentes relevantes). codigo_marca/codigo_modelo vêm da
#    API da FIPE (rode fipe_client.py isoladamente pra descobrir os
#    códigos certos - listar_marcas() e listar_modelos()).
# ----------------------------------------------------------------------
MODELOS_MONITORADOS = [
    # dict(marca_busca="chevrolet", modelo_busca="tracker",
    #      codigo_marca="59", codigo_modelo="5940", codigo_ano="2021-1",
    #      estado="sc"),
    # Adicione aqui cada modelo do estoque da Benet + concorrentes diretos.
]


def montar_tabela_fipe_local(fipe_client: FipeClient) -> list:
    tabela = []
    for modelo in MODELOS_MONITORADOS:
        valor = fipe_client.consultar_valor(
            codigo_marca=modelo["codigo_marca"],
            codigo_modelo=modelo["codigo_modelo"],
            codigo_ano=modelo["codigo_ano"],
        )
        tabela.append(valor)
    return tabela


def coletar_anuncios(scraper: MarketplaceScraperClient) -> list:
    todos_anuncios = []
    for modelo in MODELOS_MONITORADOS:
        brutos_wm = scraper.buscar_webmotors(
            marca=modelo["marca_busca"], modelo=modelo["modelo_busca"], estado=modelo["estado"]
        )
        brutos_ic = scraper.buscar_icarros(
            marca=modelo["marca_busca"], modelo=modelo["modelo_busca"], estado=modelo["estado"]
        )
        todos_anuncios.extend(normalizar_webmotors(brutos_wm))
        todos_anuncios.extend(normalizar_icarros(brutos_ic))
    return todos_anuncios


def gerar_relatorios(anuncios: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([vars(a) for a in anuncios])
    if df.empty:
        print("Nenhum anúncio coletado - confira a configuração dos actors/modelos.")
        return

    # Mapa de concorrência: todos os anúncios que não são da Benet
    mapa_concorrencia = df[~df["eh_benet"]].sort_values(["marca", "modelo", "preco"])
    mapa_concorrencia.to_excel(OUTPUT_DIR / "mapa_concorrencia.xlsx", index=False)

    # Posicionamento de preço: compara o gap médio da Benet vs. o gap médio
    # do mercado, por marca+modelo
    posicionamento = (
        df.groupby(["marca", "modelo", "eh_benet"])["gap_percentual"]
        .mean()
        .reset_index()
        .pivot(index=["marca", "modelo"], columns="eh_benet", values="gap_percentual")
        .rename(columns={True: "gap_medio_benet_pct", False: "gap_medio_mercado_pct"})
        .reset_index()
    )
    posicionamento.to_excel(OUTPUT_DIR / "posicionamento_preco.xlsx", index=False)

    print(f"Relatórios gerados em {OUTPUT_DIR}/")


def main() -> None:
    if not MODELOS_MONITORADOS:
        print(
            "Configure a lista MODELOS_MONITORADOS em main.py antes de rodar "
            "(veja o comentário de exemplo no código)."
        )
        return

    fipe_client = FipeClient()
    scraper = MarketplaceScraperClient()

    tabela_fipe = montar_tabela_fipe_local(fipe_client)
    anuncios = coletar_anuncios(scraper)
    anuncios = cruzar_com_fipe(anuncios, fipe_client, tabela_fipe)

    gerar_relatorios(anuncios)


if __name__ == "__main__":
    main()
