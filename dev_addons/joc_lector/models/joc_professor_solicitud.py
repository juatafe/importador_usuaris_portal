# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorProfessorSolicitud(models.Model):
    _name = "joc.lector.professor.solicitud"
    _description = "Sol.licitud d'acces de professorat"
    _order = "create_date desc, id desc"

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        ondelete="cascade",
        index=True,
    )
    centre_name = fields.Char(string="Nom centre", related="centre_id.name", store=True, readonly=True)
    centre_email_oficial = fields.Char(string="Email oficial", related="centre_id.email_oficial", store=True, readonly=True)
    professor_nom = fields.Char(string="Nom professor", required=True)
    professor_email = fields.Char(string="Email professional", required=True, index=True)
    municipi = fields.Char(string="Municipi")
    notes = fields.Text(string="Notes")
    estat = fields.Selection(
        [
            ("pendent", "Pendent"),
            ("acceptada", "Acceptada"),
            ("rebutjada", "Rebutjada"),
            ("caducada", "Caducada"),
        ],
        string="Estat",
        required=True,
        default="pendent",
        index=True,
    )
    decidida_per_centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Decidida per centre",
        ondelete="set null",
    )
    motiu_rebuig = fields.Char(string="Motiu rebuig")
    professor_id = fields.Many2one(
        "joc.lector.professor",
        string="Perfil professor creat",
        ondelete="set null",
    )
    token_accept_hash = fields.Char(string="Hash token acceptar", copy=False, index=True)
    token_reject_hash = fields.Char(string="Hash token rebutjar", copy=False, index=True)
    token_expires = fields.Datetime(string="Caduca token")
    token_used = fields.Boolean(string="Token usat", default=False)
    decided_at = fields.Datetime(string="Data decisio")

    @api.model
    def _normalize_email(self, value):
        if not value:
            return False
        return str(value).strip().lower()

    @api.model
    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("professor_email"):
                vals["professor_email"] = self._normalize_email(vals["professor_email"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("professor_email"):
            vals["professor_email"] = self._normalize_email(vals["professor_email"])
        return super().write(vals)

    def generate_action_tokens(self, hours=72):
        self.ensure_one()
        accept_raw = secrets.token_urlsafe(24)
        reject_raw = secrets.token_urlsafe(24)
        expires = fields.Datetime.now() + timedelta(hours=hours)
        self.write({
            "token_accept_hash": self._hash_token(accept_raw),
            "token_reject_hash": self._hash_token(reject_raw),
            "token_expires": expires,
            "token_used": False,
        })
        return accept_raw, reject_raw, expires

    def match_token(self, action, raw_token):
        self.ensure_one()
        if not raw_token or self.estat != "pendent" or self.token_used:
            return False
        now = fields.Datetime.now()
        if self.token_expires and self.token_expires < now:
            self.write({"estat": "caducada"})
            return False

        token_hash = self._hash_token(raw_token)
        expected = self.token_accept_hash if action == "acceptar" else self.token_reject_hash
        return bool(expected and token_hash == expected)

    def _find_or_create_user(self):
        self.ensure_one()
        Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        login = self.professor_email
        user = Users.search([("login", "=", login)], limit=1)
        if not user:
            user = Users.search([("email", "=", login)], limit=1)
        if user:
            return user

        return Users.create({
            "name": self.professor_nom,
            "login": login,
            "email": login,
            "notification_type": "email",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })

    def action_acceptar(self, centre, rol="professor"):
        self.ensure_one()
        if self.estat != "pendent":
            return False

        if rol not in ("professor", "admin_centre"):
            rol = "professor"

        user = self._find_or_create_user()
        groups = set(user.groups_id.ids)
        groups.add(self.env.ref("joc_lector.group_joc_lector_professor").id)
        if rol == "admin_centre":
            groups.add(self.env.ref("joc_lector.group_joc_lector_admin_centre").id)
        user.sudo().write({"groups_id": [(6, 0, list(groups))]})

        Professor = self.env["joc.lector.professor"].sudo()

        professor = Professor.search([
            ("user_id", "=", user.id),
            ("centre_id", "=", self.centre_id.id),
        ], limit=1)

        if professor:
            professor.write({"active": True, "name": self.professor_nom, "rol": rol})
        else:
            professor = Professor.create({
                "name": self.professor_nom,
                "user_id": user.id,
                "centre_id": self.centre_id.id,
                "rol": rol,
                "active": True,
            })

        old_professors = Professor.search([
            ("user_id", "=", user.id),
            ("centre_id", "!=", self.centre_id.id),
            ("rol", "=", "professor"),
            ("active", "=", True),
        ])
        if old_professors:
            old_professors.write({"active": False})

            old_links_other = self.env["joc.lector.professor.centre"].sudo().search([
                ("professor_id", "in", old_professors.ids),
                ("state", "=", "active"),
            ])
            if old_links_other:
                old_links_other.write({
                    "state": "left",
                    "date_end": fields.Datetime.now(),
                })

        Link = self.env["joc.lector.professor.centre"].sudo()
        old_links = Link.search([
            ("professor_id", "=", professor.id),
            ("state", "=", "active"),
        ])
        if old_links:
            old_links.write({
                "state": "left",
                "date_end": fields.Datetime.now(),
            })

        Link.create({
            "professor_id": professor.id,
            "centre_id": self.centre_id.id,
            "solicitud_id": self.id,
            "state": "active",
            "date_start": fields.Datetime.now(),
        })

        self.write({
            "estat": "acceptada",
            "professor_id": professor.id,
            "decidida_per_centre_id": centre.id,
            "decided_at": fields.Datetime.now(),
            "token_used": True,
        })

        return professor

    def action_rebutjar(self, centre, reason=None):
        self.ensure_one()
        if self.estat != "pendent":
            return False
        self.write({
            "estat": "rebutjada",
            "motiu_rebuig": reason or False,
            "decidida_per_centre_id": centre.id,
            "decided_at": fields.Datetime.now(),
            "token_used": True,
        })
        return True
