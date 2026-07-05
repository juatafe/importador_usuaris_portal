#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-https://provestalens.es}"

echo "== Joc Lector smoke test =="
echo "BASE_URL=$BASE_URL"
echo

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: falta el comandament $1"
    exit 1
  }
}

need_cmd curl
need_cmd python3

json_get() {
  curl -s "$1"
}

json_post() {
  curl -s -X POST "$1" \
    -H "Content-Type: application/json" \
    -d "$2"
}

json_post_auth() {
  curl -s -X POST "$1" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$2"
}

json_get_auth() {
  curl -s "$1" \
    -H "Authorization: Bearer $TOKEN"
}

assert_ok() {
  python3 - "$1" <<'PY'
import json
import sys

raw = sys.argv[1]
data = json.loads(raw)

if data.get("ok") is not True:
    print("ERROR: resposta amb ok != true")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(1)
PY
}

extract() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
path = sys.argv[2].split(".")

value = data
for key in path:
    if isinstance(value, list):
        value = value[int(key)]
    else:
        value = value[key]

print(value)
PY
}

echo "1) Ping"
PING=$(json_get "$BASE_URL/api/joc/ping")
assert_ok "$PING"
echo "OK ping"
echo

echo "2) Buscar codi de classe"
CODI_CLASSE="${CODI_CLASSE:-JL-2A4BEA}"
echo "CODI_CLASSE=$CODI_CLASSE"
echo

echo "3) Alta alumne de prova"
NOM="Smoke Test $(date +%s)"
ALTA=$(json_post "$BASE_URL/api/joc/alumne/crear" "{
  \"name\": \"$NOM\",
  \"access_code\": \"$CODI_CLASSE\",
  \"device_name\": \"smoke api\"
}")
assert_ok "$ALTA"
TOKEN=$(extract "$ALTA" "token.access_token")
echo "OK alta alumne: $NOM"
echo

echo "4) Passaport amb token"
PASSAPORT=$(json_get_auth "$BASE_URL/api/joc/passaport")
assert_ok "$PASSAPORT"
echo "OK passaport"
echo

echo "5) Llistat llibres"
LLIBRES=$(json_get "$BASE_URL/api/joc/llibres")
assert_ok "$LLIBRES"
LLIBRE_ID=$(extract "$LLIBRES" "llibres.0.id")
echo "OK llibres. Primer llibre id=$LLIBRE_ID"
echo

echo "6) Crear lectura"
LECTURA_JSON=$(json_post_auth "$BASE_URL/api/joc/lectura/crear" "{
  \"llibre_id\": $LLIBRE_ID,
  \"state\": \"reading\",
  \"punts_obtinguts\": 10
}")
assert_ok "$LECTURA_JSON"
LECTURA_ID=$(extract "$LECTURA_JSON" "lectura.id")
echo "OK lectura creada id=$LECTURA_ID"
echo

echo "7) Acabar lectura"
LECTURA_FI=$(json_post_auth "$BASE_URL/api/joc/lectura/acabar" "{
  \"lectura_id\": $LECTURA_ID,
  \"punts_obtinguts\": 10
}")
assert_ok "$LECTURA_FI"
echo "OK lectura acabada"
echo

echo "8) Crear ressenya"
RESSENYA=$(json_post_auth "$BASE_URL/api/joc/ressenya/crear" "{
  \"lectura_id\": $LECTURA_ID,
  \"text\": \"Ressenya automàtica de prova smoke test.\",
  \"valoracio\": 5,
  \"publicable\": true
}")
assert_ok "$RESSENYA"
echo "OK ressenya creada pendent d'aprovació"
echo

echo "9) Web pública"
curl -fsS "$BASE_URL/lectures" >/dev/null
curl -fsS "$BASE_URL/lectures/llibres" >/dev/null
curl -fsS "$BASE_URL/lectures/top" >/dev/null
echo "OK web pública respon"
echo

echo "10) Comprovació de dades sensibles en web pública"
if curl -s "$BASE_URL/lectures" | grep -Ei "app_uid|access_code|access_token|Authorization|Bearer|email_to" >/dev/null; then
  echo "ERROR: possible dada sensible en /lectures"
  exit 1
fi

echo "OK sense dades sensibles bàsiques"
echo

echo "✅ Smoke test completat correctament"
