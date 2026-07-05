#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8069}"
ODOO_ROOT="${ODOO_ROOT:-/home/talens/odoo_server}"
ODOO_DB="${ODOO_DB:-falla}"
CENTRE_CODE="${CENTRE_CODE:-SMOKEADMIN42}"
TS="$(date +%s)"
EMAIL_OK="${EMAIL_OK:-${TS}@edu.gva.es}"
EMAIL_BAD="${EMAIL_BAD:-centre_${TS}@edu.gva.es}"
CENTRE_NAME="${CENTRE_NAME:-Centre Smoke ${TS}}"
MUNICIPI="${MUNICIPI:-Valencia}"
TIC_EMAIL="${TIC_EMAIL:-tic_${TS}@example.org}"
PROF_EMAIL="${PROF_EMAIL:-prof_${TS}@example.org}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: falta comandament $1"
    exit 1
  }
}

need_cmd curl
need_cmd python3
need_cmd docker

json_post() {
  local url="$1"
  local body="$2"
  curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 \
    -X POST "$url" -H "Content-Type: application/json" -d "$body"
}

json_get() {
  local url="$1"
  curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 \
    -X GET "$url"
}

json_post_auth() {
  local url="$1"
  local token="$2"
  local body="$3"
  curl -sS --retry 3 --retry-all-errors --retry-connrefused --connect-timeout 5 --max-time 30 \
    -X POST "$url" -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "$body"
}

assert_ok_true() {
  local raw="$1"
  python3 - "$raw" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
if obj.get("ok") is not True:
    print("ERROR resposta:", json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(1)
PY
}

assert_error_code() {
  local raw="$1"
  local expected="$2"
  python3 - "$raw" "$expected" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
expected = sys.argv[2]
code = ((obj.get("error") or {}).get("code"))
if code != expected:
    print("ERROR codi inesperat", code, "esperat", expected)
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(1)
PY
}

extract_path() {
  local raw="$1"
  local path="$2"
  python3 - "$raw" "$path" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
parts = sys.argv[2].split('.')
for p in parts:
    obj = obj[int(p)] if isinstance(obj, list) else obj[p]
print(obj)
PY
}

set_known_admin_code() {
  local email="$1"
  local raw_code="$2"
  local hash
  hash="$(python3 - "$raw_code" <<'PY'
import hashlib
import sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
PY
)"

  (
    cd "$ODOO_ROOT"
    docker compose exec -T db psql -U odoo -d "$ODOO_DB" \
      -v ON_ERROR_STOP=1 \
      -c "UPDATE joc_lector_centre SET admin_code_hash='${hash}', admin_code_expires_at=NOW() + INTERVAL '7 days', admin_code_last_sent=NOW(), admin_verified=false, estat='actiu' WHERE email_oficial='${email}';"
  ) >/dev/null
}

echo "== 1) registrar centre valid =="
R1="$(json_post "$BASE_URL/joc_lector/api/centre/registrar" "{\"name\":\"$CENTRE_NAME\",\"email_oficial\":\"$EMAIL_OK\",\"municipi\":\"$MUNICIPI\",\"tic_nom\":\"TIC Smoke\",\"tic_email\":\"$TIC_EMAIL\"}")"
assert_ok_true "$R1"
CENTRE_ID="$(extract_path "$R1" "centre.id")"
echo "CENTRE_ID=$CENTRE_ID"

echo "== 2) registrar centre duplicat =="
R2="$(json_post "$BASE_URL/joc_lector/api/centre/registrar" "{\"name\":\"$CENTRE_NAME DUP\",\"email_oficial\":\"$EMAIL_OK\"}")"
assert_error_code "$R2" "centre_already_registered"

echo "== 3) registrar centre email invalid =="
R3="$(json_post "$BASE_URL/joc_lector/api/centre/registrar" "{\"name\":\"Centre Invalid\",\"email_oficial\":\"$EMAIL_BAD\"}")"
assert_error_code "$R3" "invalid_official_email"

echo "== 4) validar codi admin centre =="
set_known_admin_code "$EMAIL_OK" "$CENTRE_CODE"
R4="$(json_post "$BASE_URL/joc_lector/api/centre/admin/validar_codi" "{\"centre_id\":$CENTRE_ID,\"email_centre\":\"$EMAIL_OK\",\"admin_code\":\"$CENTRE_CODE\"}")"
assert_ok_true "$R4"
ADMIN_TOKEN="$(extract_path "$R4" "admin_token.access_token")"

echo "== 4b) snapshot admin centre =="
R4B="$(json_post_auth "$BASE_URL/joc_lector/api/centre/admin/snapshot" "$ADMIN_TOKEN" '{}')"
assert_ok_true "$R4B"

echo "== 4c) configurar ranking public agregat =="
R4C="$(json_post_auth "$BASE_URL/joc_lector/api/centre/admin/configuracio" "$ADMIN_TOKEN" '{"ranking_public":true,"web_publica_activa":true}')"
assert_ok_true "$R4C"

echo "== 5) buscar centre =="
R5="$(json_get "$BASE_URL/joc_lector/api/centres/buscar?q=$TS")"
assert_ok_true "$R5"

echo "== 6) professor sollicitar acces =="
R6="$(json_post "$BASE_URL/joc_lector/api/professor/solicitar_acces" "{\"centre_id\":$CENTRE_ID,\"professor_nom\":\"Professor Smoke\",\"professor_email\":\"$PROF_EMAIL\",\"municipi\":\"$MUNICIPI\"}")"
assert_ok_true "$R6"
SOLICITUD_ID="$(extract_path "$R6" "solicitud.id")"
echo "SOLICITUD_ID=$SOLICITUD_ID"

echo "== 7) convidar professor =="
INVITE_EMAIL="invite_${PROF_EMAIL}"
R7="$(json_post_auth "$BASE_URL/joc_lector/api/centre/admin/convidar_professor" "$ADMIN_TOKEN" "{\"email\":\"$INVITE_EMAIL\",\"name\":\"Professor Convidat\"}")"
assert_ok_true "$R7"

echo "== 8) llistar sollicituds pendents (admin centre) =="
R7="$(json_post_auth "$BASE_URL/joc_lector/api/centre/admin/solicituds_pendents" "$ADMIN_TOKEN" '{}')"
assert_ok_true "$R7"

echo "== 9) acceptar professor =="
R8="$(json_post_auth "$BASE_URL/joc_lector/api/professor/acceptar_solicitud" "$ADMIN_TOKEN" "{\"solicitud_id\":$SOLICITUD_ID}")"
assert_ok_true "$R8"

PROF_ID="$(extract_path "$R8" "professor_id")"
echo "PROF_ID=$PROF_ID"

echo "== 10) verificar professor assignat al centre (SQL) =="
(
  cd "$ODOO_ROOT"
  docker compose exec -T db psql -U odoo -d "$ODOO_DB" -v ON_ERROR_STOP=1 -c \
    "SELECT id, name, centre_id, active FROM joc_lector_professor WHERE id=${PROF_ID};"
)

echo "== 11) comprovar alumne sense codi de classe =="
R10="$(json_post "$BASE_URL/api/joc/alumne/crear" "{\"name\":\"Alumne sense codi\"}")"
assert_error_code "$R10" "missing_access_code"

echo "OK smoke_institucional completat"
