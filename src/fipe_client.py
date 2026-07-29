"""
fipe_client.py
Cliente para a API pública da FIPE (https://fipe.parallelum.com.br).

Essa API espelha a tabela oficial FIPE. Não requer autenticação para uso
básico, mas tem rate limit (então cacheamos localmente em SQLite para não
bater no limite toda vez que rodamos o pipeline).

Uso típico:
    client = FipeClient()
    marcas = client.listar_marcas()
    modelos = client.listar_modelos(codigo_marca="59")  # ex: Chevrolet
    anos = client.listar_anos(codigo_marca="59", codigo_modelo="5940")
    valor = client.consultar_valor(codigo_marca="59", codigo_modelo="5940", codigo_ano="2021-1")
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

FIPE_BASE_URL = "https://fipe.parallelum.com.br/api/v2"
DB_PATH = Path(__file__).parent.parent / "output" / "fipe_cache.db"

# Tipo de veículo na API: carros, motos, caminhoes
TIPO_VEICULO = "cars"


@dataclass
class ValorFipe:
    codigo_marca: str
    codigo_modelo: str
    codigo_ano: str
    marca: str
    modelo: str
    ano_modelo: int
    combustivel: str
    valor: float  # em reais, já convertido de "R$ 45.000,00" para float
    mes_referencia: str


class FipeClient:
    def __init__(self, use_cache: bool = True, request_delay_seconds: float = 0.5):
        self.use_cache = use_cache
        self.request_delay_seconds = request_delay_seconds
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        if self.use_cache:
            self._init_cache()

    # ------------------------------------------------------------------
    # Cache local (SQLite) para reduzir chamadas repetidas à API pública
    # ------------------------------------------------------------------
    def _init_cache(self) -> None:
        # Se a pasta não puder ser escrita (comum em algumas hospedagens em
        # nuvem), desliga o cache silenciosamente em vez de quebrar o app -
        # o cache é só uma otimização, não uma dependência.
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(DB_PATH)
        except OSError:
            self.use_cache = False
            return
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fipe_valores (
                codigo_marca TEXT,
                codigo_modelo TEXT,
                codigo_ano TEXT,
                marca TEXT,
                modelo TEXT,
                ano_modelo INTEGER,
                combustivel TEXT,
                valor REAL,
                mes_referencia TEXT,
                consultado_em TEXT,
                PRIMARY KEY (codigo_marca, codigo_modelo, codigo_ano)
            )
            """
        )
        self._conn.commit()

    def _cache_get(self, codigo_marca: str, codigo_modelo: str, codigo_ano: str) -> ValorFipe | None:
        if not self.use_cache:
            return None
        cur = self._conn.execute(
            "SELECT * FROM fipe_valores WHERE codigo_marca=? AND codigo_modelo=? AND codigo_ano=?",
            (codigo_marca, codigo_modelo, codigo_ano),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        data = dict(zip(cols, row))
        return ValorFipe(
            codigo_marca=data["codigo_marca"],
            codigo_modelo=data["codigo_modelo"],
            codigo_ano=data["codigo_ano"],
            marca=data["marca"],
            modelo=data["modelo"],
            ano_modelo=data["ano_modelo"],
            combustivel=data["combustivel"],
            valor=data["valor"],
            mes_referencia=data["mes_referencia"],
        )

    def _cache_set(self, v: ValorFipe) -> None:
        if not self.use_cache:
            return
        self._conn.execute(
            """
            INSERT OR REPLACE INTO fipe_valores
            (codigo_marca, codigo_modelo, codigo_ano, marca, modelo, ano_modelo,
             combustivel, valor, mes_referencia, consultado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                v.codigo_marca, v.codigo_modelo, v.codigo_ano, v.marca, v.modelo,
                v.ano_modelo, v.combustivel, v.valor, v.mes_referencia,
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Chamadas à API
    # ------------------------------------------------------------------
    def _get(self, path: str) -> Any:
        url = f"{FIPE_BASE_URL}/{path}"
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        time.sleep(self.request_delay_seconds)  # respeita rate limit da API pública
        return resp.json()

    def listar_marcas(self) -> list[dict]:
        """Retorna todas as marcas disponíveis: [{"code": "59", "name": "Chevrolet"}, ...]"""
        return self._get(f"{TIPO_VEICULO}/brands")

    def listar_modelos(self, codigo_marca: str) -> list[dict]:
        """Retorna os modelos de uma marca."""
        return self._get(f"{TIPO_VEICULO}/brands/{codigo_marca}/models")

    def listar_anos(self, codigo_marca: str, codigo_modelo: str) -> list[dict]:
        """Retorna os anos/versões disponíveis para um modelo."""
        return self._get(f"{TIPO_VEICULO}/brands/{codigo_marca}/models/{codigo_modelo}/years")

    def buscar_por_nome(
        self, nome_marca: str, nome_modelo: str, ano_desejado: int
    ) -> ValorFipe | None:
        """
        Busca o valor FIPE a partir de nomes em texto livre (ex.: marca="Chevrolet",
        modelo="Onix Sedan LT 1.0", ano_desejado=2024), sem precisar saber os
        códigos internos da FIPE. Usa correspondência aproximada (fuzzy) nos
        nomes de marca e modelo, e casa o ano mais próximo disponível.

        Retorna None se não encontrar nenhuma marca/modelo com similaridade
        mínima aceitável (evita retornar um valor de um carro completamente
        diferente por engano).
        """
        from difflib import SequenceMatcher

        def _sim(a: str, b: str) -> float:
            return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

        marcas = self.listar_marcas()
        melhor_marca = max(marcas, key=lambda m: _sim(m["name"], nome_marca))
        if _sim(melhor_marca["name"], nome_marca) < 0.5:
            return None

        modelos = self.listar_modelos(codigo_marca=melhor_marca["code"])
        melhor_modelo = max(modelos, key=lambda m: _sim(m["name"], nome_modelo))
        if _sim(melhor_modelo["name"], nome_modelo) < 0.4:
            return None

        anos = self.listar_anos(
            codigo_marca=melhor_marca["code"], codigo_modelo=melhor_modelo["code"]
        )
        if not anos:
            return None

        def _extrair_ano(codigo_ano: str) -> int:
            try:
                return int(codigo_ano.split("-")[0])
            except ValueError:
                return 0

        melhor_ano = min(anos, key=lambda a: abs(_extrair_ano(a["code"]) - ano_desejado))

        return self.consultar_valor(
            codigo_marca=melhor_marca["code"],
            codigo_modelo=melhor_modelo["code"],
            codigo_ano=melhor_ano["code"],
        )

    def consultar_valor(self, codigo_marca: str, codigo_modelo: str, codigo_ano: str) -> ValorFipe:
        """Consulta o valor FIPE de uma combinação marca/modelo/ano. Usa cache local quando possível."""
        cached = self._cache_get(codigo_marca, codigo_modelo, codigo_ano)
        if cached is not None:
            return cached

        data = self._get(
            f"{TIPO_VEICULO}/brands/{codigo_marca}/models/{codigo_modelo}/years/{codigo_ano}"
        )
        valor_str = data["price"]  # ex: "R$ 45.678,00"
        valor_float = float(
            valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
        )
        v = ValorFipe(
            codigo_marca=codigo_marca,
            codigo_modelo=codigo_modelo,
            codigo_ano=codigo_ano,
            marca=data.get("brand", ""),
            modelo=data.get("model", ""),
            ano_modelo=data.get("modelYear", 0),
            combustivel=data.get("fuel", ""),
            valor=valor_float,
            mes_referencia=data.get("referenceMonth", ""),
        )
        self._cache_set(v)
        return v


if __name__ == "__main__":
    # Teste manual rápido (requer internet — não roda no sandbox de desenvolvimento)
    client = FipeClient()
    marcas = client.listar_marcas()
    print(f"{len(marcas)} marcas encontradas. Ex.: {marcas[:3]}")
