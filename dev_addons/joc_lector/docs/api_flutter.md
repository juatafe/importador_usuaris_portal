# Joc Lector — Contracte API per a Flutter

Base URL:

    https://provestalens.es

Les rutes protegides usen esta capçalera:

    Authorization: Bearer <access_token>

## Flux inicial de l'app

1. Alumne nou:
   - POST /api/joc/alumne/crear
   - retorna alumne, passaport i token.

2. Alumne existent:
   - POST /api/joc/auth/login
   - login provisional amb app_uid.

3. Recuperació:
   - POST /api/joc/recuperacio/solicitar
   - POST /api/joc/recuperacio/validar

4. Ús normal:
   - GET /api/joc/passaport
   - GET /api/joc/llibres
   - GET /api/joc/lectures
   - POST /api/joc/lectura/crear
   - POST /api/joc/lectura/acabar
   - GET /api/joc/ressenyes
   - POST /api/joc/ressenya/crear
   - POST /api/joc/classe/entrar

## 1. Ping

GET /api/joc/ping

Comprova que l'API està activa.

Resposta esperada:

    {
      "ok": true,
      "module": "joc_lector",
      "version": "16.0.1.x.0",
      "message": "Joc Lector API activa"
    }

## 2. Alta inicial d'alumne

POST /api/joc/alumne/crear

Crea alumne, matrícula, passaport i token.

Request:

    {
      "name": "Maria",
      "access_code": "JL-2A4BEA",
      "device_name": "mòbil Maria"
    }

Resposta:

    {
      "ok": true,
      "message": "Alumne creat correctament.",
      "alumne": {
        "id": 4,
        "name": "Maria"
      },
      "passaport": {
        "id": 4,
        "punts": 0,
        "nivell": 1,
        "llibres_llegits": 0
      },
      "token": {
        "access_token": "...",
        "token_type": "Bearer",
        "expires_at": "2027-07-01 14:18:15"
      }
    }

Flutter ha de guardar token.access_token de manera segura.

## 3. Login provisional

POST /api/joc/auth/login

Request:

    {
      "app_uid": "05ea39645be8402889784281cd0c038d",
      "device_name": "mòbil alumne"
    }

Resposta:

    {
      "ok": true,
      "message": "Sessió iniciada correctament.",
      "alumne": {
        "id": 2,
        "name": "Alumne de prova"
      },
      "passaport": {
        "id": 2,
        "punts": 25,
        "nivell": 1,
        "llibres_llegits": 2
      },
      "token": {
        "access_token": "...",
        "token_type": "Bearer"
      }
    }

## 4. Logout

POST /api/joc/auth/logout

Requereix:

    Authorization: Bearer <access_token>

Resposta:

    {
      "ok": true,
      "message": "Sessió tancada correctament."
    }

## 5. Recuperació d'accés

POST /api/joc/recuperacio/solicitar

Demana un codi de recuperació. L'email s'usa només per enviar el codi i no es guarda en els models del Joc Lector.

Request:

    {
      "name": "Maria",
      "access_code": "JL-2A4BEA",
      "email": "maria@example.com",
      "device_name": "mòbil nou"
    }

Resposta:

    {
      "ok": true,
      "message": "S'ha enviat un codi de recuperació a l'email indicat.",
      "recovery_id": 2,
      "expires_at": "2026-07-01 14:40:40",
      "code_hint": "63"
    }

POST /api/joc/recuperacio/validar

Valida el codi i torna un token nou.

Request:

    {
      "recovery_id": 2,
      "code": "830963",
      "device_name": "mòbil recuperat"
    }

Resposta:

    {
      "ok": true,
      "message": "Accés recuperat correctament.",
      "token": {
        "access_token": "...",
        "token_type": "Bearer"
      }
    }

## 6. Passaport

GET /api/joc/passaport

Requereix:

    Authorization: Bearer <access_token>

Resposta:

    {
      "ok": true,
      "alumne": {
        "id": 4,
        "name": "Maria"
      },
      "passaport": {
        "id": 4,
        "punts": 0,
        "nivell": 1,
        "llibres_llegits": 0
      }
    }

## 7. Llibres

GET /api/joc/llibres

Llista llibres actius.

Resposta:

    {
      "ok": true,
      "count": 1,
      "llibres": [
        {
          "id": 1,
          "name": "El petit príncep",
          "autor": "Antoine de Saint-Exupéry",
          "isbn": "978-0156012195",
          "categoria": "Clàssics",
          "edat_recomanada": "12+",
          "slug": "el-petit-príncep-1",
          "lectura_count": 2,
          "ressenya_count": 1,
          "valoracio_mitjana": 5.0
        }
      ]
    }

## 8. Lectures

GET /api/joc/lectures

Requereix token Bearer.

POST /api/joc/lectura/crear

Request:

    {
      "llibre_id": 1,
      "state": "reading",
      "punts_obtinguts": 10
    }

Valors possibles de state:

    pending
    reading
    finished
    abandoned

POST /api/joc/lectura/acabar

Request:

    {
      "lectura_id": 3,
      "punts_obtinguts": 10
    }

Marca una lectura com acabada i aplica punts si encara no estaven aplicats.

## 9. Ressenyes

GET /api/joc/ressenyes

Requereix token Bearer.

POST /api/joc/ressenya/crear

Request amb lectura:

    {
      "lectura_id": 3,
      "text": "M'ha agradat molt.",
      "valoracio": 5,
      "publicable": true
    }

Request només amb llibre:

    {
      "llibre_id": 1,
      "text": "M'ha semblat interessant.",
      "valoracio": 4,
      "publicable": true
    }

Les ressenyes creades queden pendents d'aprovació.

## 10. Entrar en una nova classe

POST /api/joc/classe/entrar

Requereix token Bearer.

Request:

    {
      "access_code": "JL-2A4BEA"
    }

Conserva el passaport lector i tanca la matrícula anterior.

## 11. Errors

Format general:

    {
      "ok": false,
      "error": {
        "code": "invalid_token",
        "message": "Token invàlid o caducat."
      }
    }

Codis habituals:

    missing_auth
    invalid_token
    student_not_found
    class_not_found
    book_not_found
    reading_not_found
    invalid_rating
    invalid_code
    expired
    too_many_attempts
    email_send_failed

Flutter sempre ha de comprovar:

    ok == true

Si ok és false, ha de llegir:

    error.code
    error.message

## 12. Web pública

Rutes públiques:

    /lectures
    /lectures/llibres
    /lectures/top
    /lectures/llibre/<slug>
    /lectures/ressenya/<slug>

Només es publiquen ressenyes amb:

    publicable = true
    aprovada = true
    active = true

La web pública no ha de mostrar mai:

    app_uid
    access_code
    access_token
    Authorization
    Bearer
    email_to
    nom de l'alumne
