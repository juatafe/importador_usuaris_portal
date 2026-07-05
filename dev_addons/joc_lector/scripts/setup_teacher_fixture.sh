#!/usr/bin/env bash

set -euo pipefail

ODOO_DIR="${ODOO_DIR:-/home/talens/odoo_server}"
ODOO_DB="${ODOO_DB:-falla}"
CODI_CLASSE="${CODI_CLASSE:-JL-2A4BEA}"
TEACHER_LOGIN="${TEACHER_LOGIN:-docent_smoke}"
TEACHER_PASSWORD="${TEACHER_PASSWORD:-docent_smoke_123}"
TEACHER_NAME="${TEACHER_NAME:-Docent Smoke}"

cd "$ODOO_DIR"

docker compose exec -T \
    -e ODOO_DB="$ODOO_DB" \
    -e CODI_CLASSE="$CODI_CLASSE" \
    -e TEACHER_LOGIN="$TEACHER_LOGIN" \
    -e TEACHER_PASSWORD="$TEACHER_PASSWORD" \
    -e TEACHER_NAME="$TEACHER_NAME" \
    web odoo shell -c /etc/odoo/odoo.conf -d "$ODOO_DB" --http-port=8099 <<'PY'
import os

DB = os.environ["ODOO_DB"]
CODI = os.environ["CODI_CLASSE"]
LOGIN = os.environ["TEACHER_LOGIN"]
PASSWORD = os.environ["TEACHER_PASSWORD"]
NAME = os.environ["TEACHER_NAME"]

Users = env["res.users"].sudo()
Classe = env["joc.lector.classe"].sudo().search([("access_code", "=", CODI)], limit=1)
if not Classe:
    raise Exception(f"No existeix classe amb codi {CODI}")

group_prof = env.ref("joc_lector.group_joc_lector_professor")
group_user = env.ref("base.group_user")

user = Users.search([("login", "=", LOGIN)], limit=1)
if not user:
    user = Users.create({
        "name": NAME,
        "login": LOGIN,
        "password": PASSWORD,
        "groups_id": [(6, 0, [group_user.id, group_prof.id])],
    })
else:
    groups = set(user.groups_id.ids)
    groups.update([group_user.id, group_prof.id])
    user.write({"groups_id": [(6, 0, list(groups))], "name": NAME, "password": PASSWORD})

user.sudo().write({"active": True})

Professor = env["joc.lector.professor"].sudo().search([
    ("user_id", "=", user.id),
    ("centre_id", "=", Classe.centre_id.id),
], limit=1)

if not Professor:
    Professor = env["joc.lector.professor"].sudo().create({
        "name": NAME,
        "user_id": user.id,
        "centre_id": Classe.centre_id.id,
        "rol": "professor",
        "classe_ids": [(6, 0, [Classe.id])],
        "active": True,
    })
else:
    class_ids = set(Professor.classe_ids.ids)
    class_ids.add(Classe.id)
    Professor.write({"classe_ids": [(6, 0, list(class_ids))], "active": True, "rol": "professor"})

if user.id not in Classe.professor_ids.ids:
    Classe.write({"professor_ids": [(4, user.id)]})

if Professor.id not in Classe.professor_joc_ids.ids:
    Classe.write({"professor_joc_ids": [(4, Professor.id)]})

env.cr.commit()

# Comprovacio d'autenticacio en servidor: alguns entorns poden bloquejar login web.
uid = False
try:
    uid = env["res.users"].sudo().authenticate(DB, LOGIN, PASSWORD, {})
except Exception:
    uid = False

if uid:
    print(f"OK docent fixture + auth: login={LOGIN} password={PASSWORD} classe={Classe.access_code} db={DB}")
else:
    print(f"OK docent fixture (sense auth web): login={LOGIN} classe={Classe.access_code} db={DB}")
    print("WARNING: autenticacio web no validada en este entorn; revisa política d'autenticació/credencials.")
PY
