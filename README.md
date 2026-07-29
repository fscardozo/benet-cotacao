# Cotação FIPE + Mercado

Site (Streamlit) para consultar, para um veículo específico, o valor FIPE e
o preço praticado no mercado (Webmotors + OLX, via Apify). Você escolhe
marca, modelo e ano em menus em cascata alimentados direto pela FIPE, e o
site mostra: valor FIPE, mínimo/médio/mediano/máximo de mercado, gap % vs.
FIPE, e a lista de anúncios individuais com link.

## Actors do Apify usados

- **Webmotors**: `ribtools/webmotors-scraper`
- **OLX Brasil (carros)**: `israeloriente/olx-cars-scraper`

Os nomes de campo de entrada/saída desses dois actors já estão configurados
em `apify_client_wrapper.py` e `normalize.py` (confirmados na documentação
pública de cada um em julho/2026). Se um dia esses actors mudarem de nome,
saírem do ar, ou você trocar por outro, é só ajustar esses dois arquivos.

## Rodar localmente

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt

export APIFY_TOKEN="seu_token_da_conta_apify"
export APIFY_ACTOR_WEBMOTORS="ribtools/webmotors-scraper"
export APIFY_ACTOR_OLX="israeloriente/olx-cars-scraper"

streamlit run src/app.py
```

## Publicar de graça (sem programar)

Veja o passo a passo completo em `DEPLOY.md` (GitHub + Streamlit Community
Cloud).

## Por que Apify em vez de scraping próprio

Webmotors e OLX têm proteção ativa anti-bot e Termos de Uso que restringem
raspagem automatizada. Em vez de construir e manter um scraper próprio, o
site usa actors de terceiros já especializados nesses sites - eles absorvem
a manutenção técnica e você paga por volume de dados consultados.

## Limitações conhecidas

- A busca no Webmotors usa uma URL montada automaticamente a partir da
  capital do estado escolhido, num raio de 500km (cobre o estado inteiro,
  às vezes um pouco de estados vizinhos). Se os resultados vierem vazios
  ou incorretos para algum estado, é possível passar uma URL de busca
  copiada manualmente do navegador via o parâmetro `url_manual` de
  `buscar_webmotors()`.
- O gap % é calculado usando o valor FIPE oficial que nós mesmos
  consultamos (mais confiável) — mas quando o anúncio já vem com um valor
  FIPE do próprio portal (`fipe_do_anuncio`), ele aparece na tabela como
  referência extra.
