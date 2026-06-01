# Meta Connection Panel API

Base: `https://marketing.incorporacao.digital`

O painel expõe rotas REST para conexão com Meta/Facebook, publicação em páginas/Instagram, leitura de insights e geração local de imagens para publicação.

## Situação atual do contrato da API

Hoje várias rotas fazem parsing manual com `body = await request.json()` e depois usam `body.get(...)` dentro de `try/except`. Isso significa que:
- o FastAPI **não está validando automaticamente** o schema de entrada nessas rotas;
- a documentação automática do Swagger/OpenAPI tende a ficar pobre para esses endpoints;
- alguns campos obrigatórios só aparecem na implementação, não no contrato do endpoint.

Na prática, o consumidor precisa seguir esta documentação e a galeria de exemplos.

## Onde consultar exemplos prontos

- Referência em markdown: `docs/examples.md`
- Referência estruturada em JSON: `docs/examples.json`
- Catálogo de métricas de página: `GET /meta/metrics/page-insights`
- Catálogo de métricas de anúncios: `GET /meta/metrics/ads`

---

## Regras operacionais importantes para Instagram

Com base no que já funcionou em uso real e no fluxo documentado nas skills locais:

1. O caminho mais robusto é **create media -> publish**.
2. A `caption` deve ser enviada em `form-urlencoded`, preferencialmente com `--data-urlencode`.
3. O `image_url` deve apontar para um nome de arquivo simples e estável.
4. Evite timestamps, caracteres especiais e nomes muito caóticos na URL da mídia.
5. Melhor prática: gerar a arte com um `post_id` simples e publicar com um nome como `igpost_<postid>.jpg`.

---

## 1. Autenticação e estado

### `GET /health`
Retorna status básico da aplicação e disponibilidade do painel.

### `GET /meta/connect/start`
Inicia o OAuth da Meta para obtenção de access token.

### `GET /meta/connect/callback`
Recebe o callback do OAuth e persiste o token na sessão local do painel.

### `GET /meta/accounts`
Lista páginas conectadas e metadados da conta autenticada.

### `GET /meta/ad-accounts`
Lista contas de anúncio disponíveis para o usuário autenticado.

---

## 2. Resolver token/contexto do Instagram

### `GET /meta/instagram-access-token`
Resolve o token individual da página associada a uma conta Instagram Business específica, a partir do token geral atual do painel.

### Como localizar a conta
Você pode informar um destes filtros:
- `page_id`
- `ig_user_id`
- `username`

### Query params
- `page_id` opcional
- `ig_user_id` opcional
- `username` opcional
- `refresh=true|false` opcional

Se `refresh=true`, a rota refaz `me/accounts` usando o token geral e atualiza a lista local de páginas antes de resolver o token.

### Output
```json
{
  "ok": true,
  "page_id": "964609183398328",
  "page_name": "Home Unity",
  "instagram_business_account": {
    "id": "17841400000000000",
    "username": "homeunity"
  },
  "access_token": "EAAG...",
  "source": "me/accounts",
  "hint": "This token is the page-level token associated with the selected Instagram business account and can be used for Graph Instagram publishing flows."
}
```

### Quando usar
Use essa rota quando sua integração quiser:
- selecionar uma conta Instagram específica
- obter o token individual correto da página vinculada
- depois chamar o fluxo de create media / publish com esse token

---

## 3. Geração local de imagem

### `POST /meta/image/generate`
Gera uma imagem local com Nano Banana, salva no workspace, publica uma cópia com nome simples em `/media/generated/...` e devolve um payload recomendado para uso no Instagram.

### Input esperado
```json
{
  "briefing": "Post sobre automação residencial com foco em iluminação inteligente",
  "post_id": "postabc123",
  "prefix": "igpost"
}
```

Ou, se quiser controlar o prompt diretamente:
```json
{
  "prompt": "Luxury residential social media image, premium architecture, clean composition, square format, no text",
  "post_id": "postabc123",
  "prefix": "igpost"
}
```

