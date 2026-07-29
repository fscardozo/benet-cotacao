# Como colocar o site no ar (sem programar)

Este guia assume que você nunca usou GitHub nem hospedagem de site. Segue o
passo a passo do zero.

## O que você vai ter no final
Um endereço tipo `https://benet-cotacao.streamlit.app` que você acessa de
qualquer navegador (computador ou celular), com um formulário: marca,
modelo, ano, estado → botão "Consultar" → mostra FIPE + preços de mercado.

## Passo 1 — Criar conta no GitHub (onde o código vai morar)
1. Acesse https://github.com/signup e crie uma conta gratuita.
2. Depois de logado, clique no botão verde **"New"** (ou o "+" no canto
   superior direito → "New repository").
3. Dê um nome, por exemplo `benet-cotacao`. Deixe como **Public**. Clique
   em **"Create repository"**.
4. Na página do repositório vazio, clique em **"uploading an existing
   file"** e arraste TODOS os arquivos da pasta `benet-market-research`
   que eu te entreguei (mantendo a pasta `src/` como está). Clique em
   **"Commit changes"**.

## Passo 2 — Criar conta no Streamlit Community Cloud (a hospedagem, grátis)
1. Acesse https://share.streamlit.io e clique em **"Sign up"**.
2. Escolha **"Continue with GitHub"** e autorize (é a mesma conta do Passo 1).
3. Clique em **"New app"**.
4. Selecione o repositório `benet-cotacao` que você criou.
5. Em **"Main file path"**, digite: `src/app.py`
6. Clique em **"Advanced settings"** e cole suas chaves secretas (veja o
   Passo 3 antes de continuar) — NUNCA cole essas chaves direto no código
   do GitHub, é por isso que existe esse campo separado.
7. Clique em **"Deploy"**. Em 1-2 minutos o site fica no ar com uma URL que
   você pode compartilhar.

## Passo 3 — Configurar as chaves do Apify (sem expor no código)
No campo **"Secrets"** das Advanced Settings do Streamlit (Passo 2.6), cole
exatamente isso, substituindo pelos seus valores reais:

```
APIFY_TOKEN = "seu_token_aqui"
APIFY_ACTOR_WEBMOTORS = "usuario/nome-do-actor-webmotors"
APIFY_ACTOR_ICARROS = "usuario/nome-do-actor-icarros"
```

Onde conseguir cada valor:
- **APIFY_TOKEN**: crie uma conta em https://apify.com (tem plano
  gratuito), depois vá em **Settings → Integrations → API tokens**.
- **APIFY_ACTOR_WEBMOTORS / APIFY_ACTOR_ICARROS**: na Apify Store
  (https://apify.com/store), busque "webmotors" e "icarros", escolha um
  actor de cada, e copie o identificador que aparece na URL da página do
  actor (formato `usuario/nome-do-actor`).

## Passo 4 — Ajustar os nomes de campo (só uma vez)
Cada actor da Apify Store devolve os dados com nomes de campo ligeiramente
diferentes (ex.: um chama de `price`, outro de `preco`). Depois de rodar uma
consulta de teste no site e ver que o resultado não bate, é só:
1. No Apify Console, abrir o último "run" do actor e ver o JSON de saída.
2. No GitHub, editar dois arquivos (botão de lápis na página do arquivo):
   - `src/apify_client_wrapper.py`
   - `src/normalize.py`
3. Ajustar os nomes conforme o comentário que já está em cada arquivo.
4. O Streamlit atualiza o site sozinho assim que você salvar a mudança no
   GitHub (não precisa reimplantar manualmente).

## Se travar em algum passo
Qualquer erro que aparecer na tela do site ou do Streamlit Cloud, é só me
colar o texto do erro aqui na conversa que eu te ajudo a resolver.
