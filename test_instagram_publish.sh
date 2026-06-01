#!/usr/bin/env bash
set -euo pipefail

PAGE_ID="964609183398328"          # Robotzap
IG_ID="17841445066879813"         # homeunity.oficial
LOCAL_IMAGE_URL="https://marketing.incorporacao.digital/media/generated/homeunity_future_automation_post_v2.jpg"
EXTERNAL_IMAGE_URL="https://www.gstatic.com/webp/gallery/1.jpg"
CAPTION="Teste de publicação Instagram via API"
SESSION_JSON="/root/.openclaw/workspace/projects/meta-connection-panel/data/meta_session.json"

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

run_test() {
  local label="$1"
  local host="$2"
  local image_url="$3"
  echo ""
  echo "===== $label ====="
  echo "HOST: $host"
  echo "IMAGE: $image_url"

  local create_resp
  create_resp=$(curl -sS -X POST "$host/v23.0/$IG_ID/media" \
    -H "Authorization: Bearer $TOKEN" \
    --data-urlencode "image_url=$image_url" \
    --data-urlencode "caption=$CAPTION")

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
    echo "SEM creation_id; pulando publish."
    return 0
  fi

  echo "CREATION_ID: $creation_id"

  echo "STATUS RESPONSE:"
  curl -sS -X GET "$host/v23.0/$creation_id?fields=status_code" \
    -H "Authorization: Bearer $TOKEN"
  echo ""

  echo "PUBLISH RESPONSE:"
  curl -sS -X POST "$host/v23.0/$IG_ID/media_publish" \
    -H "Authorization: Bearer $TOKEN" \
    --data-urlencode "creation_id=$creation_id"
  echo ""
}

run_test "FB host + local image" "https://graph.facebook.com" "$LOCAL_IMAGE_URL"
run_test "FB host + external image" "https://graph.facebook.com" "$EXTERNAL_IMAGE_URL"
run_test "IG host + local image" "https://graph.instagram.com" "$LOCAL_IMAGE_URL"
run_test "IG host + external image" "https://graph.instagram.com" "$EXTERNAL_IMAGE_URL"
