#!/usr/bin/env bash
set -euo pipefail

USER_TOKEN_INPUT="${1:-}"
PAGE_ID="964609183398328"          # Robotzap
IG_ID="17841445066879813"         # homeunity.oficial
LOCAL_IMAGE_URL="https://marketing.incorporacao.digital/media/generated/homeunity_future_automation_post_v2.jpg"
EXTERNAL_IMAGE_URL="https://www.gstatic.com/webp/gallery/1.jpg"
CAPTION="Teste de publicação Instagram via body access_token"
SESSION_JSON="/root/.openclaw/workspace/projects/meta-connection-panel/data/meta_session.json"
API="https://graph.facebook.com/v21.0"

PAGE_TOKEN="$(python3 - <<'PY'
import json
p='/root/.openclaw/workspace/projects/meta-connection-panel/data/meta_session.json'
data=json.load(open(p))
for page in data.get('pages', []):
    if str(page.get('id')) == '964609183398328':
        print(page.get('access_token',''))
        break
PY
)"

if [[ -z "$PAGE_TOKEN" ]]; then
  echo "ERRO: token da página Robotzap não encontrado em $SESSION_JSON"
  exit 1
fi

echo "===== STEP 1: PAGE TOKEN LOCAL ====="
echo "PAGE_ID: $PAGE_ID"
echo "PAGE_TOKEN (masked): ${PAGE_TOKEN:0:8}...${PAGE_TOKEN: -6}"

echo ""
echo "===== STEP 2: GET IG ACCOUNT FROM PAGE ====="
curl -sS "$API/$PAGE_ID?fields=instagram_business_account&access_token=$PAGE_TOKEN"
echo ""

run_test() {
  local label="$1"
  local image_url="$2"

  echo ""
  echo "===== $label ====="
  echo "IMAGE: $image_url"

  local create_resp
  create_resp=$(curl -sS -X POST "$API/$IG_ID/media" \
    -d "image_url=$image_url" \
    --data-urlencode "caption=$CAPTION" \
    -d "access_token=$PAGE_TOKEN")

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
  curl -sS "$API/$creation_id?fields=status_code&access_token=$PAGE_TOKEN"
  echo ""

  echo "PUBLISH RESPONSE:"
  curl -sS -X POST "$API/$IG_ID/media_publish" \
    -d "creation_id=$creation_id" \
    -d "access_token=$PAGE_TOKEN"
  echo ""
}

run_test "LOCAL IMAGE with body access_token" "$LOCAL_IMAGE_URL"
run_test "EXTERNAL IMAGE with body access_token" "$EXTERNAL_IMAGE_URL"

if [[ -n "$USER_TOKEN_INPUT" ]]; then
  echo ""
  echo "===== OPTIONAL STEP: me/accounts with USER TOKEN ====="
  curl -sS "$API/me/accounts?access_token=$USER_TOKEN_INPUT"
  echo ""
fi