Se `briefing` for fornecido, a IA gera internamente o `copy` (legenda) e o `image_prompt`. O `prompt` explícito tem precedência sobre o `briefing`.

### Output
A resposta inclui:
- `local_path`
- `public_url`
- `copy` — legenda gerada por IA (presente quando `briefing` é fornecido)
- `generated` — `{copy, image_prompt, provider}` quando `briefing` é fornecido
- `recommended_media_payload` — payload pronto para usar em `/meta/instagram/post`

---

## 4. Publicação no Facebook

### `POST /meta/facebook/post`
Cria um post de texto ou texto+link em uma Facebook Page.

Campos principais:
- `page_id` **obrigatório**
- `message` **obrigatório**
- `link` opcional
- `published` opcional
- `scheduled_publish_time` opcional

### `POST /meta/facebook/photo`
Publica uma imagem em uma página do Facebook.

Campos principais:
- `page_id` **obrigatório**
- `image_url` **obrigatório**
- `caption` opcional
- `published` opcional
- `scheduled_publish_time` opcional

### `POST /meta/facebook/album`
Publica múltiplas imagens como álbum/post composto em uma página.

Campos principais:
- `page_id` **obrigatório**
- `image_urls` **obrigatório**
- `caption` opcional
- `published` opcional

---

## 5. Publicação no Instagram

### `POST /meta/instagram/post`
Cria um container de mídia e, opcionalmente, publica esse container no Instagram.

### Input esperado
```json
{
  "page_id": "642584102277878",
  "image_url": "https://marketing.incorporacao.digital/media/generated/igpost_postabc123.jpg",
  "caption": "Legenda com emojis e quebras de linha",
  "post_type": "image",
  "publish_now": true
}
```

### Campos
- `image_url` **obrigatório**
- `caption` opcional
- `post_type` opcional — hoje principalmente informativo
- `publish_now` opcional — se `false`, só cria o container
- contexto de autenticação pode vir por `page_id`, `username`, `ig_user_id`, `access_token`

### O que a resposta inclui
- `post_type`
- `media.image_url`
- `media.caption`
- `media.create_endpoint`
- `media.publish_endpoint`
- `creation`
- `publish_result`
- `next_step` quando `publish_now=false`

### `POST /meta/instagram/publish-container`
Publica um container já criado.

### Input esperado
```json
{
  "page_id": "642584102277878",
  "container_id": "17900000000000001"
}
```

### Outros endpoints Instagram
- `POST /meta/instagram/carousel`
- `POST /meta/instagram/story`
- `POST /meta/instagram/reel`
- `POST /meta/instagram-media/create`
- `POST /meta/instagram-media/publish`
- `GET /meta/instagram/container-status`
- `GET /meta/instagram-insights`
- `GET /meta/instagram-media-insights`

---

## 6. Insights orgânicos

### `GET /meta/page-insights`
Consulta métricas de página.

### `GET /meta/post-insights`
Consulta métricas de um post específico.

---

## 7. Catálogo de métricas

### `GET /meta/metrics/page-insights`
Retorna a lista de métricas suportadas para `/meta/page-insights`.

### `GET /meta/metrics/ads`
Retorna métricas úteis para insights de campanhas, conjuntos e anúncios.

---

## 8. Onde a API ainda pode melhorar

Hoje os principais problemas são:
1. **Inputs sem schema forte** em várias rotas `POST`.
2. **Swagger pobre** porque a maior parte das rotas usa `Request` cru em vez de `BaseModel`.
3. **Campos obrigatórios escondidos no código** e não no contrato.
4. **Outputs reais variam conforme a resposta do Graph**, então é melhor manter uma galeria de exemplos versionada.

---

## 9. Próximo passo recomendado

Para deixar o sistema realmente funcional sem depender de IA para interpretar contrato:
- criar models Pydantic para as rotas principais
- anotar `response_model`
- expor uma rota/página pública de exemplos JSON
- manter `docs/examples.md` e `docs/examples.json` como referências oficiais de integração
