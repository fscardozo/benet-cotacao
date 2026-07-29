"""
consultar_veiculo.py
Consulta pontual: você informa marca, modelo, versão e ano de um veículo, e
recebe o valor FIPE + o valor praticado no mercado (Webmotors/iCarros via
Apify) para veículos comparáveis.

Uso:
    python src/consultar_veiculo.py --marca "Chevrolet" --modelo "Onix Sedan LT 1.0" --ano 2024 --estado sp

Ou importando a função diretamente:
    from consultar_veiculo import consultar_veiculo
    resultado = consultar_veiculo("Chevrolet", "Onix Sedan LT 1.0", 2024, estado="sp")
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from apify_client_wrapper import MarketplaceScraperClient
from fipe_client import FipeClient, ValorFipe
from normalize import AnuncioNormalizado, normalizar_icarros, normalizar_webmotors


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
) -> ResultadoConsulta:
    fipe_client = FipeClient()
    scraper = MarketplaceScraperClient()

    # 1. Valor FIPE
    valor_fipe_obj: ValorFipe | None = fipe_client.buscar_por_nome(
        nome_marca=marca, nome_modelo=modelo, ano_desejado=ano
    )
    valor_fipe = valor_fipe_obj.valor if valor_fipe_obj else None

    # 2. Anúncios de mercado equivalentes
    brutos_wm = scraper.buscar_webmotors(marca=marca, modelo=modelo, estado=estado, max_paginas=max_paginas)
    brutos_ic = scraper.buscar_icarros(marca=marca, modelo=modelo, estado=estado, max_paginas=max_paginas)

    anuncios = normalizar_webmotors(brutos_wm) + normalizar_icarros(brutos_ic)
    # Filtra só o ano pedido (± 0, pode relaxar pra ano-1/ano+1 se vier pouco resultado)
    anuncios = [a for a in anuncios if a.ano_modelo == ano and a.preco > 0]

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
            print(
                f"  [{a.portal}] R$ {a.preco:,.2f} | {a.km or '?'} km | "
                f"{a.cidade}/{a.estado} | {a.anunciante} | {a.url}"
            )
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
