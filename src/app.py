"""
app.py
Site (Streamlit) para consultar FIPE + valor de mercado de um veículo.
Marca/modelo/ano são escolhidos em menus em cascata alimentados direto pela
FIPE (evita erro de digitação e ambiguidade de nome).

Rodar localmente:
    streamlit run src/app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from consultar_veiculo import consultar_veiculo
from fipe_client import FipeClient

st.set_page_config(page_title="Cotação FIPE + Mercado - Benet", page_icon="🚗", layout="centered")

st.title("🚗 Cotação FIPE + Mercado")
st.caption("Escolha marca, modelo e ano para ver o valor FIPE e o preço praticado no mercado (Webmotors/OLX).")


# ------------------------------------------------------------------
# Funções com cache: a tabela FIPE muda no máximo uma vez por mês, então
# cacheamos por 1 dia pra não bater a API pública a cada clique do usuário.
# ------------------------------------------------------------------
@st.cache_data(ttl=86400)
def carregar_marcas() -> list[dict]:
    return FipeClient(use_cache=False).listar_marcas()


@st.cache_data(ttl=86400)
def carregar_modelos(codigo_marca: str) -> list[dict]:
    return FipeClient(use_cache=False).listar_modelos(codigo_marca)


@st.cache_data(ttl=86400)
def carregar_anos(codigo_marca: str, codigo_modelo: str) -> list[dict]:
    return FipeClient(use_cache=False).listar_anos(codigo_marca, codigo_modelo)


try:
    marcas = carregar_marcas()
except Exception as e:
    st.error(f"Não consegui carregar a lista de marcas da FIPE. Detalhe técnico: {e}")
    st.stop()

nomes_marcas = [m["name"] for m in marcas]

col1, col2 = st.columns(2)
with col1:
    nome_marca = st.selectbox("Marca", nomes_marcas, index=None, placeholder="Escolha a marca")
with col2:
    estado = st.selectbox(
        "Estado (UF) para buscar anúncios",
        ["sp", "sc", "rj", "mg", "pr", "rs", "ba", "go", "pe", "ce", "df"],
        index=0,
    )

nome_modelo = None
nome_ano = None
codigo_marca = codigo_modelo = codigo_ano = None

if nome_marca:
    codigo_marca = next(m["code"] for m in marcas if m["name"] == nome_marca)
    modelos = carregar_modelos(codigo_marca)
    nomes_modelos = [m["name"] for m in modelos]
    nome_modelo = st.selectbox("Modelo / versão", nomes_modelos, index=None, placeholder="Escolha o modelo")

if nome_modelo:
    codigo_modelo = next(m["code"] for m in modelos if m["name"] == nome_modelo)
    anos = carregar_anos(codigo_marca, codigo_modelo)
    nomes_anos = [a["name"] for a in anos]
    nome_ano = st.selectbox("Ano", nomes_anos, index=None, placeholder="Escolha o ano")

if nome_ano:
    codigo_ano = next(a["code"] for a in anos if a["name"] == nome_ano)

enviar = st.button("Consultar", use_container_width=True, disabled=not (nome_marca and nome_modelo and nome_ano))

if enviar:
    ano_numerico = int(codigo_ano.split("-")[0])

    with st.spinner("Consultando FIPE e anúncios de mercado..."):
        try:
            resultado = consultar_veiculo(
                marca=nome_marca,
                modelo=nome_modelo,
                ano=ano_numerico,
                estado=estado,
                codigo_marca=codigo_marca,
                codigo_modelo=codigo_modelo,
                codigo_ano=codigo_ano,
            )
        except Exception as e:
            st.error(
                "Não consegui completar a consulta. Confira se o APIFY_TOKEN e os "
                "actors (APIFY_ACTOR_WEBMOTORS / APIFY_ACTOR_OLX) estão "
                f"configurados corretamente.\n\nDetalhe técnico: {e}"
            )
            st.stop()

    st.subheader(f"{resultado.marca} {resultado.modelo} {resultado.ano}")

    col_fipe, col_qtd = st.columns(2)
    with col_fipe:
        if resultado.valor_fipe is not None:
            st.metric("Valor FIPE", f"R$ {resultado.valor_fipe:,.2f}")
        else:
            st.warning("Valor FIPE não encontrado.")
    with col_qtd:
        st.metric("Anúncios encontrados", resultado.quantidade_anuncios)

    if resultado.quantidade_anuncios:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mínimo", f"R$ {resultado.preco_minimo:,.0f}")
        c2.metric("Médio", f"R$ {resultado.preco_medio:,.0f}")
        c3.metric("Mediano", f"R$ {resultado.preco_mediano:,.0f}")
        c4.metric("Máximo", f"R$ {resultado.preco_maximo:,.0f}")

        if resultado.gap_medio_percentual is not None:
            sinal = "acima" if resultado.gap_medio_percentual > 0 else "abaixo"
            st.info(
                f"O mercado está, em média, **{abs(resultado.gap_medio_percentual)}% {sinal}** "
                f"do valor FIPE."
            )

        st.subheader("Anúncios encontrados")
        df = pd.DataFrame(
            [
                {
                    "Portal": a.portal,
                    "Preço": a.preco,
                    "KM": a.km,
                    "Gap vs. FIPE (%)": a.gap_percentual,
                    "Link": a.url,
                }
                for a in sorted(resultado.anuncios, key=lambda x: x.preco)
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum anúncio comparável encontrado no mercado para esse ano/modelo.")
