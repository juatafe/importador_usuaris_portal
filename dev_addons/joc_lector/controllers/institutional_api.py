# -*- coding: utf-8 -*-

import json
import logging
from urllib.parse import urlencode

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import Response, request


MANUAL_REGISTRATION_MESSAGE = "Este centre no es pot donar d’alta automàticament. Escriu a joc-lector@provestalens.es per a sol·licitar l’alta manual."
JOC_LECTOR_EMAIL_FROM = "Joc Lector <joc-lector@provestalens.es>"
_logger = logging.getLogger(__name__)


class JocLectorInstitutionalApiController(http.Controller):
    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False, default=str),
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def _error(self, code, message, status=400, extra=None):
        payload = {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
        }
        if extra:
            payload.update(extra)
        return self._json(payload, status=status)

    def _payload(self):
        if request.httprequest.method == "GET":
            return {}
        raw = request.httprequest.data or b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _param(self, name, default=None):
        body = self._payload()
        return request.params.get(name) or body.get(name) or default

    def _param_raw(self, name, default=None):
        body = self._payload()
        if name in request.params:
            return request.params.get(name)
        if name in body:
            return body.get(name)
        return default

    def _normalize_email(self, value):
        if not value:
            return False
        return str(value).strip().lower()

    def _centre_code_from_email(self, email):
        email = self._normalize_email(email)
        if not email or "@" not in email:
            return False
        local_part = email.split("@", 1)[0].strip()
        return local_part if local_part.isdigit() else False

    def _text_or_none(self, value):
        if value is None or value is False or isinstance(value, bool):
            return None
        text = str(value).strip()
        return text if text else None

    def _as_bool(self, value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")
        return bool(value)

    def _has_param(self, name):
        body = self._payload()
        return name in request.params or name in body

    def _find_centre_from_params(self):
        Centre = request.env["joc.lector.centre"].sudo()
        centre = False

        centre_id = self._param("centre_id") or self._param("centreId")
        if centre_id:
            try:
                centre = Centre.search([("id", "=", int(centre_id)), ("active", "=", True)], limit=1)
            except Exception:
                centre = False

        if not centre:
            codi_centre = (self._param("codi_centre") or self._param("codiCentre") or "").strip()
            if codi_centre:
                centre = Centre.search([
                    ("active", "=", True),
                    "|",
                    ("codi_centre", "=", codi_centre),
                    ("code", "=", codi_centre),
                ], limit=1)

        if not centre:
            email = self._normalize_email(
                self._param("email_centre")
                or self._param("emailCentre")
                or self._param("email_oficial")
                or self._param("official_email")
            )
            if email:
                centre = Centre.search([("email_oficial", "=", email), ("active", "=", True)], limit=1)

        return centre

    def _base_url(self):
        return request.env["ir.config_parameter"].sudo().get_param("web.base.url", "")

    def _app_url(self, view, **params):
        query = {"view": view}
        query.update({key: value for key, value in params.items() if value not in (None, False, "")})
        return "%s/lectures/app/?%s" % (
            self._base_url().rstrip("/"),
            urlencode(query),
        )

    def _format_datetime_local(self, value):
        if not value:
            return ""
        local_dt = fields.Datetime.context_timestamp(
            request.env["res.users"].sudo().with_context(tz="Europe/Madrid").browse(request.env.uid),
            value,
        )
        return local_dt.strftime("%d/%m/%Y %H:%M")

    def _serialize_centre(self, centre):
        return {
            "id": centre.id,
            "name": centre.name,
            "codi_centre": self._text_or_none(centre.codi_centre),
            "municipi": self._text_or_none(centre.municipi),
            "email_oficial": self._text_or_none(centre.email_oficial),
            "official_email": self._text_or_none(centre.email_oficial),
            "tic_nom": self._text_or_none(centre.tic_nom),
            "nom_tic": self._text_or_none(centre.tic_nom),
            "nom_contacte_tic": self._text_or_none(centre.tic_nom),
            "persona_tic": self._text_or_none(centre.tic_nom),
            "tic_name": self._text_or_none(centre.tic_nom),
            "tic_email": self._text_or_none(centre.tic_email),
            "email_tic": self._text_or_none(centre.tic_email),
            "email_contacte_tic": self._text_or_none(centre.tic_email),
            "correu_tic": self._text_or_none(centre.tic_email),
            "contacte_tic_email": self._text_or_none(centre.tic_email),
            "ranking_public": centre.ranking_public,
            "ranking_public_actiu": centre.ranking_public,
            "ranquingPublicActiu": centre.ranking_public,
            "web_publica_activa": centre.web_publica_activa,
            "estat": centre.estat,
            "admin_verified": centre.admin_verified,
        }

    def _serialize_solicitud(self, solicitud):
        return {
            "id": solicitud.id,
            "centre_id": solicitud.centre_id.id,
            "centre_name": solicitud.centre_id.name,
            "professor_nom": solicitud.professor_nom,
            "professor_email": solicitud.professor_email,
            "municipi": self._text_or_none(solicitud.municipi),
            "estat": solicitud.estat,
            "create_date": solicitud.create_date,
            "token_expires": solicitud.token_expires,
            "motiu_rebuig": self._text_or_none(solicitud.motiu_rebuig),
        }

    def _serialize_professor(self, professor):
        return {
            "id": professor.id,
            "name": professor.name,
            "email": self._text_or_none(professor.user_id.login or professor.user_id.email),
            "user_id": professor.user_id.id,
            "centre_id": professor.centre_id.id,
            "rol": professor.rol,
            "active": professor.active,
            "classe_ids": professor.classe_ids.ids,
        }

    def _serialize_invitation(self, invitation):
        invitation.expire_if_needed()
        return {
            "id": invitation.id,
            "centre_id": invitation.centre_id.id,
            "email": invitation.email,
            "name": self._text_or_none(invitation.name),
            "state": invitation.state,
            "expires_at": invitation.expires_at,
            "created_by": invitation.created_by.id if invitation.created_by else None,
            "accepted_user_id": invitation.accepted_user_id.id if invitation.accepted_user_id else None,
            "professor_id": invitation.professor_id.id if invitation.professor_id else None,
        }

    def _centre_public_stats(self, centre):
        Lectura = request.env["joc.lector.lectura"].sudo()
        domain = [
            ("centre_id", "=", centre.id),
            ("estat_validacio", "=", "acceptada"),
        ]
        return {
            "lectures_validades": Lectura.search_count(domain),
            "llibres_acabats": Lectura.search_count(domain + [("state", "=", "finished")]),
            "ressenyes_publiques": Lectura.search_count(domain + [
                ("visible_publicament", "=", True),
                ("ressenya", "!=", False),
            ]),
        }

    def _admin_snapshot(self, centre):
        Professor = request.env["joc.lector.professor"].sudo()
        Solicitud = request.env["joc.lector.professor.solicitud"].sudo()
        Invitation = request.env["joc.lector.professor.invitation"].sudo()

        professors = Professor.search([("centre_id", "=", centre.id), ("active", "=", True)], order="name asc")
        pendents = Solicitud.search([("centre_id", "=", centre.id), ("estat", "=", "pendent")], order="create_date desc")
        invitations = Invitation.search([("centre_id", "=", centre.id), ("state", "=", "pendent")], order="create_date desc")
        invitations.expire_if_needed()
        invitations = invitations.filtered(lambda inv: inv.state == "pendent")

        centre_data = self._serialize_centre(centre)
        data = {
            "ok": True,
            "centre": centre_data,
            "configuracio": {
                "ranking_public": centre.ranking_public,
                "ranking_public_actiu": centre.ranking_public,
                "ranquingPublicActiu": centre.ranking_public,
                "web_publica_activa": centre.web_publica_activa,
            },
            "estadistiques_publiques": self._centre_public_stats(centre),
            "professorat": [self._serialize_professor(p) for p in professors],
            "solicituds_pendents": [self._serialize_solicitud(s) for s in pendents],
            "invitacions_pendents": [self._serialize_invitation(i) for i in invitations],
        }
        data["data"] = {
            "centre": centre_data,
            "configuracio": data["configuracio"],
            "estadistiques_publiques": data["estadistiques_publiques"],
            "professorat": data["professorat"],
            "solicituds_pendents": data["solicituds_pendents"],
            "invitacions_pendents": data["invitacions_pendents"],
        }
        return data

    def _admin_bearer_token(self):
        auth_header = (request.httprequest.headers.get("Authorization") or "").strip()
        if not auth_header.lower().startswith("bearer "):
            return None
        return auth_header.split(" ", 1)[1].strip()

    def _centre_by_admin_token(self):
        raw_token = self._admin_bearer_token()
        if not raw_token:
            return False, False
        return request.env["joc.lector.centre.admin.token"].sudo().authenticate_raw_token(raw_token)

    def _authenticate_admin(self):
        centre, _token = self._centre_by_admin_token()
        if centre:
            if centre.is_login_blocked():
                return None, self._error(
                    "centre_admin_blocked",
                    "L'acces d'administracio del centre esta temporalment bloquejat.",
                    status=429,
                )
            return centre, None
        return None, self._error(
            "missing_admin_token",
            "Cal Authorization: Bearer <token_admin_centre>.",
            status=401,
        )

    def _authenticate_admin_with_code(self, email_oficial, admin_code):
        if not email_oficial or not admin_code:
            return None, self._error(
                "missing_credentials",
                "Cal indicar email_oficial i codi_admin.",
                status=400,
            )

        centre = request.env["joc.lector.centre"].sudo().search([
            ("email_oficial", "=", self._normalize_email(email_oficial)),
            ("active", "=", True),
        ], limit=1)

        if not centre:
            return None, self._error(
                "centre_not_found",
                "No s'ha trobat cap centre amb eixe correu oficial.",
                status=404,
            )

        if centre.is_login_blocked():
            return None, self._error(
                "centre_admin_blocked",
                "L'acces d'administracio del centre esta temporalment bloquejat.",
                status=429,
                extra={"blocked_until": centre.admin_login_blocked_until},
            )

        if not centre.check_admin_code(admin_code):
            centre.consume_login_attempt(False)
            return None, self._error(
                "invalid_admin_code",
                "Credencials d'administracio incorrectes.",
                status=401,
            )

        centre.consume_login_attempt(True)
        centre.write({"admin_verified": True})
        return centre, None

    def _send_template(self, xmlid, record, ctx=None, email_to=None, subject=None):
        template = request.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.error("Mail template not found: %s", xmlid)
            return False

        template = template.sudo().with_context(**(ctx or {}))
        email_values = {}
        email_values["email_from"] = JOC_LECTOR_EMAIL_FROM
        if email_to:
            email_values["email_to"] = email_to
        if subject:
            email_values["subject"] = subject

        mail_id = template.send_mail(record.id, force_send=True, email_values=email_values)
        _logger.info(
            "Sent mail template %s for %s(%s) to %s mail_id=%s",
            xmlid,
            record._name,
            record.id,
            email_to or template.email_to,
            mail_id,
        )
        return mail_id or True

    @http.route("/joc_lector/api/centre/registrar", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_registrar(self, **kwargs):
        name = (self._param("name") or self._param("nom_centre") or "").strip()
        email_oficial = self._normalize_email(self._param("email_oficial"))
        municipi = (self._param("municipi") or "").strip()
        tic_nom = (
            self._param("tic_nom")
            or self._param("nom_tic")
            or self._param("nom_contacte_tic")
            or self._param("persona_tic")
            or self._param("tic_name")
            or ""
        ).strip()
        tic_email = self._normalize_email(
            self._param("tic_email")
            or self._param("email_tic")
            or self._param("email_contacte_tic")
            or self._param("correu_tic")
            or self._param("contacte_tic_email")
        )

        if not name or not email_oficial:
            return self._error(
                "missing_params",
                "Cal indicar nom del centre i email_oficial.",
                status=400,
            )

        Centre = request.env["joc.lector.centre"].sudo()

        if not Centre._is_valid_official_email(email_oficial):
            return self._error(
                "invalid_official_email",
                MANUAL_REGISTRATION_MESSAGE,
                status=400,
            )

        centre_existing = Centre.search([("email_oficial", "=", email_oficial)], limit=1)
        if centre_existing:
            self._send_template(
                "joc_lector.mail_template_joc_lector_centre_duplicate_attempt",
                centre_existing,
                ctx={"duplicate_request_name": name},
                email_to=email_oficial,
            )
            return self._error(
                "centre_already_registered",
                "El centre ja esta registrat. Contacta amb la persona TIC de referencia.",
                status=409,
                extra={
                    "centre": self._serialize_centre(centre_existing),
                    "tic_email": self._text_or_none(centre_existing.tic_email),
                },
            )

        centre = Centre.create({
            "name": name,
            "code": self._centre_code_from_email(email_oficial),
            "email_oficial": email_oficial,
            "municipi": municipi or False,
            "tic_nom": tic_nom or False,
            "tic_email": tic_email or False,
            "estat": "actiu",
            "ranking_public": False,
        })

        raw_code = centre.set_new_admin_code()
        self._send_template(
            "joc_lector.mail_template_joc_lector_centre_admin_code_created",
            centre,
            ctx={"admin_code": raw_code},
            email_to=centre.email_oficial,
        )

        return self._json({
            "ok": True,
            "message": "Centre registrat correctament. S'ha enviat el codi d'administracio al correu oficial.",
            "centre": self._serialize_centre(centre),
        }, status=201)

    @http.route("/joc_lector/api/centre/admin/login", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_login(self, **kwargs):
        email_oficial = self._param("email_oficial")
        admin_code = self._param("codi_admin") or self._param("admin_code")

        centre, error = self._authenticate_admin_with_code(email_oficial, admin_code)
        if error:
            return error

        raw_token, token = request.env["joc.lector.centre.admin.token"].sudo().create_for_centre(centre)

        return self._json({
            "ok": True,
            "message": "Sessio d'administracio de centre iniciada.",
            "centre": self._serialize_centre(centre),
            "token": {
                "access_token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.date_expires,
            },
        })

    @http.route("/joc_lector/api/centre/admin/validar_codi", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_validar_codi(self, **kwargs):
        centre = self._find_centre_from_params()
        admin_code = self._param("admin_code") or self._param("codi_admin")
        email_centre = self._normalize_email(self._param("email_centre") or self._param("emailCentre"))

        if not centre:
            return self._error("centre_not_found", "No s'ha trobat el centre.", status=404)

        if email_centre and centre.email_oficial != email_centre:
            return self._error("invalid_admin_code", "Credencials d'administracio incorrectes.", status=401)

        if centre.is_login_blocked():
            return self._error(
                "centre_admin_blocked",
                "L'acces d'administracio del centre esta temporalment bloquejat.",
                status=429,
                extra={"blocked_until": centre.admin_login_blocked_until},
            )

        if not centre.check_admin_code(admin_code):
            centre.consume_login_attempt(False)
            return self._error("invalid_admin_code", "Credencials d'administracio incorrectes.", status=401)

        centre.consume_login_attempt(True)
        centre.write({"admin_verified": True})
        raw_token, token = request.env["joc.lector.centre.admin.token"].sudo().create_for_centre(centre)

        return self._json({
            "ok": True,
            "admin_token": {
                "access_token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.date_expires,
            },
            "token": {
                "access_token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.date_expires,
            },
            "centre": self._serialize_centre(centre),
        })

    @http.route("/joc_lector/api/centre/admin/reenviar_codi", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_reenviar_codi(self, **kwargs):
        centre = None

        centre_token, _token = self._centre_by_admin_token()
        if centre_token:
            centre = centre_token

        if not centre:
            centre = self._find_centre_from_params()
            email_centre = self._normalize_email(self._param("email_centre") or self._param("emailCentre"))
            if not centre or (email_centre and centre.email_oficial != email_centre):
                return self._json({
                    "ok": True,
                    "message": "Si les dades corresponen a un centre registrat, s'enviara un nou codi al correu oficial.",
                })

        raw_code = centre.set_new_admin_code()
        self._send_template(
            "joc_lector.mail_template_joc_lector_admin_code_regenerated",
            centre,
            ctx={"admin_code": raw_code},
            email_to=centre.email_oficial,
        )

        return self._json({
            "ok": True,
            "message": "Codi d'administracio regenerat i enviat al correu oficial del centre.",
            "centre": self._serialize_centre(centre),
        })

    @http.route([
        "/joc_lector/api/centre/admin/snapshot",
        "/joc_lector/api/centre/admin/dades",
    ], type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def centre_admin_snapshot(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error
        return self._json(self._admin_snapshot(centre))

    @http.route("/joc_lector/api/centre/admin/actualitzar", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_actualitzar(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        vals = {}
        if self._has_param("name") or self._has_param("nom_centre"):
            vals["name"] = (self._param("name") or self._param("nom_centre") or "").strip() or centre.name

        official_email = (
            self._param("email_oficial")
            or self._param("official_email")
            or self._param("correu_oficial")
        )
        official_email_changed = False
        if (
            self._has_param("email_oficial")
            or self._has_param("official_email")
            or self._has_param("correu_oficial")
        ):
            official_email = self._normalize_email(official_email)
            Centre = request.env["joc.lector.centre"].sudo()
            if not Centre._is_valid_official_email(official_email):
                return self._error(
                    "invalid_official_email",
                    MANUAL_REGISTRATION_MESSAGE,
                    status=400,
                )

            duplicate = Centre.search([
                ("id", "!=", centre.id),
                ("email_oficial", "=", official_email),
                ("active", "=", True),
            ], limit=1)
            if duplicate:
                return self._error(
                    "official_email_already_used",
                    "Ja existix un centre actiu amb este correu oficial.",
                    status=409,
                )

            if centre.email_oficial != official_email:
                vals["email_oficial"] = official_email
                vals["code"] = self._centre_code_from_email(official_email)
                vals["admin_verified"] = False
                official_email_changed = True

        if self._has_param("municipi"):
            vals["municipi"] = (self._param("municipi") or "").strip() or False

        persona_tic = (
            self._param("persona_tic")
            or self._param("tic_nom")
            or self._param("nom_tic")
            or self._param("nom_contacte_tic")
            or self._param("tic_name")
        )
        if (
            self._has_param("persona_tic")
            or self._has_param("tic_nom")
            or self._has_param("nom_tic")
            or self._has_param("nom_contacte_tic")
            or self._has_param("tic_name")
        ):
            vals["tic_nom"] = str(persona_tic or "").strip() or False

        email_tic = (
            self._param("email_tic")
            or self._param("tic_email")
            or self._param("email_contacte_tic")
            or self._param("correu_tic")
            or self._param("contacte_tic_email")
        )
        if (
            self._has_param("email_tic")
            or self._has_param("tic_email")
            or self._has_param("email_contacte_tic")
            or self._has_param("correu_tic")
            or self._has_param("contacte_tic_email")
        ):
            vals["tic_email"] = self._normalize_email(email_tic)

        if vals:
            centre.write(vals)

        admin_code_resent = False
        admin_tokens_revoked = False
        if official_email_changed:
            raw_code = centre.set_new_admin_code()
            self._send_template(
                "joc_lector.mail_template_joc_lector_admin_code_regenerated",
                centre,
                ctx={"admin_code": raw_code},
                email_to=centre.email_oficial,
            )
            request.env["joc.lector.centre.admin.token"].sudo().search([
                ("centre_id", "=", centre.id),
                ("active", "=", True),
            ]).write({"active": False})
            admin_code_resent = True
            admin_tokens_revoked = True

        payload = {
            "ok": True,
            "message": "Dades del centre actualitzades.",
            "centre": self._serialize_centre(centre),
        }
        if official_email_changed:
            payload.update({
                "message": "Dades del centre actualitzades. S'ha enviat un nou codi d'administracio al correu oficial i s'han revocat les sessions admin anteriors.",
                "admin_code_resent": admin_code_resent,
                "admin_tokens_revoked": admin_tokens_revoked,
            })
        return self._json(payload)

    @http.route("/joc_lector/api/centre/admin/configuracio", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_configuracio(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        vals = {}
        if self._has_param("ranking_public"):
            vals["ranking_public"] = self._as_bool(self._param_raw("ranking_public"), centre.ranking_public)
        if self._has_param("ranquingPublicActiu"):
            vals["ranking_public"] = self._as_bool(self._param_raw("ranquingPublicActiu"), centre.ranking_public)
        if self._has_param("web_publica_activa"):
            vals["web_publica_activa"] = self._as_bool(self._param_raw("web_publica_activa"), centre.web_publica_activa)

        if vals:
            centre.write(vals)

        return self._json({
            "ok": True,
            "message": "Configuracio de centre actualitzada.",
            "centre": self._serialize_centre(centre),
            "configuracio": {
                "ranking_public": centre.ranking_public,
                "ranking_public_actiu": centre.ranking_public,
                "ranquingPublicActiu": centre.ranking_public,
                "web_publica_activa": centre.web_publica_activa,
            },
        })

    @http.route("/joc_lector/api/centres/buscar", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def centres_buscar(self, **kwargs):
        q = (self._param("q") or self._param("query") or "").strip()
        limit = int(self._param("limit") or 20)
        limit = max(1, min(limit, 100))

        domain = [("active", "=", True)]
        if q:
            domain += ["|", "|", ("name", "ilike", q), ("email_oficial", "ilike", q), ("municipi", "ilike", q)]

        centres = request.env["joc.lector.centre"].sudo().search(domain, order="name asc", limit=limit)

        return self._json({
            "ok": True,
            "count": len(centres),
            "centres": [self._serialize_centre(centre) for centre in centres],
        })

    @http.route([
        "/joc_lector/api/professor/solicitar_acces",
        "/joc_lector/api/professor/solicitar_centre",
    ], type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_solicitar_acces(self, **kwargs):
        professor_nom = (self._param("professor_nom") or self._param("name") or "").strip()
        professor_email = self._normalize_email(self._param("professor_email") or self._param("email"))
        municipi = (self._param("municipi") or "").strip()
        notes = (self._param("notes") or self._param("justificacio") or "").strip()

        if not professor_nom or not professor_email:
            return self._error(
                "missing_professor_data",
                "Cal indicar nom i email professional del professorat.",
                status=400,
            )

        Centre = request.env["joc.lector.centre"].sudo()

        centre = False
        centre_id = int(self._param("centre_id") or 0)
        if centre_id:
            centre = Centre.search([("id", "=", centre_id), ("active", "=", True)], limit=1)

        if not centre:
            codi_centre = (self._param("codi_centre") or self._param("codiCentre") or "").strip()
            if codi_centre:
                centre = Centre.search([
                    ("active", "=", True),
                    "|",
                    ("codi_centre", "=", codi_centre),
                    ("code", "=", codi_centre),
                ], limit=1)

        if not centre:
            email_oficial = self._normalize_email(self._param("email_oficial") or self._param("centre_email_oficial"))
            centre_name = (self._param("centre_name") or self._param("nom_centre") or "").strip()

            if email_oficial:
                centre = Centre.search([("email_oficial", "=", email_oficial)], limit=1)

            if not centre and (centre_name or email_oficial):
                if not email_oficial or not Centre._is_valid_official_email(email_oficial):
                    return self._error(
                        "invalid_official_email",
                        MANUAL_REGISTRATION_MESSAGE,
                        status=400,
                    )

                centre = Centre.create({
                    "name": centre_name or email_oficial,
                    "code": self._centre_code_from_email(email_oficial),
                    "email_oficial": email_oficial,
                    "municipi": municipi or False,
                    "estat": "actiu",
                })
                raw_code = centre.set_new_admin_code()
                self._send_template(
                    "joc_lector.mail_template_joc_lector_centre_admin_code_created",
                    centre,
                    ctx={"admin_code": raw_code},
                    email_to=centre.email_oficial,
                )

        if not centre:
            return self._error(
                "centre_not_found",
                "No s'ha trobat cap centre i no s'han aportat dades suficients per registrar-lo.",
                status=404,
            )

        if not centre.email_oficial:
            return self._error(
                "missing_centre_official_email",
                "El centre no te correu oficial configurat. No es pot enviar la sol.licitud d'acces.",
                status=400,
            )

        pending_template = request.env.ref(
            "joc_lector.mail_template_joc_lector_professor_pending",
            raise_if_not_found=False,
        )
        if not pending_template:
            return self._error(
                "missing_mail_template",
                "No existeix la plantilla joc_lector.mail_template_joc_lector_professor_pending.",
                status=500,
            )

        Solicitud = request.env["joc.lector.professor.solicitud"].sudo()
        primary_email = centre.tic_email or centre.email_oficial
        mail_info = {
            "template": "joc_lector.mail_template_joc_lector_professor_pending",
            "primary_to": primary_email,
            "primary_sent": False,
            "courtesy_to": centre.email_oficial if centre.email_oficial != primary_email else None,
            "courtesy_sent": False,
        }

        try:
            with request.env.cr.savepoint():
                solicitud = Solicitud.create({
                    "centre_id": centre.id,
                    "professor_nom": professor_nom,
                    "professor_email": professor_email,
                    "municipi": municipi or False,
                    "notes": notes or False,
                    "estat": "pendent",
                })

                accept_token, reject_token, expires = solicitud.generate_action_tokens(hours=72)
                accept_url = self._app_url(
                    "professor_solicitud",
                    action="acceptar",
                    token=accept_token,
                )
                reject_url = self._app_url(
                    "professor_solicitud",
                    action="rebutjar",
                    token=reject_token,
                )

                template_ctx = {
                    "accept_url": accept_url,
                    "reject_url": reject_url,
                    "token_expires": expires,
                }

                mail_info["primary_mail_id"] = self._send_template(
                    "joc_lector.mail_template_joc_lector_professor_pending",
                    solicitud,
                    ctx=template_ctx,
                    email_to=primary_email,
                    subject="Joc Lector: accio requerida - nova sollicitud de professorat",
                )
                mail_info["primary_sent"] = bool(mail_info["primary_mail_id"])

                if centre.email_oficial and centre.email_oficial != primary_email:
                    courtesy_ctx = dict(template_ctx, courtesy_copy=True)
                    try:
                        mail_info["courtesy_mail_id"] = self._send_template(
                            "joc_lector.mail_template_joc_lector_professor_pending",
                            solicitud,
                            ctx=courtesy_ctx,
                            email_to=centre.email_oficial,
                            subject="Joc Lector: copia de cortesia - nova sollicitud de professorat",
                        )
                        mail_info["courtesy_sent"] = bool(mail_info["courtesy_mail_id"])
                    except Exception as exc:
                        mail_info["courtesy_error"] = str(exc)
                        _logger.exception(
                            "Could not send courtesy professor request email for solicitud %s to %s",
                            solicitud.id,
                            centre.email_oficial,
                        )
        except Exception as exc:
            _logger.exception(
                "Could not create/send professor access request for centre %s to %s",
                centre.id,
                primary_email,
            )
            return self._error(
                "mail_send_failed",
                "No s'ha pogut enviar la sol.licitud d'acces. Revisa SMTP, cua mail.mail i logs d'Odoo.",
                status=500,
                extra={"mail": dict(mail_info, error=str(exc))},
            )

        message = "Sol.licitud enviada. Queda pendent d'aprovacio del centre."
        if centre.tic_email:
            message = "Sol.licitud enviada al contacte TIC. El centre rep una copia de cortesia."

        return self._json({
            "ok": True,
            "message": message,
            "solicitud": self._serialize_solicitud(solicitud),
            "mail": mail_info,
        }, status=201)

    @http.route("/joc_lector/api/centre/admin/solicituds_pendents", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def centre_admin_solicituds_pendents(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        solicitudes = request.env["joc.lector.professor.solicitud"].sudo().search([
            ("centre_id", "=", centre.id),
            ("estat", "=", "pendent"),
        ], order="create_date desc", limit=200)

        return self._json({
            "ok": True,
            "count": len(solicitudes),
            "solicituds": [self._serialize_solicitud(s) for s in solicitudes],
        })

    @http.route("/joc_lector/api/centre/admin/convidar_professor", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_convidar_professor(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        email = self._normalize_email(self._param("email"))
        name = (self._param("name") or self._param("nom") or "").strip()
        if not email:
            return self._error("missing_email", "Cal indicar email del professorat.", status=400)

        Invitation = request.env["joc.lector.professor.invitation"].sudo()
        active_invitation = Invitation.search([
            ("centre_id", "=", centre.id),
            ("email", "=", email),
            ("state", "=", "pendent"),
        ], order="id desc", limit=1)
        if active_invitation:
            active_invitation.expire_if_needed()
            if active_invitation.state == "pendent":
                raw_token = active_invitation.refresh_token()
                if name:
                    active_invitation.write({"name": name})
                invite_url = self._app_url("professor_invitacio", token=raw_token)
                self._send_template(
                    "joc_lector.mail_template_joc_lector_professor_invitation",
                    active_invitation,
                    ctx={
                        "invite_url": invite_url,
                        "privacy_url": "%s/lectures/privacitat" % self._base_url(),
                        "invitation_expires_display": self._format_datetime_local(active_invitation.expires_at),
                    },
                    email_to=email,
                )
                return self._json({
                    "ok": True,
                    "message": "Ja hi havia una invitacio pendent per a este email. S'ha reenviat amb un enllac nou.",
                    "invitation": self._serialize_invitation(active_invitation),
                })

        raw_token, invitation = Invitation.create_invitation(
            centre,
            email,
            name=name,
            created_by=request.env.user if request.env.user and request.env.user.id else None,
        )
        invite_url = self._app_url("professor_invitacio", token=raw_token)
        self._send_template(
            "joc_lector.mail_template_joc_lector_professor_invitation",
            invitation,
            ctx={
                "invite_url": invite_url,
                "privacy_url": "%s/lectures/privacitat" % self._base_url(),
                "invitation_expires_display": self._format_datetime_local(invitation.expires_at),
            },
            email_to=email,
        )

        return self._json({
            "ok": True,
            "message": "Invitacio enviada al professorat.",
            "invitation": self._serialize_invitation(invitation),
        }, status=201)

    @http.route("/joc_lector/api/centre/admin/professorat/resoldre", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_professorat_resoldre(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        decisio = (self._param("decisio") or "").strip().lower()
        if decisio in ("acceptar", "acceptada", "accept"):
            decisio = "acceptar"
        elif decisio in ("rebutjar", "rebutjada", "reject"):
            decisio = "rebutjar"
        else:
            return self._error("invalid_decision", "Cal indicar decisio acceptar/rebutjar.", status=400)

        rol = (self._param("rol") or "professor").strip()
        if rol not in ("professor", "admin_centre"):
            rol = "professor"

        solicitud_id = int(self._param("solicitud_id") or self._param("solicitudId") or 0)
        professor_id = int(self._param("professor_id") or self._param("professorId") or 0)

        Solicitud = request.env["joc.lector.professor.solicitud"].sudo()
        solicitud = False
        if solicitud_id:
            solicitud = Solicitud.search([
                ("id", "=", solicitud_id),
                ("centre_id", "=", centre.id),
                ("estat", "=", "pendent"),
            ], limit=1)

        if solicitud:
            if decisio == "acceptar":
                try:
                    professor = solicitud.action_acceptar(centre, rol=rol)
                except ValidationError as exc:
                    return self._error("limit_exceeded", str(exc), status=409)
                self._send_template(
                    "joc_lector.mail_template_joc_lector_professor_accepted",
                    solicitud,
                    ctx={"centre_name": solicitud.centre_id.name},
                    email_to=solicitud.professor_email,
                )
                return self._json({
                    "ok": True,
                    "message": "Professorat acceptat correctament.",
                    "solicitud": self._serialize_solicitud(solicitud),
                    "professor": self._serialize_professor(professor),
                })

            reason = (self._param("motiu") or self._param("reason") or "").strip()
            solicitud.action_rebutjar(centre, reason=reason)
            self._send_template(
                "joc_lector.mail_template_joc_lector_professor_rejected",
                solicitud,
                ctx={"centre_name": solicitud.centre_id.name, "rejection_reason": reason},
                email_to=solicitud.professor_email,
            )
            return self._json({
                "ok": True,
                "message": "Sol.licitud rebutjada.",
                "solicitud": self._serialize_solicitud(solicitud),
            })

        if professor_id:
            professor = request.env["joc.lector.professor"].sudo().search([
                ("id", "=", professor_id),
                ("centre_id", "=", centre.id),
            ], limit=1)
            if not professor:
                return self._error("professor_not_found", "No s'ha trobat professorat del centre.", status=404)
            if decisio == "acceptar":
                professor.write({"active": True, "rol": rol})
            else:
                professor.write({"active": False})
            return self._json({
                "ok": True,
                "professor": self._serialize_professor(professor),
            })

        return self._error("solicitud_not_found", "Cal indicar solicitud_id o professor_id valid.", status=404)

    @http.route("/joc_lector/api/centre/admin/professorat", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def centre_admin_professorat(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        snapshot = self._admin_snapshot(centre)
        return self._json({
            "ok": True,
            "professorat": snapshot["professorat"],
            "pendents": snapshot["solicituds_pendents"],
            "invitacions_pendents": snapshot["invitacions_pendents"],
        })

    def _find_solicitud_for_action(self, action):
        Solicitud = request.env["joc.lector.professor.solicitud"].sudo()

        action_token = self._param("token") or self._param("action_token")
        solicitud_id = int(self._param("solicitud_id") or 0)

        if action_token:
            digest = Solicitud._hash_token(action_token)
            field_name = "token_accept_hash" if action == "acceptar" else "token_reject_hash"
            solicitud = Solicitud.search([(field_name, "=", digest)], limit=1)
            if not solicitud:
                return None, None, self._error(
                    "invalid_or_expired_token",
                    "Token invalid o caducat.",
                    status=401,
                )
            if solicitud.estat != "pendent" or solicitud.token_used:
                return solicitud, solicitud.centre_id, None
            if not solicitud.match_token(action, action_token):
                if solicitud.estat != "pendent":
                    return solicitud, solicitud.centre_id, None
                return None, None, self._error(
                    "invalid_or_expired_token",
                    "Token invalid o caducat.",
                    status=401,
                )
            return solicitud, solicitud.centre_id, None

        centre, error = self._authenticate_admin()
        if error:
            return None, None, error

        if not solicitud_id:
            return None, None, self._error(
                "missing_solicitud_id",
                "Cal indicar solicitud_id o token temporal.",
                status=400,
            )

        solicitud = Solicitud.search([
            ("id", "=", solicitud_id),
            ("centre_id", "=", centre.id),
            ("estat", "=", "pendent"),
        ], limit=1)
        if not solicitud:
            return None, None, self._error(
                "solicitud_not_found",
                "No s'ha trobat la sol.licitud pendent.",
                status=404,
            )

        return solicitud, centre, None

    def _render_solicitud_action_page(self, action, solicitud):
        token = self._param("token") or self._param("action_token") or ""
        action_path = (
            "/joc_lector/api/professor/acceptar_solicitud"
            if action == "acceptar"
            else "/joc_lector/api/professor/rebutjar_solicitud"
        )
        action_url = "%s?token=%s" % (action_path, token) if token else action_path
        return request.render("joc_lector.professor_solicitud_action_page", {
            "action": action,
            "action_url": action_url,
            "solicitud": solicitud,
            "centre": solicitud.centre_id,
        })

    @http.route("/joc_lector/api/professor/acceptar_solicitud", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def professor_acceptar_solicitud(self, **kwargs):
        solicitud, centre, error = self._find_solicitud_for_action("acceptar")
        if error:
            return error
        if request.httprequest.method == "GET":
            return self._render_solicitud_action_page("acceptar", solicitud)
        if solicitud.estat != "pendent" or solicitud.token_used:
            return self._error(
                "solicitud_already_resolved",
                "Esta sol.licitud ja no esta pendent.",
                status=409,
                extra={"solicitud": self._serialize_solicitud(solicitud)},
            )

        rol = (self._param("rol") or "professor").strip()
        try:
            professor = solicitud.action_acceptar(centre, rol=rol)
        except ValidationError as exc:
            return self._error("limit_exceeded", str(exc), status=409)
        if not professor:
            return self._error(
                "invalid_state",
                "La sol.licitud no es pot acceptar en l'estat actual.",
                status=409,
            )

        self._send_template(
            "joc_lector.mail_template_joc_lector_professor_accepted",
            solicitud,
            ctx={"centre_name": solicitud.centre_id.name},
            email_to=solicitud.professor_email,
        )

        return self._json({
            "ok": True,
            "message": "Professorat acceptat correctament.",
            "solicitud": self._serialize_solicitud(solicitud),
            "professor_id": professor.id,
            "centre": self._serialize_centre(solicitud.centre_id),
        })

    @http.route("/joc_lector/api/professor/rebutjar_solicitud", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def professor_rebutjar_solicitud(self, **kwargs):
        solicitud, centre, error = self._find_solicitud_for_action("rebutjar")
        if error:
            return error
        if request.httprequest.method == "GET":
            return self._render_solicitud_action_page("rebutjar", solicitud)
        if solicitud.estat != "pendent" or solicitud.token_used:
            return self._error(
                "solicitud_already_resolved",
                "Esta sol.licitud ja no esta pendent.",
                status=409,
                extra={"solicitud": self._serialize_solicitud(solicitud)},
            )

        reason = (self._param("motiu") or self._param("reason") or "").strip()
        ok = solicitud.action_rebutjar(centre, reason=reason)
        if not ok:
            return self._error(
                "invalid_state",
                "La sol.licitud no es pot rebutjar en l'estat actual.",
                status=409,
            )

        self._send_template(
            "joc_lector.mail_template_joc_lector_professor_rejected",
            solicitud,
            ctx={"centre_name": solicitud.centre_id.name, "rejection_reason": reason},
            email_to=solicitud.professor_email,
        )

        return self._json({
            "ok": True,
            "message": "Sol.licitud rebutjada.",
            "solicitud": self._serialize_solicitud(solicitud),
        })

    @http.route("/joc_lector/api/centre/admin/classe/crear", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_crear_classe(self, **kwargs):
        centre, error = self._authenticate_admin()
        if error:
            return error

        name = (self._param("name") or self._param("nom") or "").strip()
        curs_academic = (self._param("curs_academic") or "").strip() or "2026-2027"
        curs_grup = (
            self._param("curs_grup")
            or self._param("cursGrup")
            or self._param("grup")
            or curs_academic
            or ""
        ).strip()
        nivell = (self._param("nivell") or "").strip()

        if not name:
            return self._error("missing_class_name", "Cal indicar el nom de la classe.")

        classe = request.env["joc.lector.classe"].sudo().create({
            "name": name,
            "centre_id": centre.id,
            "curs_academic": curs_academic,
            "curs_grup": curs_grup,
            "nivell": nivell or False,
        })

        return self._json({
            "ok": True,
            "message": "Classe creada correctament.",
            "classe": {
                "id": classe.id,
                "name": classe.name,
                "curs_academic": classe.curs_academic,
                "curs_grup": classe.curs_grup,
                "codi_acces": classe.access_code,
            },
        }, status=201)

    @http.route("/joc_lector/api/centre/admin/configurar", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def centre_admin_configurar(self, **kwargs):
        return self.centre_admin_configuracio(**kwargs)
