# Compatibilitat de redireccions entre Odoo 16 i Werkzeug

## Causa

La imatge construïda amb `odoo:16.0` contenia Odoo `16.0-20250819`,
Python `3.9.2` i Werkzeug `1.0.1`. Eixa revisió d'Odoo cridava
`HTTPException.get_response(self, environ, scope)`, però Werkzeug 1.0.1 només
accepta `self` i `environ`. Quan `website` o `http_routing` generava una
redirecció, el `TypeError` escapava de la capa HTTP i el client rebia una
connexió tancada sense resposta.

La branca oficial actual d'Odoo 16 ja diferencia entre Werkzeug antic (sense
`scope`) i nou (amb `scope`). El build executa
`scripts/patch_odoo_werkzeug.py` per garantir la mateixa compatibilitat fins i
tot si Docker reutilitza una revisió antiga de la imatge base. L'script és
idempotent i interromp el build si `odoo/http.py` no coincideix amb cap variant
coneguda.

## Reconstrucció i comprovació

Des de l'arrel del projecte:

```bash
docker compose build --pull web
docker compose up -d web
docker compose ps
./scripts/smoke_odoo_http.sh
docker compose logs --no-color --tail=200 web
```

El smoke test usa `http://127.0.0.1:8069`, `Host: provestalens.es` i
`X-Forwarded-Proto: https`. Comprova que `/web/login` respon 200, que
`/lectures/` retorna una resposta HTTP i que `/web` retorna una redirecció.

## Tornar arrere

Abans del desplegament, anota el hash de la imatge activa:

```bash
docker inspect odoo_server-web-1 --format '{{.Image}}'
```

Si la nova imatge falla, restaura el commit anterior amb `git revert`, torna a
construir la imatge i executa de nou el smoke test. Per una recuperació
immediata, etiqueta el hash anterior com `odoo_server-web:latest` i recrea només
el servei web:

```bash
docker tag <hash-anterior> odoo_server-web:latest
docker compose up -d --no-deps --force-recreate web
```

La correcció no modifica volums, base de dades, credencials, SMTP ni fitxers
`.env`.
