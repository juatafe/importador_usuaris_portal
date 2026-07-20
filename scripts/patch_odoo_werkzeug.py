#!/usr/bin/env python3
"""Keep Odoo 16 redirects compatible with old and new Werkzeug releases."""

from pathlib import Path


HTTP_PY = Path("/usr/lib/python3/dist-packages/odoo/http.py")

BROKEN = """def get_response(self, environ=None, scope=None):
    return Response(__wz_get_response(self, environ, scope))
"""

FIXED = """def get_response(self, environ=None, scope=None):
    # Werkzeug 1.x accepts only environ; Werkzeug 2.x also accepts ASGI scope.
    if scope is None:
        return Response(__wz_get_response(self, environ))
    return Response(__wz_get_response(self, environ, scope))
"""

UPSTREAM_FIXED = """def get_response(self, environ=None, scope=None):
    if scope is None:  # compatible with werkzeug 0.16.x
        return Response(__wz_get_response(self, environ))
    else:
        return Response(__wz_get_response(self, environ, scope))  # werkzeug 2.0.2
"""


def main():
    source = HTTP_PY.read_text()
    matches = sum(block in source for block in (BROKEN, FIXED, UPSTREAM_FIXED))
    if matches != 1:
        raise SystemExit(
            f"Cannot safely patch {HTTP_PY}: expected exactly one known "
            "Odoo HTTPException.get_response block"
        )

    if BROKEN in source:
        HTTP_PY.write_text(source.replace(BROKEN, FIXED, 1))
        print(f"Patched Werkzeug redirect compatibility in {HTTP_PY}")
    else:
        print(f"Werkzeug redirect compatibility already present in {HTTP_PY}")


if __name__ == "__main__":
    main()
