# Joc Lector API V2 - Colleccio cURL

Base URL local d'exemple:

http://localhost:8069

## 0) Variables recomanades

```bash
BASE_URL="http://localhost:8069"
APP_UID="flutter-test-uid-001"
CODI_CLASSE="JL-2A4BEA"
NOM_VISIBLE="Lector Prova"
```

## 1) Health

```bash
curl -sS -X POST "$BASE_URL/joc_lector/api/health" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Resposta esperada:

```json
{"ok": true, "service": "joc_lector", "status": "up"}
```

## 2) Entrar classe (crea/enllaca alumne i retorna token)

```bash
curl -sS -X POST "$BASE_URL/joc_lector/api/alumne/entrar_classe" \
  -H "Content-Type: application/json" \
  -d "{\"codi_classe\":\"$CODI_CLASSE\",\"app_uid\":\"$APP_UID\",\"nom_visible\":\"$NOM_VISIBLE\"}"
```

Guarda el token retornat en token.access_token.

## 3) Sync lectures

Substituix TOKEN pel token real retornat en el pas 2.

```bash
TOKEN="PEGA_ACI_EL_TOKEN"

curl -sS -X POST "$BASE_URL/joc_lector/api/sync/lectures" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "lectures": [
      {
        "client_uid": "read-001",
        "titol": "Matilda",
        "autor": "Roald Dahl",
        "isbn": "9780142410370",
        "estat": "acabat",
        "data_inici": "2026-06-01",
        "data_fi": "2026-06-10",
        "valoracio": 5,
        "ressenya": "Molt divertit",
        "evidencia_text": "foto carnet lector",
        "visible_publicament": true
      }
    ]
  }'
```

Per provar deduplicacio per client_uid, torna a llançar exactament la mateixa peticio.

## 4) Passaport alumne

```bash
curl -sS -X POST "$BASE_URL/joc_lector/api/alumne/passaport" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}'
```

## 5) Cataleg actiu

```bash
curl -sS -X GET "$BASE_URL/joc_lector/api/cataleg"
```

## 6) Ranking meu (sense noms d'altres alumnes)

```bash
curl -sS -X POST "$BASE_URL/joc_lector/api/alumne/ranking/meu" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}'
```

## 7) Endpoints docents (sessio Odoo usuari)

Aquests endpoints usen auth=user. Primer cal autenticar sessio web d'Odoo i guardar cookie.

Prerequisit:

- L'usuari Odoo ha de tindre credencials correctes.
- L'usuari ha d'estar vinculat a un registre joc.lector.professor actiu.
- El perfil joc.lector.professor ha de tindre classes assignades per poder validar lectures.

### 7.1 Login docent en sessio Odoo

```bash
ODOO_DB="falla"
ODOO_LOGIN="admin"
ODOO_PASSWORD="admin"
COOKIE_JAR="/tmp/joc_lector_docent.cookies"

curl -sS -c "$COOKIE_JAR" -X POST "$BASE_URL/web/session/authenticate" \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"params\":{\"db\":\"$ODOO_DB\",\"login\":\"$ODOO_LOGIN\",\"password\":\"$ODOO_PASSWORD\"},\"id\":1}"
```

### 7.2 Classes del professor

```bash
curl -sS -b "$COOKIE_JAR" -X GET "$BASE_URL/joc_lector/api/professor/classes"
```

Resposta: cada classe inclou `id`, `server_id` i `serverId` amb el mateix valor,
per compatibilitat amb clients Flutter que guarden identificadors locals i de
servidor per separat.

```json
{
  "ok": true,
  "count": 1,
  "classes": [
    {
      "id": 12,
      "server_id": 12,
      "serverId": 12,
      "name": "6é A",
      "access_code": "JL-ABC123",
      "codi_acces": "JL-ABC123",
      "actions": {
        "reenviar_credencials_url": "/joc_lector/api/professor/classe/credencials/reenviar"
      }
    }
  ]
}
```

### 7.3 Crear o sincronitzar classe docent

```bash
curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/joc_lector/api/docent/classes" \
  -H "Content-Type: application/json" \
  -d '{"nom":"6é A","curs_academic":"2026-2027","curs_grup":"6A","alumnes":["Aina","Marc"]}'
```

El servidor genera `classe.access_code`/`classe.codi_acces` i retorna
`classe.serverId` perquè l'app el guarde abans d'obrir el detall o reenviar
credencials.

### 7.4 Reenviar credencials de classe

```bash
curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/joc_lector/api/professor/classe/credencials/reenviar" \
  -H "Content-Type: application/json" \
  -d '{"classe_id": 12}'
```

També s'accepten `classeId`, `server_id`, `serverId`, `codi_classe`,
`codiClasse`, `codi_acces`, `access_code` i `accessCode`.

### 7.5 Validacions pendents

```bash
curl -sS -b "$COOKIE_JAR" -X GET "$BASE_URL/joc_lector/api/professor/validacions_pendents"
```

### 7.6 Validar lectura (acceptada)

Substituix LECTURA_ID per una lectura pendent de les teues classes.

```bash
LECTURA_ID="5"

curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/joc_lector/api/professor/validar_lectura" \
  -H "Content-Type: application/json" \
  -d "{\"lectura_id\": $LECTURA_ID, \"decisio\": \"acceptada\", \"visible_publicament\": true, \"comentari\": \"Validada en revisio docent\"}"
```

## 8) Comprovar moviments de punts des de PostgreSQL (Docker)

```bash
cd /home/talens/odoo_server

docker compose exec -T db psql -U odoo -d falla -c "
SELECT id, alumne_id, origen, lectura_id, repte_id, punts, motiu, data
FROM joc_lector_punts_moviment
ORDER BY id DESC
LIMIT 20;"
```

## 9) Comprovar passaport recalculat

```bash
cd /home/talens/odoo_server

docker compose exec -T db psql -U odoo -d falla -c "
SELECT p.id, p.alumne_id, p.punts, p.nivell, p.llibres_llegits
FROM joc_lector_passaport p
ORDER BY p.id DESC
LIMIT 20;"
```

## 10) Criteris de validacio funcional

- health respon ok true
- entrar_classe retorna token i dades de centre/classe
- sync_lectures crea o actualitza i manté estat_validacio
- passaport retorna lectures i estat_validacio
- validar_lectura amb decisio acceptada crea moviment en punts
- ranking/meu no exposa noms d'altres alumnes

## 11) Admin centre

```bash
ADMIN_CODE="ABC123"
CENTRE_ID="3"

curl -sS -X POST "$BASE_URL/joc_lector/api/centre/admin/validar_codi" \
  -H "Content-Type: application/json" \
  -d "{\"centre_id\":$CENTRE_ID,\"admin_code\":\"$ADMIN_CODE\"}"
```

Guarda `admin_token.access_token`:

```bash
ADMIN_TOKEN="PEGA_ACI_EL_TOKEN_ADMIN"

curl -sS -X POST "$BASE_URL/joc_lector/api/centre/admin/snapshot" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```bash
curl -sS -X POST "$BASE_URL/joc_lector/api/centre/admin/configuracio" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ranking_public":true,"web_publica_activa":true}'
```

```bash
curl -sS -X POST "$BASE_URL/joc_lector/api/centre/admin/convidar_professor" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"professor@example.org","name":"Professor Exemple"}'
```
