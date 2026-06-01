#!/usr/bin/env bash
set -euo pipefail

PAGE_ID="964609183398328"          # Robotzap
IG_ID="17841445066879813"         # homeunity.oficial
LOCAL_IMAGE_URL="https://marketing.incorporacao.digital/media/generated/homeunity_future_automation_post_v2.jpg"
EXTERNAL_IMAGE_URL="https://www.gstatic.com/webp/gallery/1.jpg"
CAPTION="Teste de publicação Instagram via JSON + Bearer"
SESSION_JSON="/root/.openclaw/workspace/projects/meta-connection-panel/data/meta_session.json"
API="https://graph.facebook.com/v21.0"

TOKEN="$(python3 - <<'PY'
import json
p='/root/.openclaw/workspace/projects/meta-connection-panel/data/meta_session.json'
data=json.load(open(p))
for page in data.get('pages', []):
    if str(page.get('id')) == '964609183398328':
        print(page.get('access_token',''))
        break
PY
)"

if [[ -z "$TOKEN" ]]; then
  echo "ERRO: token da página Robotzap não encontrado em $SESSION_JSON"
  exit 1
fi

echo "===== PAGE / IG CONTEXT ====="
echo "PAGE_ID: $PAGE_ID"
echo "IG_ID:   $IG_ID"
echo "TOKEN (masked): ${TOKEN:0:8}...${TOKEN: -6}"

echo ""
echo "===== PAGE -> INSTAGRAM ACCOUNT CHECK ====="
curl -sS "$API/$PAGE_ID?fields=instagram_business_account&access_token=$TOKEN"
echo ""

run_test() {
  local label="$1"
  local image_url="$2"

  echo ""
  echo "===== $label ====="
  echo "IMAGE: $image_url"

  local payload
  payload=$(python3 - <<'PY' "$image_url" "$CAPTION"
import json,sys
print(json.dumps({
    'image_url': sys.argv[1],
    'caption': sys.argv[2]
}))
PY
)

  local create_resp
  create_resp=$(curl -sS -X POST "$API/$IG_ID/media" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$payload")

  echo "CREATE RESPONSE:"
  echo "$create_resp"

  local creation_id
  creation_id=$(python3 - <<'PY' "$create_resp"
import json,sys
try:
    data=json.loads(sys.argv[1])
    print(data.get('id',''))
except Exception:
    print('')
PY
)

  if [[ -z "$creation_id" ]]; then
    echo "SEM creation_id; pulando status/publish."
    return 0
  fi

  echo "CREATION_ID: $creation_id"

  echo "STATUS RESPONSE:"
  curl -sS -X GET "$API/$creation_id?fields=status_code" \
    -H "Authorization: Bearer $TOKEN"
  echo ""

  local publish_payload
  publish_payload=$(python3 - <<'PY' "$creation_id"
import json,sys
print(json.dumps({'creation_id': sys.argv[1]}))
PY
)

  echo "PUBLISH RESPONSE:"
  curl -sS -X POST "$API/$IG_ID/media_publish" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$publish_payload"
  echo ""
}

run_test "JSON+Bearer with LOCAL image" "$LOCAL_IMAGE_URL"
run_test "JSON+Bearer with EXTERNAL image" "$EXTERNAL_IMAGE_URL"
