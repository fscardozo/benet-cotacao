"""
consultar_veiculo.py
Consulta pontual: você informa marca, modelo, versão e ano de um veículo, e
recebe o valor FIPE + o valor praticado no mercado (Webmotors + OLX, via
Apify) para veículos comparáveis.

Uso via linha de comando (busca a FIPE por nome, com correspondência aproximada):
    python src/consultar_veiculo.py --marca "Chevrolet" --modelo "Onix Sedan LT 1.0" --ano 2024 --estado sp

Uso programático com código FIPE exato (usado pelo app.py, que já sabe o
código exato por causa dos menus em cascata):
    from consultar_veiculo import consultar_veiculo
    resultado = consultar_veiculo(
        marca="Chevrolet", modelo="Onix Sedan LT 1.0", ano=2024, estado="sp",
        codigo_marca="59", codigo_modelo="5940", codigo_ano="2024-1",
    )
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from apify_client_wrapper import MarketplaceScraperClient
from fipe_client import FipeClient, ValorFipe
from normalize import AnuncioNormalizado, normalizar_olx, normalizar_webmotors


@dataclass
class ResultadoConsulta:
    marca: str
    modelo: str
    ano: int
    valor_fipe: float | None
    quantidade_anuncios: int
    preco_minimo: float | None
    preco_medio: float | None
    preco_mediano: float | None
    preco_maximo: float | None
    gap_medio_percentual: float | None  # (preço médio de mercado - FIPE) / FIPE * 100
    anuncios: list[AnuncioNormalizado]


def consultar_veiculo(
    marca: str,
    modelo: str,
    ano: int,
    estado: str = "sp",
    max_paginas: int = 3,
    codigo_marca: str | None = None,
    codigo_modelo: str | None = None,
    codigo_ano: str | None = None,
) -> ResultadoConsulta:
    fipe_client = FipeClient()
    scraper = MarketplaceScraperClient()

    # 1. Valor FIPE - usa os códigos exatos se disponíveis (mais preciso;
    #    é o que o app.py manda, já que os menus em cascata sempre têm o
    #    código certo), senão cai pra busca aproximada por nome.
    valor_fipe_obj: ValorFipe | None
    if codigo_marca and codigo_modelo and codigo_ano:
        valor_fipe_obj = fipe_client.consultar_valor(codigo_marca, codigo_modelo, codigo_ano)
    else:
        valor_fipe_obj = fipe_client.buscar_por_nome(
            nome_marca=marca, nome_modelo=modelo, ano_desejado=ano
        )
    valor_fipe = valor_fipe_obj.valor if valor_fipe_obj else None

    # 2. Anúncios de mercado equivalentes
    brutos_wm = scraper.buscar_webmotors(marca=marca, modelo=modelo, estado=estado, max_paginas=max_paginas)
    brutos_olx = scraper.buscar_olx(
        marca=marca, modelo=modelo, estado=estado, max_paginas=max_paginas,
        ano_de=ano, ano_ate=ano,
    )

    anuncios = normalizar_webmotors(brutos_wm) + normalizar_olx(brutos_olx)
    # Filtra só o ano pedido e preços válidos
    anuncios = [a for a in anuncios if a.ano_modelo == ano and a.preco > 0]

    # Cruza com a FIPE (usa o mesmo valor já consultado acima como única
    # entrada da "tabela local", já que aqui é uma consulta pontual de um
    # único modelo/ano - não precisa buscar mais nada)
    if valor_fipe_obj:
        for a in anuncios:
            a.valor_fipe = valor_fipe_obj.valor
            a.gap_percentual = round((a.preco - valor_fipe_obj.valor) / valor_fipe_obj.valor * 100, 2)
    else:
        for a in anuncios:
            if a.fipe_do_anuncio:
                a.valor_fipe = a.fipe_do_anuncio
                a.gap_percentual = round((a.preco - a.fipe_do_anuncio) / a.fipe_do_anuncio * 100, 2)

    precos = [a.preco for a in anuncios]
    preco_medio = statistics.mean(precos) if precos else None
    gap_medio = (
        round((preco_medio - valor_fipe) / valor_fipe * 100, 2)
        if (preco_medio is not None and valor_fipe)
        else None
    )

    return ResultadoConsulta(
        marca=marca,
        modelo=modelo,
        ano=ano,
        valor_fipe=valor_fipe,
        quantidade_anuncios=len(precos),
        preco_minimo=min(precos) if precos else None,
        preco_medio=preco_medio,
        preco_mediano=statistics.median(precos) if precos else None,
        preco_maximo=max(precos) if precos else None,
        gap_medio_percentual=gap_medio,
        anuncios=anuncios,
    )


def imprimir_resultado(r: ResultadoConsulta) -> None:
    print(f"\n=== {r.marca} {r.modelo} {r.ano} ===\n")

    if r.valor_fipe is not None:
        print(f"Valor FIPE: R$ {r.valor_fipe:,.2f}")
    else:
        print("Valor FIPE: não encontrado (confira a grafia da marca/modelo)")

    print(f"Anúncios encontrados no mercado: {r.quantidade_anuncios}")
    if r.quantidade_anuncios:
        print(f"  Preço mínimo:  R$ {r.preco_minimo:,.2f}")
        print(f"  Preço médio:   R$ {r.preco_medio:,.2f}")
        print(f"  Preço mediano: R$ {r.preco_mediano:,.2f}")
        print(f"  Preço máximo:  R$ {r.preco_maximo:,.2f}")
        if r.gap_medio_percentual is not None:
            sinal = "acima" if r.gap_medio_percentual > 0 else "abaixo"
            print(f"  Mercado está {abs(r.gap_medio_percentual)}% {sinal} da FIPE, em média")

        print("\nAnúncios individuais:")
        for a in sorted(r.anuncios, key=lambda x: x.preco):
            print(f"  [{a.portal}] R$ {a.preco:,.2f} | {a.km or '?'} km | {a.url}")
    else:
        print("  Nenhum anúncio comparável encontrado no mercado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta FIPE + valor de mercado de um veículo")
    parser.add_argument("--marca", required=True, help='Ex: "Chevrolet"')
    parser.add_argument("--modelo", required=True, help='Ex: "Onix Sedan LT 1.0"')
    parser.add_argument("--ano", required=True, type=int, help="Ex: 2024")
    parser.add_argument("--estado", default="sp", help="UF para buscar anúncios (padrão: sp)")
    args = parser.parse_args()

    resultado = consultar_veiculo(args.marca, args.modelo, args.ano, estado=args.estado)
    imprimir_resultado(resultado)


if __name__ == "__main__":
    main()
