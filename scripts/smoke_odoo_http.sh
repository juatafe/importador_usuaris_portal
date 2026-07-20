#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8069}"
HOST_HEADER="${HOST_HEADER:-provestalens.es}"
CURL=(curl --silent --show-error --max-time 20 --output /dev/null
  --header "Host: ${HOST_HEADER}"
  --header "X-Forwarded-Proto: https")

request_code() {
  local path="$1"
  local code

  if ! code="$("${CURL[@]}" --write-out '%{http_code}' "${BASE_URL}${path}")"; then
    echo "FAIL ${path}: connection closed or curl failed" >&2
    return 1
  fi
  if [[ ! "$code" =~ ^[1-5][0-9][0-9]$ ]]; then
    echo "FAIL ${path}: invalid HTTP status ${code}" >&2
    return 1
  fi
  printf '%s' "$code"
}

login_code="$(request_code /web/login)"
[[ "$login_code" == 200 ]] || {
  echo "FAIL /web/login: expected 200, got ${login_code}" >&2
  exit 1
}
echo "PASS /web/login: HTTP ${login_code}"

lectures_code="$(request_code /lectures/)"
echo "PASS /lectures/: HTTP ${lectures_code} (connection returned a response)"

redirect_code="$(request_code /web)"
[[ "$redirect_code" =~ ^3[0-9][0-9]$ ]] || {
  echo "FAIL /web: expected a redirect, got ${redirect_code}" >&2
  exit 1
}
echo "PASS /web redirect: HTTP ${redirect_code}"
