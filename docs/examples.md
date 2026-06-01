# Meta Connection Panel — JSON examples

Base: `https://marketing.incorporacao.digital`

Esta página concentra exemplos prontos de **input** e **output** para as rotas principais do painel.

> Observação: os exemplos abaixo representam contratos práticos da API atual. Como várias rotas ainda usam parsing manual de JSON, o OpenAPI automático não descreve tudo com precisão.

## Regras práticas importantes para Instagram

- O fluxo mais robusto é: **create media -> publish**.
- Caption longo funciona melhor com `form-urlencoded` / `--data-urlencode`.
- URL da imagem precisa ser simples e estável.
- Evite nomes com timestamps, caracteres estranhos ou padrões muito caóticos.
- Melhor prática: gerar a imagem com um **post_id simples** e publicar com nome tipo `igpost_<postid>.jpg`.

## Padrão curl recomendado (seguindo o que funcionou na prática)

### Create media
```bash
curl -X POST 'https://graph.facebook.com/v23.0/{ig-user-id}/media' \
  -d 'image_url=https://marketing.incorporacao.digital/media/generated/igpost_postabc123.jpg' \
  --data-urlencode 'caption=Legenda com emojis e quebras de linha' \
  -d 'access_token=ACCESS_TOKEN'
```

### Publish media
```bash
curl -X POST 'https://graph.facebook.com/v23.0/{ig-user-id}/media_publish' \
  -d 'creation_id=17900000000000000' \
  -d 'access_token=ACCESS_TOKEN'
```

---

## 1) Gerar imagem com Nano Banana

### Endpoint
`POST /meta/image/generate`

### Input
```json
{
  "prompt": "Luxury residential social media image, premium architecture, clean composition, square format, no text",
  "post_id": "postabc123",
  "prefix": "igpost"
}
```

### Output de sucesso
```json
{
  "ok": true,
  "prompt": "Luxury residential social media image, premium architecture, clean composition, square format, no text",
  "post_id": "postabc123",
  "image": {
    "slide_number": 1,
    "path": "/root/.openclaw/workspace/outputs/nano-banana/igpost_postabc123.png",
    "status": "ok",
    "model": "nano-banana-pro-preview"
  },
  "local_path": "/root/.openclaw/workspace/outputs/nano-banana/igpost_postabc123.png",
  "public_url": "https://marketing.incorporacao.digital/media/generated/igpost_postabc123.jpg",
  "recommended_media_payload": {
    "image_url": "https://marketing.incorporacao.digital/media/generated/igpost_postabc123.jpg",
    "caption": "Legenda aqui",
    "post_type": "image"
  }
}
```

---

## 2) Instagram post — create + publish automático

### Endpoint
`POST /meta/instagram/post`

### Input
```json
{
  "page_id": "642584102277878",
  "image_url": "https://marketing.incorporacao.digital/media/generated/igpost_postabc123.jpg",
  "caption": "Legenda com emojis e quebras de linha\n\nAgora usando create media e publish.",
  "post_type": "image",
  "publish_now": true
}
```

### Output de sucesso
```json
{
  "ok": true,
  "post_type": "image",
  "media": {
    "image_url": "https://marketing.incorporacao.digital/media/generated/igpost_postabc123.jpg",
    "caption": "Legenda com emojis e quebras de linha\n\nAgora usando create media e publish.",
    "create_endpoint": "https://graph.facebook.com/v23.0/17841400000000000/media",
    "publish_endpoint": "https://graph.facebook.com/v23.0/17841400000000000/media_publish"
  },
  "creation": {
    "id": "17900000000000000"
  },
  "publish_result": {
    "id": "17910000000000000"
  }
}
```

---

## 3) Instagram post — create only

### Endpoint
`POST /meta/instagram/post`

### Input
```json
{
  "page_id": "642584102277878",
  "image_url": "https://marketing.incorporacao.digital/media/generated/igpost_postxyz999.jpg",
  "caption": "Criar container primeiro",
  "post_type": "image",
  "publish_now": false
}
```

### Output de sucesso
```json
{
  "ok": true,
  "post_type": "image",
  "media": {
    "image_url": "https://marketing.incorporacao.digital/media/generated/igpost_postxyz999.jpg",
    "caption": "Criar container primeiro",
    "create_endpoint": "https://graph.facebook.com/v23.0/17841400000000000/media",
    "publish_endpoint": "https://graph.facebook.com/v23.0/17841400000000000/media_publish"
  },
  "creation": {
    "id": "17900000000000001"
  },
  "publish_result": null,
  "next_step": {
    "action": "publish_container",
    "creation_id": "17900000000000001",
    "endpoint": "/meta/instagram/publish-container"
  }
}
```

---

## 4) Publicar container já criado

