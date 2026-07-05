#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8069}"
CODI_CLASSE="${CODI_CLASSE:-JL-2A4BEA}"
APP_UID="${APP_UID:-flutter-smoke-v2-$(date +%s)}"
NOM_VISIBLE="${NOM_VISIBLE:-Smoke V2}"
CLIENT_UID="${CLIENT_UID:-smoke-v2-read-$APP_UID}"
CLIENT_UID_SNAKE="${CLIENT_UID_SNAKE:-smoke-v2-read-snake-$APP_UID}"

ODOO_DB="${ODOO_DB:-falla}"
ODOO_LOGIN="${ODOO_LOGIN:-admin}"
ODOO_PASSWORD="${ODOO_PASSWORD:-admin}"
COOKIE_JAR="${COOKIE_JAR:-/tmp/joc_lector_docent.cookies}"
SETUP_DOCENT_FIXTURE="${SETUP_DOCENT_FIXTURE:-0}"
RUN_DOCENT_TESTS="${RUN_DOCENT_TESTS:-0}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: falta comandament $1"
    exit 1
  }
}

need_cmd curl
need_cmd python3

json_post() {
  local url="$1"
  local body="$2"
  curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 -X POST "$url" -H "Content-Type: application/json" -d "$body"
}

json_get() {
  local url="$1"
  curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 -X GET "$url"
}

json_post_auth_bearer() {
  local url="$1"
  local token="$2"
  local body="$3"
  curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 -X POST "$url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d "$body"
}

extract_json_path() {
  local raw="$1"
  local path="$2"
  python3 - "$raw" "$path" <<'PY'
import json
import sys

raw = sys.argv[1]
path = sys.argv[2].split('.')
obj = json.loads(raw)
for p in path:
    if isinstance(obj, list):
        obj = obj[int(p)]
    else:
        obj = obj[p]
print(obj)
PY
}

