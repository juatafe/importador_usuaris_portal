# -*- coding: utf-8 -*-

import json

from odoo import fields
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import Response, request


class JocLectorPublicController(http.Controller):
    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False, default=str),
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def _error(self, code, message, status=400):
        return self._json({"ok": False, "error": {"code": code, "message": message}}, status=status)

    def _payload(self):
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

    def _find_invitation_by_token(self, token):
        if not token:
            return False
        Invitation = request.env["joc.lector.professor.invitation"].sudo()
        token_hash = Invitation._hash_token(str(token).strip())
        return Invitation.search([("token_hash", "=", token_hash)], limit=1)

    def _format_invitation_expires(self, invitation):
        if not invitation or not invitation.expires_at:
            return ""
        local_dt = fields.Datetime.context_timestamp(
            invitation.with_context(tz="Europe/Madrid"),
            invitation.expires_at,
        )
        return local_dt.strftime("%d/%m/%Y %H:%M")

    def _get_public_reviews_domain(self):
        return [
            ("active", "=", True),
            ("publicable", "=", True),
            ("aprovada", "=", True),
        ]

    def _get_books_domain(self):
        return [
            ("active", "=", True),
        ]

    def _render_public_not_found(self, title, message):
        return request.render("joc_lector.public_not_found", {
            "title": title,
            "message": message,
        })

    @http.route(
        ["/lectures", "/lectures/"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_home(self, **kwargs):
        Llibre = request.env["joc.lector.llibre"].sudo()
        Ressenya = request.env["joc.lector.ressenya"].sudo()
        Lectura = request.env["joc.lector.lectura"].sudo()

        llibres_destacats = Llibre.search(
            self._get_books_domain(),
            order="valoracio_mitjana desc, lectura_count desc, name asc",
            limit=6,
        )

        ressenyes_recents = Ressenya.search(
            self._get_public_reviews_domain(),
            order="create_date desc, id desc",
            limit=6,
        )

        stats = {
            "llibres": Llibre.search_count(self._get_books_domain()),
            "lectures": Lectura.search_count([("state", "=", "finished")]),
            "ressenyes": Ressenya.search_count(self._get_public_reviews_domain()),
        }

        return request.render("joc_lector.public_home", {
            "llibres_destacats": llibres_destacats,
            "ressenyes_recents": ressenyes_recents,
            "stats": stats,
        })

    @http.route(
        ["/lectures/llibres"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_llibres(self, q=None, **kwargs):
        Llibre = request.env["joc.lector.llibre"].sudo()

        domain = self._get_books_domain()

        if q:
            q = q.strip()
            domain += [
                "|", "|",
                ("name", "ilike", q),
                ("autor", "ilike", q),
                ("categoria", "ilike", q),
            ]

        llibres = Llibre.search(
            domain,
            order="name asc",
            limit=200,
        )

        return request.render("joc_lector.public_llibres", {
            "llibres": llibres,
            "q": q or "",
        })

    @http.route(
        ["/lectures/top"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_top(self, **kwargs):
        Llibre = request.env["joc.lector.llibre"].sudo()

        llibres_mes_llegits = Llibre.search(
            self._get_books_domain(),
            order="lectura_count desc, valoracio_mitjana desc, name asc",
            limit=20,
        )

        llibres_mes_valorats = Llibre.search(
            self._get_books_domain() + [("ressenya_count", ">", 0)],
            order="valoracio_mitjana desc, ressenya_count desc, name asc",
            limit=20,
        )

        return request.render("joc_lector.public_top", {
            "llibres_mes_llegits": llibres_mes_llegits,
            "llibres_mes_valorats": llibres_mes_valorats,
        })

    @http.route(
        ["/lectures/privacitat"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_privacitat(self, **kwargs):
        return request.render("joc_lector.public_privacitat", {})

    @http.route(
        ["/lectures/app", "/lectures/app/"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_app(self, **kwargs):
        return request.render("joc_lector.public_app", {})

    @http.route(
        ["/joc_lector/professor/invitacio"],
        type="http",
        auth="public",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
        csrf=False,
    )
    def professor_invitacio(self, token=None, **kwargs):
        invitation = self._find_invitation_by_token(token)
        status = "invalid"
        professor = False

        if invitation:
            invitation.expire_if_needed()
            if invitation.state == "pendent" and invitation.match_token(token):
                status = "pending"
                if request.httprequest.method == "POST":
                    professor = invitation.action_acceptar()
                    status = "accepted" if professor else "invalid"
            elif invitation.state == "acceptada":
                status = "already_accepted"
            elif invitation.state == "caducada":
                status = "expired"
            else:
                status = invitation.state or "invalid"

        return request.render("joc_lector.professor_invitation_page", {
            "invitation": invitation,
            "status": status,
            "token": token or "",
            "professor": professor,
            "expires_display": self._format_invitation_expires(invitation) if invitation else "",
            "privacy_url": "/lectures/privacitat",
        })

    @http.route(
        ["/joc_lector/api/professor/acceptar_invitacio"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def professor_acceptar_invitacio(self, token=None, **kwargs):
        token = token or self._param("token")
        invitation = self._find_invitation_by_token(token)

        if not invitation:
            return self._error("invalid_or_expired_token", "Token invalid o caducat.", status=401)

        invitation.expire_if_needed()
        if invitation.state == "acceptada":
            professor = invitation.professor_id
            return self._json({
                "ok": True,
                "status": "already_accepted",
                "message": "La invitacio ja havia sigut acceptada.",
                "professor": {
                    "id": professor.id,
                    "name": professor.name,
                    "email": professor.user_id.email or professor.user_id.login,
                    "rol": professor.rol,
                } if professor else None,
                "centre": {
                    "id": invitation.centre_id.id,
                    "name": invitation.centre_id.name,
                },
            })

        if invitation.state == "caducada":
            return self._error("expired_token", "La invitacio ha caducat.", status=410)

        if invitation.state != "pendent" or not invitation.match_token(token):
            return self._error("invalid_or_expired_token", "Token invalid o caducat.", status=401)

        try:
            professor = invitation.action_acceptar()
        except ValidationError as exc:
            return self._error("limit_exceeded", str(exc), status=409)
        if not professor:
            return self._error("invalid_state", "La invitacio no es pot acceptar en l'estat actual.", status=409)

        return self._json({
            "ok": True,
            "status": "accepted",
            "message": "Invitacio acceptada correctament.",
            "professor": {
                "id": professor.id,
                "name": professor.name,
                "email": professor.user_id.email or professor.user_id.login,
                "rol": professor.rol,
            },
            "centre": {
                "id": professor.centre_id.id,
                "name": professor.centre_id.name,
            },
        })

    @http.route(
        ["/lectures/llibre/<string:slug>"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_llibre_detail(self, slug, **kwargs):
        Llibre = request.env["joc.lector.llibre"].sudo()
        Ressenya = request.env["joc.lector.ressenya"].sudo()

        llibre = Llibre.search([
            ("slug", "=", slug),
            ("active", "=", True),
        ], limit=1)

        if not llibre:
            return self._render_public_not_found(
                "Llibre no trobat",
                "No hem trobat este llibre en el cataleg public. Pot haver canviat l'enllac o encara no estar publicat.",
            )

        ressenyes = Ressenya.search(
            self._get_public_reviews_domain() + [
                ("llibre_id", "=", llibre.id),
            ],
            order="create_date desc, id desc",
            limit=50,
        )

        return request.render("joc_lector.public_llibre_detail", {
            "llibre": llibre,
            "ressenyes": ressenyes,
        })

    @http.route(
        ["/lectures/ressenya/<string:slug>"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def lectures_ressenya_detail(self, slug, **kwargs):
        Ressenya = request.env["joc.lector.ressenya"].sudo()

        ressenya = Ressenya.search(
            self._get_public_reviews_domain() + [
                ("slug", "=", slug),
            ],
            limit=1,
        )

        if not ressenya:
            return self._render_public_not_found(
                "Ressenya no trobada",
                "No hem trobat esta ressenya publica. Pot haver sigut retirada, estar pendent de validacio o haver canviat l'enllac.",
            )

        return request.render("joc_lector.public_ressenya_detail", {
            "ressenya": ressenya,
            "llibre": ressenya.llibre_id,
        })
