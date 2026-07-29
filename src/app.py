"""
app.py
Site simples (Streamlit) para consultar FIPE + valor de mercado de um veículo.

Rodar localmente:
    streamlit run src/app.py

Colocar na internet de graça (sem programar):
    Veja o passo a passo em DEPLOY.md
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from consultar_veiculo import consultar_veiculo

st.set_page_config(page_title="Cotação FIPE + Mercado - Benet", page_icon="🚗", layout="centered")

st.title("🚗 Cotação FIPE + Mercado")
st.caption("Consulte o valor FIPE e o preço praticado no mercado (Webmotors/iCarros) para um veículo específico.")

with st.form("consulta"):
    col1, col2 = st.columns(2)
    with col1:
        marca = st.text_input("Marca", placeholder="Ex: Chevrolet")
        ano = st.number_input("Ano modelo", min_value=1990, max_value=2027, value=2024, step=1)
    with col2:
        modelo = st.text_input("Modelo / versão", placeholder="Ex: Onix Sedan LT 1.0")
        estado = st.selectbox(
            "Estado (UF) para buscar anúncios",
            ["sp", "sc", "rj", "mg", "pr", "rs", "ba", "go", "pe", "ce"],
            index=0,
        )
    enviar = st.form_submit_button("Consultar", use_container_width=True)

if enviar:
    if not marca or not modelo:
        st.error("Preencha marca e modelo antes de consultar.")
    else:
        with st.spinner("Consultando FIPE e anúncios de mercado..."):
            try:
                resultado = consultar_veiculo(marca, modelo, int(ano), estado=estado)
            except Exception as e:
                st.error(
                    "Não consegui completar a consulta. Confira se o APIFY_TOKEN e os "
                    "actors (APIFY_ACTOR_WEBMOTORS / APIFY_ACTOR_ICARROS) estão "
                    f"configurados corretamente.\n\nDetalhe técnico: {e}"
                )
                st.stop()

        st.subheader(f"{resultado.marca} {resultado.modelo} {resultado.ano}")

        col_fipe, col_qtd = st.columns(2)
        with col_fipe:
            if resultado.valor_fipe is not None:
                st.metric("Valor FIPE", f"R$ {resultado.valor_fipe:,.2f}")
            else:
                st.warning("Valor FIPE não encontrado — confira a grafia da marca/modelo.")
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
                        "Cidade": a.cidade,
                        "UF": a.estado,
                        "Anunciante": a.anunciante,
                        "Link": a.url,
                    }
                    for a in sorted(resultado.anuncios, key=lambda x: x.preco)
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum anúncio comparável encontrado no mercado para esse ano/modelo.")