### Endpoint
`POST /meta/instagram/publish-container`

### Input
```json
{
  "page_id": "642584102277878",
  "container_id": "17900000000000001"
}
```

### Output de sucesso
```json
{
  "ok": true,
  "publish_result": {
    "id": "17910000000000001"
  }
}
```

---

## 5) Facebook post — texto/link

### Endpoint
`POST /meta/facebook/post`

### Input
```json
{
  "page_id": "642584102277878",
  "message": "Conheça nosso novo material sobre incorporação digital.",
  "link": "https://incorporacao.digital",
  "published": true,
  "scheduled_publish_time": ""
}
```

### Output de sucesso
```json
{
  "ok": true,
  "result": {
    "id": "122161771856901904"
  }
}
```

### Output de erro
```json
{
  "ok": false,
  "error": "missing_page_id_or_message"
}
```

---

## 6) Facebook photo post

### Endpoint
`POST /meta/facebook/photo`

### Input
```json
{
  "page_id": "964609183398328",
  "image_url": "https://marketing.incorporacao.digital/media/generated/homeunity_future_automation_post_v2.jpg",
  "caption": "O futuro da automação residencial começa agora.",
  "published": true,
  "scheduled_publish_time": ""
}
```

### Output de sucesso
```json
{
  "ok": true,
  "result": {
    "id": "122120964159199298",
    "post_id": "964609183398328_122120964195199298"
  }
}
```

### Output de erro
```json
{
  "ok": false,
  "error": "missing_page_id_or_image_url"
}
```

---

## 7) Facebook album

### Endpoint
`POST /meta/facebook/album`

### Input
```json
{
  "page_id": "642584102277878",
  "image_urls": [
    "https://example.com/album-1.jpg",
    "https://example.com/album-2.jpg",
    "https://example.com/album-3.jpg"
  ],
  "caption": "Veja os bastidores do projeto.",
  "published": true
}
```

### Output de sucesso
```json
{
  "ok": true,
  "photo_ids": [
    { "media_fbid": "111" },
    { "media_fbid": "222" },
    { "media_fbid": "333" }
  ],
  "result": {
    "id": "444"
  }
}
```

### Output de erro
```json
{
  "ok": false,
  "error": "missing_page_id_or_image_urls"
}
```

---

## 8) Page insights

### Endpoint
`GET /meta/page-insights?page_id=642584102277878&metrics=page_impressions,page_engagement&period=day`

### Output de sucesso
```json
{
  "ok": true,
  "page_id": "642584102277878",
  "metrics": "page_impressions,page_engagement",
  "result": {
    "data": [
      {
        "name": "page_impressions",
        "period": "day",
        "values": [
          {
            "value": 1240,
            "end_time": "2026-04-06T07:00:00+0000"
          }
        ],
        "title": "Daily Total Impressions",
        "description": "Total number of impressions"
      }
    ]
  }
}
```

---

## 9) Post insights

### Endpoint
`GET /meta/post-insights?post_id=964609183398328_122120964195199298&metrics=post_impressions,post_clicks`

### Output de sucesso
```json
{
  "ok": true,
  "post_id": "964609183398328_122120964195199298",
  "metrics": "post_impressions,post_clicks",
  "result": {
    "data": []
  }
}
```

---

## 10) Métricas disponíveis — page insights

### Endpoint
`GET /meta/metrics/page-insights`

### Output
```json
{
  "ok": true,
  "description": "Supported metric names for the page insights endpoints. Combine the \"name\" values with commas when calling /meta/page-insights or /meta/post-insights.",
  "metrics": [
    {
      "name": "page_impressions",
      "description": "Total number of times any content from the Page was shown.",
      "periods": ["day", "week", "days_28", "lifetime"],
      "unit": "count",
      "object": "page"
    }
  ],
  "hint": "Example: /meta/page-insights?page_id=123&metrics=page_engagement,page_impressions"
}
```

---

## 11) Métricas disponíveis — ads

### Endpoint
`GET /meta/metrics/ads`

### Output
```json
{
  "ok": true,
  "description": "Advertising metrics that the Graph API accepts when requesting /<ad>/insights, /<adset>/insights, or /<campaign>/insights.",
  "metrics": [
    {
      "name": "impressions",
      "description": "Number of times the ad, ad set or campaign was shown.",
      "supported_objects": ["ad", "adset", "campaign", "account"],
      "unit": "count"
    },
    {
      "name": "spend",
      "description": "Amount spent on the ads during the period (in account currency).",
      "supported_objects": ["ad", "adset", "campaign"],
      "unit": "currency"
    }
  ],
  "hint": "Use these names as the metric parameter on Facebook Graph insights requests (e.g. metric=impressions,clicks)."
}
```