assert_ok_true() {
  local raw="$1"
  python3 - "$raw" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
if obj.get('ok') is not True:
    print('ERROR resposta:', json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(1)
PY
}

assert_sync_keys() {
  local raw="$1"
  local expected_client_uid="${2:-}"
  python3 - "$raw" <<'PY'
import json
import sys

obj = json.loads(sys.argv[1])
if obj.get("ok") is not True:
  print("ERROR sync no ok")
  sys.exit(1)

lectures = obj.get("lectures") or []
if not lectures:
  print("ERROR sync sense lectures en resposta")
  sys.exit(1)

item = lectures[0]
required = ["server_id", "serverId", "client_uid", "clientUid", "estat", "estat_validacio", "estatValidacio"]
missing = [k for k in required if k not in item]
if missing:
  print("ERROR claus faltants en sync:", missing)
  print(json.dumps(item, ensure_ascii=False, indent=2))
  sys.exit(1)

if item.get("server_id") != item.get("serverId"):
  print("ERROR server_id i serverId no coincideixen")
  sys.exit(1)

if item.get("client_uid") != item.get("clientUid"):
  print("ERROR client_uid i clientUid no coincideixen")
  sys.exit(1)

print("OK claus de sync validades")
PY

  if [[ -n "$expected_client_uid" ]]; then
    python3 - "$raw" "$expected_client_uid" <<'PY'
import json
import sys

obj = json.loads(sys.argv[1])
expected = sys.argv[2]
item = obj["lectures"][0]

if item.get("client_uid") != expected or item.get("clientUid") != expected:
  print("ERROR clientUid no torna correctament")
  print("expected:", expected)
  print(json.dumps(item, ensure_ascii=False, indent=2))
  sys.exit(1)

print("OK clientUid conservat", expected)
PY
  fi
}

assert_same_server_id() {
  local first_raw="$1"
  local second_raw="$2"
  python3 - "$first_raw" "$second_raw" <<'PY'
import json
import sys

first = json.loads(sys.argv[1])
second = json.loads(sys.argv[2])

a = first["lectures"][0]["server_id"]
b = second["lectures"][0]["server_id"]

if a != b:
  print("ERROR deduplicacio: server_id diferent", a, b)
  sys.exit(1)

print("OK deduplicacio idempotent server_id", a)
PY
}

assert_professor_class_keys() {
  local raw="$1"
  python3 - "$raw" <<'PY'
import json
import sys

obj = json.loads(sys.argv[1])
if obj.get("ok") is not True:
  print("ERROR classes docent no ok")
  sys.exit(1)

classes = obj.get("classes") or []
if not classes:
  print("ERROR resposta docent sense classes")
  sys.exit(1)

item = classes[0]
required = ["id", "server_id", "serverId", "access_code", "codi_acces"]
missing = [k for k in required if k not in item]
if missing:
  print("ERROR claus faltants en classe docent:", missing)
  print(json.dumps(item, ensure_ascii=False, indent=2))
  sys.exit(1)

if item.get("id") != item.get("server_id") or item.get("id") != item.get("serverId"):
  print("ERROR id, server_id i serverId no coincideixen en classe docent")
  print(json.dumps(item, ensure_ascii=False, indent=2))
  sys.exit(1)

print("OK claus de classe docent validades")
PY
}

assert_single_client_uid_in_db() {
  local client_uid="$1"
  local expected_server_id="$2"
  local count
  local db_server_id

  count=$(cd /home/talens/odoo_server && docker compose exec -T db psql -U odoo -d "$ODOO_DB" -Atc \
    "SELECT COUNT(*) FROM joc_lector_lectura WHERE client_uid = '$client_uid';")
  if [[ "$count" != "1" ]]; then
    echo "ERROR deduplicacio DB: client_uid=$client_uid count=$count"
    exit 1
  fi

  db_server_id=$(cd /home/talens/odoo_server && docker compose exec -T db psql -U odoo -d "$ODOO_DB" -Atc \
    "SELECT id FROM joc_lector_lectura WHERE client_uid = '$client_uid' LIMIT 1;")
  if [[ "$db_server_id" != "$expected_server_id" ]]; then
    echo "ERROR deduplicacio DB: server_id resposta=$expected_server_id db=$db_server_id"
    exit 1
  fi

  echo "OK DB sense duplicats per client_uid $client_uid"
}

echo "== 1) health =="
HEALTH=$(json_post "$BASE_URL/joc_lector/api/health" '{}')
assert_ok_true "$HEALTH"
echo "$HEALTH"

echo "== 2) entrar_classe =="
ENTRAR=$(json_post "$BASE_URL/joc_lector/api/alumne/entrar_classe" "{\"codi_classe\":\"$CODI_CLASSE\",\"app_uid\":\"$APP_UID\",\"nom_visible\":\"$NOM_VISIBLE\"}")
assert_ok_true "$ENTRAR"
TOKEN=$(extract_json_path "$ENTRAR" "token.access_token")
echo "TOKEN obtingut"

echo "== 3) sync lectures camelCase clientUid =="
SYNC=$(json_post_auth_bearer "$BASE_URL/joc_lector/api/sync/lectures" "$TOKEN" "{\"lectures\":[{\"clientUid\":\"$CLIENT_UID\",\"titol\":\"El petit princep\",\"autor\":\"A. de Saint-Exupery\",\"isbn\":\"9780156012195\",\"estat\":\"acabat\",\"dataInici\":\"2026-06-01\",\"dataFi\":\"2026-06-10\",\"valoracio\":5,\"ressenya\":\"Ressenya smoke v2\",\"evidenciaText\":\"prova manual\",\"visiblePublicament\":true}]}")
assert_ok_true "$SYNC"
assert_sync_keys "$SYNC" "$CLIENT_UID"
LECTURA_ID=$(extract_json_path "$SYNC" "lectures.0.server_id")
echo "LECTURA_ID=$LECTURA_ID"

echo "== 4) sync idempotent repetit (mateix clientUid) =="
SYNC_REPEAT=$(json_post_auth_bearer "$BASE_URL/joc_lector/api/sync/lectures" "$TOKEN" "{\"lectures\":[{\"clientUid\":\"$CLIENT_UID\",\"titol\":\"El petit princep\",\"isbn\":\"9780156012195\",\"estat\":\"acabat\",\"dataInici\":\"2026-06-01\",\"dataFi\":\"2026-06-10\",\"valoracio\":5,\"ressenya\":\"Ressenya smoke v2 repetida\",\"visiblePublicament\":true}]}")
assert_ok_true "$SYNC_REPEAT"
assert_sync_keys "$SYNC_REPEAT" "$CLIENT_UID"
assert_same_server_id "$SYNC" "$SYNC_REPEAT"
assert_single_client_uid_in_db "$CLIENT_UID" "$LECTURA_ID"

echo "== 5) sync snake_case client_uid =="
SYNC_SNAKE=$(json_post_auth_bearer "$BASE_URL/joc_lector/api/sync/lectures" "$TOKEN" "{\"lectures\":[{\"client_uid\":\"$CLIENT_UID_SNAKE\",\"titol\":\"Matilda\",\"isbn\":\"9780142410370\",\"estat\":\"finished\",\"data_inici\":\"2026-05-01\",\"data_fi\":\"2026-05-12\",\"valoracio\":4,\"ressenya\":\"Sync snake case\",\"evidencia_text\":\"nota\",\"visible_publicament\":false}]}")
assert_ok_true "$SYNC_SNAKE"
assert_sync_keys "$SYNC_SNAKE" "$CLIENT_UID_SNAKE"
LECTURA_ID_SNAKE=$(extract_json_path "$SYNC_SNAKE" "lectures.0.server_id")
assert_single_client_uid_in_db "$CLIENT_UID_SNAKE" "$LECTURA_ID_SNAKE"

echo "== 6) passaport =="
PASSAPORT=$(json_post_auth_bearer "$BASE_URL/joc_lector/api/alumne/passaport" "$TOKEN" '{}')
assert_ok_true "$PASSAPORT"
echo "$PASSAPORT"

if [[ "$RUN_DOCENT_TESTS" == "1" ]]; then
  if [[ "$SETUP_DOCENT_FIXTURE" == "1" ]]; then
    echo "== 7) setup docent fixture =="
    /home/talens/odoo_server/dev_addons/joc_lector/scripts/setup_teacher_fixture.sh
    ODOO_LOGIN="${TEACHER_LOGIN:-docent_smoke}"
    ODOO_PASSWORD="${TEACHER_PASSWORD:-docent_smoke_123}"
  fi

  echo "== 8) login sessio docent web =="
  AUTH_DOCENT=$(curl -sS -c "$COOKIE_JAR" -X POST "$BASE_URL/web/session/authenticate" \
    --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"params\":{\"db\":\"$ODOO_DB\",\"login\":\"$ODOO_LOGIN\",\"password\":\"$ODOO_PASSWORD\"},\"id\":1}")

  python3 - "$AUTH_DOCENT" <<'PY'
import json
import sys

raw = sys.argv[1]
if not raw.strip():
  print("ERROR login docent: resposta buida de /web/session/authenticate")
  sys.exit(1)

try:
  obj = json.loads(raw)
except Exception:
  print("ERROR login docent: resposta no JSON")
  print(raw)
  sys.exit(1)

if obj.get('error'):
  print('ERROR login docent (credencials o permisos):')
  print(json.dumps(obj, ensure_ascii=False, indent=2))
  sys.exit(1)

print('Sessio docent oberta')
PY

  echo "== 9) classes docent =="
  CLASSES=$(curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 -b "$COOKIE_JAR" -X GET "$BASE_URL/joc_lector/api/professor/classes")
  assert_ok_true "$CLASSES"
  assert_professor_class_keys "$CLASSES"
  echo "$CLASSES"

  echo "== 10) validar lectura acceptada =="
  VALIDAR=$(curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 -b "$COOKIE_JAR" -X POST "$BASE_URL/joc_lector/api/professor/validar_lectura" \
    -H "Content-Type: application/json" \
    -d "{\"lectura_id\":$LECTURA_ID,\"decisio\":\"acceptada\",\"visible_publicament\":true,\"comentari\":\"Validada per smoke test\"}")
  assert_ok_true "$VALIDAR"
  echo "$VALIDAR"
fi

echo "== 11) ranking meu =="
RANKING=$(curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 -X POST "$BASE_URL/joc_lector/api/alumne/ranking/meu" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}')
assert_ok_true "$RANKING"
echo "$RANKING"

echo "== 12) comprovacio SQL moviments punts =="
cd /home/talens/odoo_server
docker compose exec -T db psql -U odoo -d "$ODOO_DB" -c "SELECT id, alumne_id, origen, lectura_id, punts, motiu, data FROM joc_lector_punts_moviment ORDER BY id DESC LIMIT 10;"

echo "OK smoke_api_v2 finalitzat"
