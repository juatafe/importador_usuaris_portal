# Contracte API Odoo per a Joc Lector

La Flutter app funciona en mode local si `JOC_API_BASE_URL` no està definit.
Quan està configurat, Odoo actua com a font de veritat i la sincronització és
best effort: primer es guarda localment i després es puja al backend.

## Principis de dades

- El passaport lector és personal i històric.
- La participació en classe, centre i curs és contextual.
- Un canvi de codi de classe no ha de crear un passaport nou ni perdre lectures.
- Les ressenyes públiques només poden eixir si estan validades i
  `visiblePublicament` és `true`.
- El correu temporal de recuperació s'envia a Odoo però no s'ha de persistir.
- `publicRankingEnabled` només activa rànquings públics agregats de centre.
- Els rànquings públics no poden exposar noms d'alumnes.

## Autenticació docent

`POST /joc_lector/api/professor/demanar_codi`

```json
{ "email": "docent@centre.edu" }
```

També s'accepten els àlies `enviar_codi` i `reenviar_codi`.

`POST /joc_lector/api/professor/verificar_codi`

```json
{ "email": "docent@centre.edu", "codi": "CODI_REBUT_PER_EMAIL" }
```

Resposta:

```json
{
  "ok": true,
  "access_token": "token",
  "token_type": "Bearer",
  "professor": {
    "id": 12,
    "email": "docent@centre.edu",
    "rol": "professor"
  },
  "centre": { "id": 3 }
}
```

Els endpoints docents de gestió accepten `Authorization: Bearer <access_token>`.

`POST /joc_lector/api/docent/classes`

Crea o sincronitza una classe del professorat en Odoo. El servidor genera el
codi de classe i, si s'envien alumnes, també els codis d'alumne. També
s'accepten els àlies `/joc_lector/api/professor/classes/crear` i
`/joc_lector/api/professor/classe/crear`.

```json
{
  "nom": "6é A",
  "curs_academic": "2026-2027",
  "curs_grup": "6A",
  "nivell": "6é Primària",
  "alumnes": ["Aina", "Marc"]
}
```

Resposta:

```json
{
  "ok": true,
  "created": true,
  "classe": {
    "id": 12,
    "server_id": 12,
    "serverId": 12,
    "name": "6é A",
    "access_code": "JL-ABC123",
    "codi_acces": "JL-ABC123"
  },
  "created_students_count": 2,
  "alumnes": [
    {
      "id": 45,
      "name": "Aina",
      "codi_alumne": "XXXXXX",
      "classe_id": 12,
      "codi_classe": "JL-ABC123"
    }
  ]
}
```

## Accés alumne

`POST /joc/api/student/access`

```json
{ "accessCode": "ORONETA-02-RQ" }
```

Resposta:

```json
{
  "classe": {
    "nom": "2n ESO A",
    "curs": "2026-2027",
    "codi": "2ESOA-26",
    "centreId": "3",
    "docentId": "12",
    "alumnes": []
  },
  "alumne": {
    "ordre": 2,
    "idLlista": "A02",
    "animal": "Oroneta",
    "codiAcces": "ORONETA-02-RQ",
    "actiu": true
  },
  "lectures": [],
  "passaportHistoric": []
}
```

`lectures` són les lectures visibles en la classe/curs actual.  
`passaportHistoric` és el passaport personal recuperable, sense donar al
professor nou visibilitat de tot l'històric.

## Sincronització alumne

`POST /joc/api/sync/student_passport`

```json
{
  "accessCode": "ORONETA-02-RQ",
  "classCode": "2ESOA-26",
  "studentLocalId": "A02",
  "readings": [
    {
      "llibreId": "cat_123",
      "titol": "Wonder",
      "autor": "R. J. Palacio",
      "estat": "llegit",
      "dataInici": "2026-06-01",
      "dataFi": "2026-06-12",
      "valoracio": 5,
      "ressenya": "Text de l'alumne",
      "validacio": "pendent",
      "visiblePublicament": true
    }
  ]
}
```

Odoo ha de validar estats, persistir lectures, conservar l'històric personal i
mantindre separada la participació contextual de classe/curs.

## Sincronització docent/admin

`POST /joc/api/sync/centre`

```json
{
  "id": "3",
  "nom": "IES Exemple",
  "codi": "IES-EX",
  "poblacio": "València",
  "emailDomini": "iesexemple.edu",
  "publicRankingEnabled": false
}
```

