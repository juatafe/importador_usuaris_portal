#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys

DEFAULT_BASE_URL = "https://provestalens.es/scanner/api"


def run_curl(endpoint, data=None, token=None, base_url=DEFAULT_BASE_URL, verbose=False):
    """Executa una crida curl i retorna la resposta JSON"""
    cmd = [
        "curl", "-s", "-k", "-X", "POST", f"{base_url}{endpoint}",
        "-H", "Content-Type: application/json",
    ]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if data is None:
        data = {}
    cmd += ["-d", json.dumps(data)]

    if verbose:
        print("   ▶ curl:", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"error": "Invalid JSON", "raw": result.stdout}


def main():
    parser = argparse.ArgumentParser(description="Runner de proves per a l'Scanner API")
    parser.add_argument("--user", required=True, help="Usuari per fer login")
    parser.add_argument("--password", required=True, help="Password per fer login")
    parser.add_argument("--barcode", help="Codi de barres a provar (opcional)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="URL base de l'API (per defecte: %(default)s)")
    parser.add_argument("--verbose", action="store_true", help="Mostra les comandes curl abans d'executar-les")
    args = parser.parse_args()

    print("▶ Running scanner API tests with curl...")

    # 1) LOGIN
    print("\n1) Login...")
    login_resp = run_curl("/login", {"user": args.user, "password": args.password}, base_url=args.base_url, verbose=args.verbose)
    print("   Response:", login_resp)
    token = login_resp.get("result", {}).get("token")
    if not token:
        print("❌ No s'ha pogut obtindre token")
        sys.exit(1)
    print("   ✅ Token:", token)

    # 2) PING
    print("\n2) Ping...")
    ping_resp = run_curl("/ping", {}, token=token, base_url=args.base_url, verbose=args.verbose)
    print("   Response:", ping_resp)

    # 3) CHECK barcode (no trobat)
    print("\n3) Check barcode (not found)...")
    check_resp = run_curl("/check", {"barcode": "0000000000000"}, token=token, base_url=args.base_url, verbose=args.verbose)
    print("   Response:", check_resp)

    # 4) CHECK barcode (valid, si s'ha passat)
    if args.barcode:
        print("\n4) Check barcode (valid)...")
        check_resp2 = run_curl("/check", {"barcode": args.barcode}, token=token, base_url=args.base_url, verbose=args.verbose)
        print("   Response:", check_resp2)

    # 5) LOGOUT
    print("\n5) Logout...")
    logout_resp = run_curl("/logout", {}, token=token, base_url=args.base_url, verbose=args.verbose)
    print("   Response:", logout_resp)

    print("\n▶ Done.")


if __name__ == "__main__":
    main()
