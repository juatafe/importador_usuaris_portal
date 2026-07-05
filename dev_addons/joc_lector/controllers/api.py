# -*- coding: utf-8 -*-

import json

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request, Response


JOC_LECTOR_EMAIL_FROM = "Joc Lector <joc-lector@provestalens.es>"


class JocLectorApiController(http.Controller):
    """API pública provisional per a l'app del Joc Lector.

    Nota:
    - En esta primera fase usem app_uid com a identificador provisional.
    - En una fase posterior afegirem tokens d'autenticació.
    """

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str)
        return Response(
            body,
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def _error(self, message, status=400, code="error"):
        return self._json_response(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                },
            },
            status=status,
        )

    def _payload(self):
        if request.httprequest.method != "POST":
            return {}

        raw = request.httprequest.data or b""
        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _param(self, name, default=None):
        payload = self._payload()
        return request.params.get(name) or payload.get(name) or default

    def _find_alumne_by_app_uid(self):
        app_uid = self._param("app_uid")
        if not app_uid:
            return None, self._error("Falta el paràmetre app_uid.", status=400, code="missing_app_uid")

        alumne = request.env["joc.lector.alumne"].sudo().search([
            ("app_uid", "=", app_uid),
            ("active", "=", True),
        ], limit=1)

        if not alumne:
            return None, self._error("No s'ha trobat cap alumne amb eixe app_uid.", status=404, code="student_not_found")

        return alumne, None

    def _serialize_classe(self, classe):
        if not classe:
            return None

        return {
            "id": classe.id,
            "name": classe.name,
            "curs_academic": classe.curs_academic,
            "access_code": classe.access_code,
            "centre": {
                "id": classe.centre_id.id,
                "name": classe.centre_id.name,
                "code": classe.centre_id.code,
            } if classe.centre_id else None,
        }

    def _serialize_alumne(self, alumne):
        return {
            "id": alumne.id,
            "name": alumne.name,
            "app_uid": alumne.app_uid,
            "current_classe": self._serialize_classe(alumne.current_classe_id),
        }

    def _serialize_passaport(self, passaport):
        if not passaport:
            return None

        return {
            "id": passaport.id,
            "punts": passaport.punts,
            "nivell": passaport.nivell,
            "llibres_llegits": passaport.llibres_llegits,
        }

    def _serialize_llibre(self, llibre):
        return {
            "id": llibre.id,
            "name": llibre.name,
            "autor": llibre.autor,
            "isbn": llibre.isbn,
            "editorial": llibre.editorial,
            "any_publicacio": llibre.any_publicacio,
            "categoria": llibre.categoria,
            "edat_recomanada": llibre.edat_recomanada,
            "resum": llibre.resum,
            "slug": llibre.slug,
            "lectura_count": llibre.lectura_count,
            "ressenya_count": llibre.ressenya_count,
            "valoracio_mitjana": llibre.valoracio_mitjana,
        }

    def _serialize_lectura(self, lectura):
        return {
            "id": lectura.id,
            "alumne_id": lectura.alumne_id.id,
            "llibre": self._serialize_llibre(lectura.llibre_id),
            "classe": self._serialize_classe(lectura.classe_id),
            "curs_academic": lectura.curs_academic,
            "date_start": lectura.date_start,
            "date_end": lectura.date_end,
            "state": lectura.state,
            "punts_obtinguts": lectura.punts_obtinguts,
            "points_applied": lectura.points_applied,
        }

    def _serialize_ressenya(self, ressenya):
        return {
            "id": ressenya.id,
            "alumne_id": ressenya.alumne_id.id,
            "llibre": self._serialize_llibre(ressenya.llibre_id),
            "lectura_id": ressenya.lectura_id.id if ressenya.lectura_id else None,
            "classe": self._serialize_classe(ressenya.classe_id),
            "curs_academic": ressenya.curs_academic,
            "text": ressenya.text,
            "valoracio": ressenya.valoracio,
            "publicable": ressenya.publicable,
            "aprovada": ressenya.aprovada,
            "slug": ressenya.slug,
        }

    @http.route(
        "/api/joc/ping",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def ping(self, **kwargs):
        module = request.env["ir.module.module"].sudo().search([
            ("name", "=", "joc_lector")
        ], limit=1)

        return self._json_response({
            "ok": True,
            "module": "joc_lector",
            "version": module.latest_version if module else None,
            "message": "Joc Lector API activa",
        })

    @http.route(
        "/api/joc/alumne",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        cors="*",
    )
    def alumne(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        return self._json_response({
            "ok": True,
            "alumne": self._serialize_alumne(alumne),
        })

    @http.route(
        "/api/joc/passaport",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        cors="*",
    )
    def passaport(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id)
        ], limit=1)

        return self._json_response({
            "ok": True,
            "alumne": self._serialize_alumne(alumne),
            "passaport": self._serialize_passaport(passaport),
        })

    @http.route(
        "/api/joc/llibres",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def llibres(self, **kwargs):
        limit = int(request.params.get("limit", 100))
        limit = max(1, min(limit, 200))

        llibres = request.env["joc.lector.llibre"].sudo().search([
            ("active", "=", True),
        ], order="name", limit=limit)

        return self._json_response({
            "ok": True,
            "count": len(llibres),
            "llibres": [self._serialize_llibre(llibre) for llibre in llibres],
        })

    @http.route(
        "/api/joc/lectures",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        cors="*",
    )
    def lectures(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        lectures = request.env["joc.lector.lectura"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], order="date_start desc, id desc")

        return self._json_response({
            "ok": True,
            "alumne": self._serialize_alumne(alumne),
            "count": len(lectures),
            "lectures": [self._serialize_lectura(lectura) for lectura in lectures],
        })

    @http.route(
        "/api/joc/ressenyes",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        cors="*",
    )
    def ressenyes(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        ressenyes = request.env["joc.lector.ressenya"].sudo().search([
            ("alumne_id", "=", alumne.id),
            ("active", "=", True),
        ], order="create_date desc, id desc")

        return self._json_response({
            "ok": True,
            "alumne": self._serialize_alumne(alumne),
            "count": len(ressenyes),
            "ressenyes": [self._serialize_ressenya(ressenya) for ressenya in ressenyes],
        })

    def _get_int_param(self, name, default=None):
        value = self._param(name, default)
        if value in (None, "", False):
            return default
        try:
            return int(value)
        except Exception:
            return default

    def _get_bool_param(self, name, default=False):
        value = self._param(name, default)

        if isinstance(value, bool):
            return value

        if value in (None, ""):
            return default

        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")

        return bool(value)

    def _find_llibre(self):
        llibre_id = self._get_int_param("llibre_id")
        if not llibre_id:
            return None, self._error("Falta el paràmetre llibre_id.", status=400, code="missing_book_id")

        llibre = request.env["joc.lector.llibre"].sudo().search([
            ("id", "=", llibre_id),
            ("active", "=", True),
        ], limit=1)

        if not llibre:
            return None, self._error("No s'ha trobat cap llibre amb eixe identificador.", status=404, code="book_not_found")

        return llibre, None

    def _find_lectura_for_alumne(self, alumne):
        lectura_id = self._get_int_param("lectura_id")
        if not lectura_id:
            return None, self._error("Falta el paràmetre lectura_id.", status=400, code="missing_reading_id")

        lectura = request.env["joc.lector.lectura"].sudo().search([
            ("id", "=", lectura_id),
            ("alumne_id", "=", alumne.id),
        ], limit=1)

        if not lectura:
            return None, self._error("No s'ha trobat cap lectura d'eixe alumne amb eixe identificador.", status=404, code="reading_not_found")

        return lectura, None

    @http.route(
        "/api/joc/lectura/crear",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def lectura_crear(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        llibre, error = self._find_llibre()
        if error:
            return error

        state = self._param("state", "reading")
        if state not in ("pending", "reading", "finished", "abandoned"):
            return self._error("L'estat de la lectura no és vàlid.", status=400, code="invalid_reading_state")

        punts_obtinguts = self._get_int_param("punts_obtinguts", 10)
        if punts_obtinguts < 0:
            return self._error("Els punts obtinguts no poden ser negatius.", status=400, code="invalid_points")

        lectura = request.env["joc.lector.lectura"].sudo().create({
            "alumne_id": alumne.id,
            "llibre_id": llibre.id,
            "classe_id": alumne.current_classe_id.id if alumne.current_classe_id else False,
            "state": state,
            "punts_obtinguts": punts_obtinguts,
        })

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id)
        ], limit=1)

        return self._json_response({
            "ok": True,
            "message": "Lectura creada correctament.",
            "lectura": self._serialize_lectura(lectura),
            "passaport": self._serialize_passaport(passaport),
        })

    @http.route(
        "/api/joc/lectura/acabar",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def lectura_acabar(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        lectura, error = self._find_lectura_for_alumne(alumne)
        if error:
            return error

        if lectura.state == "finished" and lectura.points_applied:
            passaport = request.env["joc.lector.passaport"].sudo().search([
                ("alumne_id", "=", alumne.id)
            ], limit=1)

            return self._json_response({
                "ok": True,
                "message": "La lectura ja estava acabada.",
                "lectura": self._serialize_lectura(lectura),
                "passaport": self._serialize_passaport(passaport),
            })

        vals = {"state": "finished"}

        punts_obtinguts = self._get_int_param("punts_obtinguts", None)
        if punts_obtinguts is not None:
            if punts_obtinguts < 0:
                return self._error("Els punts obtinguts no poden ser negatius.", status=400, code="invalid_points")
            vals["punts_obtinguts"] = punts_obtinguts

        lectura.write(vals)

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id)
        ], limit=1)

        return self._json_response({
            "ok": True,
            "message": "Lectura acabada correctament.",
            "lectura": self._serialize_lectura(lectura),
            "passaport": self._serialize_passaport(passaport),
        })

    @http.route(
        "/api/joc/ressenya/crear",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def ressenya_crear(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        lectura_id = self._get_int_param("lectura_id")
        llibre_id = self._get_int_param("llibre_id")

        lectura = None
        llibre = None

        if lectura_id:
            lectura = request.env["joc.lector.lectura"].sudo().search([
                ("id", "=", lectura_id),
                ("alumne_id", "=", alumne.id),
            ], limit=1)

            if not lectura:
                return self._error("No s'ha trobat la lectura indicada per a eixe alumne.", status=404, code="reading_not_found")

            llibre = lectura.llibre_id

        elif llibre_id:
            llibre = request.env["joc.lector.llibre"].sudo().search([
                ("id", "=", llibre_id),
                ("active", "=", True),
            ], limit=1)

            if not llibre:
                return self._error("No s'ha trobat el llibre indicat.", status=404, code="book_not_found")

        else:
            return self._error("Cal indicar lectura_id o llibre_id.", status=400, code="missing_book_or_reading")

        text = self._param("text", "")
        if not text or not str(text).strip():
            return self._error("El text de la ressenya no pot estar buit.", status=400, code="empty_review")

        valoracio = self._get_int_param("valoracio", 5)
        if valoracio < 1 or valoracio > 5:
            return self._error("La valoració ha d'estar entre 1 i 5.", status=400, code="invalid_rating")

        publicable = self._get_bool_param("publicable", False)

        vals = {
            "alumne_id": alumne.id,
            "llibre_id": llibre.id,
            "lectura_id": lectura.id if lectura else False,
            "classe_id": lectura.classe_id.id if lectura and lectura.classe_id else alumne.current_classe_id.id if alumne.current_classe_id else False,
            "text": str(text).strip(),
            "valoracio": valoracio,
            "publicable": publicable,
            "aprovada": False,
        }

        ressenya = request.env["joc.lector.ressenya"].sudo().create(vals)

        return self._json_response({
            "ok": True,
            "message": "Ressenya creada correctament. Queda pendent d'aprovació.",
            "ressenya": self._serialize_ressenya(ressenya),
        })

    @http.route(
        "/api/joc/classe/entrar",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def classe_entrar(self, **kwargs):
        alumne, error = self._find_alumne_by_app_uid()
        if error:
            return error

        access_code = self._param("access_code")
        if not access_code:
            return self._error("Falta el codi de classe.", status=400, code="missing_access_code")

        access_code = str(access_code).strip().upper()

        classe = request.env["joc.lector.classe"].sudo().search([
            ("access_code", "=", access_code),
            ("active", "=", True),
        ], limit=1)

        if not classe:
            return self._error("No s'ha trobat cap classe activa amb eixe codi.", status=404, code="class_not_found")

        passaport_abans = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id)
        ], limit=1)

        if alumne.current_classe_id and alumne.current_classe_id.id == classe.id:
            return self._json_response({
                "ok": True,
                "message": "L'alumne ja està en esta classe.",
                "migrated": False,
                "alumne": self._serialize_alumne(alumne),
                "classe": self._serialize_classe(classe),
                "passaport": self._serialize_passaport(passaport_abans),
            })

        try:
            matricula = request.env["joc.lector.matricula"].sudo().create({
                "alumne_id": alumne.id,
                "classe_id": classe.id,
            })
        except ValidationError as exc:
            return self._error(str(exc), status=409, code="class_ratio_too_large")

        passaport_despres = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id)
        ], limit=1)

        return self._json_response({
            "ok": True,
            "message": "Alumne incorporat a la nova classe conservant el passaport lector.",
            "migrated": True,
            "alumne": self._serialize_alumne(alumne),
            "classe": self._serialize_classe(classe),
            "matricula": {
                "id": matricula.id,
                "state": matricula.state,
                "date_start": matricula.date_start,
                "date_end": matricula.date_end,
            },
            "passaport": self._serialize_passaport(passaport_despres),
            "passaport_conservat": bool(passaport_abans and passaport_despres and passaport_abans.id == passaport_despres.id),
        })

    def _get_bearer_token(self):
        auth_header = request.httprequest.headers.get("Authorization") or ""
        auth_header = auth_header.strip()

        if not auth_header.lower().startswith("bearer "):
            return None

        return auth_header.split(" ", 1)[1].strip()

    def _find_alumne_by_token(self):
        raw_token = self._get_bearer_token()
        if not raw_token:
            return None, None, None

        alumne, token = request.env["joc.lector.auth.token"].sudo().authenticate_raw_token(raw_token)

        if not alumne:
            return None, None, self._error(
                "Token invàlid o caducat.",
                status=401,
                code="invalid_token",
            )

        return alumne, token, None

    def _find_alumne_by_app_uid(self):
        """Busca l'alumne.

        Prioritat:
        1. Authorization: Bearer <token>
        2. app_uid com a mecanisme provisional de transició
        """
        alumne, token, error = self._find_alumne_by_token()
        if error:
            return None, error

        if alumne:
            return alumne, None

        app_uid = self._param("app_uid")
        if not app_uid:
            return None, self._error(
                "Falta autenticació. Usa Authorization: Bearer <token> o app_uid provisional.",
                status=401,
                code="missing_auth",
            )

        alumne = request.env["joc.lector.alumne"].sudo().search([
            ("app_uid", "=", app_uid),
            ("active", "=", True),
        ], limit=1)

        if not alumne:
            return None, self._error(
                "No s'ha trobat cap alumne amb eixe app_uid.",
                status=404,
                code="student_not_found",
            )

        return alumne, None

    def _serialize_classe(self, classe, include_access_code=False):
        if not classe:
            return None

        data = {
            "id": classe.id,
            "name": classe.name,
            "curs_academic": classe.curs_academic,
            "centre": {
                "id": classe.centre_id.id,
                "name": classe.centre_id.name,
                "code": classe.centre_id.code,
            } if classe.centre_id else None,
        }

        if include_access_code:
            data["access_code"] = classe.access_code

        return data

    def _serialize_alumne(self, alumne, include_app_uid=False):
        data = {
            "id": alumne.id,
            "name": alumne.name,
            "codi_alumne": alumne.codi_alumne,
            "current_classe": self._serialize_classe(alumne.current_classe_id),
        }

        if include_app_uid:
            data["app_uid"] = alumne.app_uid

        return data

    def _serialize_token(self, raw_token, token):
        return {
            "access_token": raw_token,
            "token_type": "Bearer",
            "expires_at": token.date_expires,
            "device_name": token.device_name,
            "hint": token.token_hint,
        }

    @http.route(
        "/api/joc/auth/login",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def auth_login(self, **kwargs):
        app_uid = self._param("app_uid")
        if not app_uid:
            return self._error(
                "Falta app_uid per iniciar sessió.",
                status=400,
                code="missing_app_uid",
            )

        alumne = request.env["joc.lector.alumne"].sudo().search([
            ("app_uid", "=", app_uid),
            ("active", "=", True),
        ], limit=1)

        if not alumne:
            return self._error(
                "No s'ha trobat cap alumne amb eixe app_uid.",
                status=404,
                code="student_not_found",
            )

        device_name = self._param("device_name", "Dispositiu")
        raw_token, token = request.env["joc.lector.auth.token"].sudo().create_for_alumne(
            alumne,
            device_name=device_name,
        )

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], limit=1)

        return self._json_response({
            "ok": True,
            "message": "Sessió iniciada correctament.",
            "alumne": self._serialize_alumne(alumne),
            "passaport": self._serialize_passaport(passaport),
            "token": self._serialize_token(raw_token, token),
        })

    @http.route(
        "/api/joc/auth/logout",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def auth_logout(self, **kwargs):
        alumne, token, error = self._find_alumne_by_token()
        if error:
            return error

        if not token:
            return self._error(
                "Falta Authorization: Bearer <token>.",
                status=401,
                code="missing_token",
            )

        token.sudo().write({"active": False})

        return self._json_response({
            "ok": True,
            "message": "Sessió tancada correctament.",
        })

    @http.route(
        "/api/joc/alumne/crear",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def alumne_crear(self, **kwargs):
        name = self._param("name")
        access_code = self._param("access_code")
        device_name = self._param("device_name", "Dispositiu")

        if not name or not str(name).strip():
            return self._error(
                "El nom visible de l'alumne és obligatori.",
                status=400,
                code="missing_student_name",
            )

        if not access_code or not str(access_code).strip():
            return self._error(
                "El codi de classe és obligatori.",
                status=400,
                code="missing_access_code",
            )

        name = str(name).strip()
        access_code = str(access_code).strip().upper()

        if len(name) < 2:
            return self._error(
                "El nom visible ha de tindre almenys 2 caràcters.",
                status=400,
                code="invalid_student_name",
            )

        if len(name) > 80:
            return self._error(
                "El nom visible és massa llarg.",
                status=400,
                code="student_name_too_long",
            )

        classe = request.env["joc.lector.classe"].sudo().search([
            ("access_code", "=", access_code),
            ("active", "=", True),
        ], limit=1)

        if not classe:
            return self._error(
                "No s'ha trobat cap classe activa amb eixe codi.",
                status=404,
                code="class_not_found",
            )

        alumne = request.env["joc.lector.alumne"].sudo().create({
            "name": name,
        })

        try:
            matricula = request.env["joc.lector.matricula"].sudo().create({
                "alumne_id": alumne.id,
                "classe_id": classe.id,
            })
        except ValidationError as exc:
            alumne.unlink()
            return self._error(str(exc), status=409, code="class_ratio_too_large")

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], limit=1)

        raw_token, token = request.env["joc.lector.auth.token"].sudo().create_for_alumne(
            alumne,
            device_name=device_name,
        )

        return self._json_response({
            "ok": True,
            "message": "Alumne creat correctament.",
            "alumne": self._serialize_alumne(alumne),
            "classe": self._serialize_classe(classe),
            "matricula": {
                "id": matricula.id,
                "state": matricula.state,
                "date_start": matricula.date_start,
                "date_end": matricula.date_end,
            },
            "passaport": self._serialize_passaport(passaport),
            "token": self._serialize_token(raw_token, token),
        }, status=201)

    def _is_recovery_debug_enabled(self):
        value = request.env["ir.config_parameter"].sudo().get_param(
            "joc_lector.recovery_debug",
            default="0",
        )
        return str(value).strip().lower() in ("1", "true", "yes", "si", "sí", "on")

    def _send_recovery_email(self, email_to, alumne, classe, raw_code):
        subject = "Codi de recuperació del Joc Lector"

        body_html = f"""
        <p>Hola,</p>
        <p>Has sol·licitat recuperar l'accés al <strong>Joc Lector</strong>.</p>
        <p>El teu codi de recuperació és:</p>
        <h2 style="letter-spacing: 4px;">{raw_code}</h2>
        <p>Este codi caduca en 15 minuts.</p>
        <p>Perfil: <strong>{alumne.name}</strong></p>
        <p>Classe: <strong>{classe.name}</strong> — {classe.curs_academic}</p>
        <p>Si no ho has demanat tu, pots ignorar este missatge.</p>
        """

        mail = request.env["mail.mail"].sudo().create({
            "subject": subject,
            "email_from": JOC_LECTOR_EMAIL_FROM,
            "email_to": email_to,
            "body_html": body_html,
            "auto_delete": True,
        })

        mail.sudo().send()

        return True

    @http.route(
        "/api/joc/recuperacio/solicitar",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def recuperacio_solicitar(self, **kwargs):
        name = self._param("name")
        access_code = self._param("access_code")
        email = self._param("email")
        device_name = self._param("device_name", "Dispositiu recuperació")

        if not name or not str(name).strip():
            return self._error(
                "Cal indicar el nom visible de l'alumne.",
                status=400,
                code="missing_student_name",
            )

        if not access_code or not str(access_code).strip():
            return self._error(
                "Cal indicar el codi de classe.",
                status=400,
                code="missing_access_code",
            )

        if not email or not str(email).strip():
            return self._error(
                "Cal indicar un email temporal per rebre el codi.",
                status=400,
                code="missing_email",
            )

        name = str(name).strip()
        access_code = str(access_code).strip().upper()
        email = str(email).strip()

        if "@" not in email or "." not in email:
            return self._error(
                "L'email no sembla vàlid.",
                status=400,
                code="invalid_email",
            )

        classe = request.env["joc.lector.classe"].sudo().search([
            ("access_code", "=", access_code),
            ("active", "=", True),
        ], limit=1)

        if not classe:
            return self._error(
                "No s'ha trobat cap classe activa amb eixe codi.",
                status=404,
                code="class_not_found",
            )

        alumnes = request.env["joc.lector.alumne"].sudo().search([
            ("name", "=ilike", name),
            ("current_classe_id", "=", classe.id),
            ("active", "=", True),
        ])

        if not alumnes:
            return self._error(
                "No s'ha trobat cap alumne actiu amb eixe nom en eixa classe.",
                status=404,
                code="student_not_found",
            )

        if len(alumnes) > 1:
            return self._error(
                "Hi ha més d'un alumne amb eixe nom en la classe. Cal que el professor revise els perfils.",
                status=409,
                code="ambiguous_student",
            )

        alumne = alumnes[0]

        raw_code, recovery = request.env["joc.lector.recovery.code"].sudo().create_for_alumne(
            alumne,
            device_name=device_name,
            minutes=15,
        )

        try:
            self._send_recovery_email(email, alumne, classe, raw_code)
        except Exception:
            return self._error(
                "No s'ha pogut enviar el correu de recuperació. Revisa la configuració de correu d'Odoo.",
                status=500,
                code="email_send_failed",
            )

        response = {
            "ok": True,
            "message": "S'ha enviat un codi de recuperació a l'email indicat.",
            "recovery_id": recovery.id,
            "expires_at": recovery.date_expires,
            "code_hint": recovery.code_hint,
        }

        if self._is_recovery_debug_enabled():
            response["debug_code"] = raw_code

        return self._json_response(response)

    @http.route(
        "/api/joc/recuperacio/validar",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def recuperacio_validar(self, **kwargs):
        recovery_id = self._get_int_param("recovery_id")
        code = self._param("code")
        device_name = self._param("device_name", "Dispositiu recuperat")

        if not recovery_id:
            return self._error(
                "Cal indicar recovery_id.",
                status=400,
                code="missing_recovery_id",
            )

        if not code or not str(code).strip():
            return self._error(
                "Cal indicar el codi de recuperació.",
                status=400,
                code="missing_code",
            )

        recovery = request.env["joc.lector.recovery.code"].sudo().search([
            ("id", "=", recovery_id),
        ], limit=1)

        if not recovery:
            return self._error(
                "No s'ha trobat la sol·licitud de recuperació.",
                status=404,
                code="recovery_not_found",
            )

        valid, reason = recovery.validate_code(code)

        if not valid:
            messages = {
                "used_or_inactive": "El codi ja s'ha utilitzat o està inactiu.",
                "expired": "El codi ha caducat.",
                "too_many_attempts": "S'han superat els intents permesos.",
                "invalid_code": "El codi no és correcte.",
            }

            return self._error(
                messages.get(reason, "El codi no és vàlid."),
                status=400,
                code=reason,
            )

        alumne = recovery.alumne_id

        raw_token, token = request.env["joc.lector.auth.token"].sudo().create_for_alumne(
            alumne,
            device_name=device_name,
        )

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], limit=1)

        return self._json_response({
            "ok": True,
            "message": "Accés recuperat correctament.",
            "alumne": self._serialize_alumne(alumne),
            "passaport": self._serialize_passaport(passaport),
            "token": self._serialize_token(raw_token, token),
        })