`POST /joc/api/sync/classes`

```json
{ "classes": [] }
```

`POST /joc/api/sync/reptes`

```json
{ "challenges": [] }
```

`GET /joc/api/sync/teacher_snapshot`

```json
{
  "centre": {},
  "classes": [],
  "reptes": []
}
```

## Administració de centre

Els endpoints d'administració de centre usen un token propi de centre:
`Authorization: Bearer ADMIN_TOKEN`. No accepten tokens d'alumne.

`POST /joc_lector/api/centre/admin/validar_codi`

```json
{ "centre_id": 3, "email_centre": "12345678@edu.gva.es", "admin_code": "ABC123" }
```

Resposta:

```json
{
  "ok": true,
  "admin_token": {
    "access_token": "token",
    "token_type": "Bearer",
    "expires_at": "2026-07-09 12:00:00"
  },
  "centre": {}
}
```

El codi d'administració es guarda només com a hash i caduca. El token d'admin
centre també es guarda hashejat en `joc.lector.centre.admin.token` i pot
caducar o revocar-se desactivant-lo.

`POST /joc_lector/api/centre/admin/reenviar_codi`

```json
{ "centre_id": 3, "email_centre": "12345678@edu.gva.es" }
```

Genera un codi nou, invalida l'anterior i l'envia al correu oficial.

`GET|POST /joc_lector/api/centre/admin/snapshot`

Retorna dades del centre, configuració, professorat actiu, sol·licituds
pendents i invitacions pendents. No retorna alumnat, passaports ni rànquings
individuals.

`POST /joc_lector/api/centre/admin/actualitzar`

Permet actualitzar només camps no sensibles: `name`, `municipi`,
`persona_tic`/`tic_nom`, `email_tic`/`tic_email`.

També permet canviar el correu oficial amb `email_oficial`, `official_email` o
`correu_oficial`. Odoo valida el format `numero@edu.gva.es`, comprova que no
existisca un altre centre actiu amb el mateix correu, recalcula `code`/
`codi_centre` amb la part anterior a `@`, marca el centre com no verificat,
envia un nou codi d'administració al correu oficial nou i revoca els tokens
admin actius del centre.

`POST /joc_lector/api/centre/admin/configuracio`

```json
{ "ranking_public": true, "web_publica_activa": true }
```

El rànquing públic és agregat i només compta lectures validades.

`POST /joc_lector/api/centre/admin/convidar_professor`

```json
{ "email": "professor@example.org", "name": "Professor Exemple" }
```

No duplica invitacions actives del mateix email i centre, i no retorna el token
en clar. El correu apunta a la vista nativa de l'app:
`/lectures/app/?view=professor_invitacio&token=TOKEN`.

L'app accepta la invitació amb:

`POST /joc_lector/api/professor/acceptar_invitacio`

```json
{ "token": "TOKEN" }
```

`POST /joc_lector/api/professor/solicitar_centre`

```json
{ "centre_id": 3, "email": "professor@example.org", "name": "Professor Exemple", "justificacio": "Soc docent del centre" }
```

Els correus de resolució apunten a:
`/lectures/app/?view=professor_solicitud&action=acceptar&token=TOKEN` i
`/lectures/app/?view=professor_solicitud&action=rebutjar&token=TOKEN`.

`POST /joc_lector/api/centre/admin/professorat/resoldre`

```json
{ "solicitud_id": 7, "decisio": "acceptar", "rol": "professor" }
```

`GET|POST /joc_lector/api/centre/admin/professorat`

Llista professorat actiu, sol·licituds pendents i invitacions pendents, sense
dades d'alumnat.

## Recuperació d'accés

`POST /joc/api/recovery/request_code`

```json
{ "email": "correu.temporal@example.com" }
```

Odoo pot usar este correu per enviar el codi en eixe moment, però no l'ha de
guardar com a dada persistent de l'alumne.

## Web pública futura

Les dades públiques han de vindre d'endpoints agregats, per exemple:

`GET /joc/api/public/summary`

Resposta orientativa:

```json
{
  "centreId": "3",
  "curs": "2026-2027",
  "llibresLlegits": 124,
  "paginesValidades": 21800,
  "ressenyesPubliques": 57,
  "publicRankingEnabled": true
}
```

No ha d'incloure noms d'alumnes ni posicions individuals.
