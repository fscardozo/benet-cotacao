# Pesquisa de Mercado - Benet Veículos

Ferramenta que cruza a tabela FIPE com anúncios de Webmotors/iCarros (via
Apify) para apoiar a compra de veículos: você informa marca/modelo/ano de um
carro que está cotando, e recebe o valor FIPE + o valor praticado no mercado
(mínimo, médio, mediano, máximo) com os anúncios individuais pra comparar.

Também tem um modo de monitoramento em lote (`src/main.py`), útil se um dia
quiser acompanhar vários modelos de uma vez em vez de consultar um por vez -
mas o uso principal hoje é a consulta pontual abaixo.

## Consulta pontual (uso principal)

Depois de configurar os passos 1-3 abaixo:

```bash
python src/consultar_veiculo.py --marca "Chevrolet" --modelo "Onix Sedan LT 1.0" --ano 2024 --estado sp
```

Saída esperada:
```
=== Chevrolet Onix Sedan LT 1.0 2024 ===

Valor FIPE: R$ 87.432,00
Anúncios encontrados no mercado: 3
  Preço mínimo:  R$ 82.500,00
  Preço médio:   R$ 85.766,67
  Preço mediano: R$ 84.900,00
  Preço máximo:  R$ 89.900,00
  Mercado está 1.9% abaixo da FIPE, em média

Anúncios individuais:
  [icarros] R$ 82.500,00 | 15000 km | Santos/SP | Revenda C | http://ic1
  [webmotors] R$ 84.900,00 | 12000 km | Sao Paulo/SP | Revenda A | http://wm1
  [webmotors] R$ 89.900,00 | 8000 km | Campinas/SP | Revenda B | http://wm2
```

A busca do valor FIPE é por nome (você não precisa saber os códigos internos
da FIPE) - o `fipe_client.buscar_por_nome()` faz correspondência aproximada
de marca/modelo e pega o ano mais próximo do pedido.

## Passo a passo para colocar no ar

### 1. Instalar dependências
```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
```

### 2. Escolher os actors no Apify
1. Crie uma conta em https://apify.com (tem plano gratuito com créditos).
2. Na Apify Store, busque **"webmotors"** e **"icarros"** e escolha os
   actors que melhor atendem (existem várias opções de terceiros -
   compare preço por 1.000 resultados e teste o output antes de decidir).
3. Rode manualmente pelo Console do Apify uma busca de teste (ex.: 1 marca,
   1 modelo) e olhe o JSON de saída no dataset - copie os nomes exatos dos
   campos retornados.
4. Ajuste dois lugares no código com esses nomes reais:
   - `src/apify_client_wrapper.py` → dict `run_input` de `buscar_webmotors`
     e `buscar_icarros` (nomes dos parâmetros de busca do actor).
   - `src/normalize.py` → dicts `CAMPOS_WEBMOTORS` e `CAMPOS_ICARROS`
     (nomes dos campos de saída do actor).

### 3. Configurar variáveis de ambiente
```bash
export APIFY_TOKEN="seu_token_da_conta_apify"
export APIFY_ACTOR_WEBMOTORS="usuario/nome-do-actor-webmotors"
export APIFY_ACTOR_ICARROS="usuario/nome-do-actor-icarros"
```

### 4. Configurar os modelos a monitorar
Edite `MODELOS_MONITORADOS` em `src/main.py`. Para descobrir os códigos de
marca/modelo da FIPE, rode isoladamente:
```bash
python -c "from src.fipe_client import FipeClient; c = FipeClient(); print(c.listar_marcas())"
```

### 5. Rodar o pipeline
```bash
python src/main.py
```

Isso gera em `output/`:
- **posicionamento_preco.xlsx** — gap % médio da Benet vs. gap % médio do
  mercado, por marca/modelo (quanto acima/abaixo da FIPE cada um está
  praticando).
- **mapa_concorrencia.xlsx** — todos os anúncios de concorrentes coletados,
  com preço, km, cidade e gap vs. FIPE, ordenados por modelo.

## Por que Apify em vez de scraping próprio

Webmotors e iCarros têm proteção ativa anti-bot e Termos de Uso que
restringem raspagem automatizada. Em vez de construir e manter um scraper
próprio (que vira uma queda de braço técnica constante e um risco direto pra
Benet), o pipeline usa actors de terceiros já especializados nesses dois
sites - eles absorvem a manutenção técnica e você paga por volume de dados.

## Próximos passos sugeridos
- Agendar a execução (cron local, GitHub Actions, ou Apify Scheduler) para
  rodar diária ou semanalmente.
- Adicionar um histórico (ao invés de sobrescrever o Excel, acumular em uma
  tabela com data da coleta) para acompanhar tendência de preço ao longo do
  tempo, não só a foto do dia.
- Ajustar o limiar de similaridade em `normalize.cruzar_com_fipe` (hoje em
  0.55) conforme a qualidade dos nomes de modelo que os actors escolhidos
  retornam.
