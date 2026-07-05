# -*- coding: utf-8 -*-

import hashlib
import hmac
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorProfessorInvitation(models.Model):
    _name = "joc.lector.professor.invitation"
    _description = "Invitacio de professorat"
    _order = "create_date desc, id desc"

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        ondelete="cascade",
        index=True,
    )
    email = fields.Char(string="Email", required=True, index=True)
    name = fields.Char(string="Nom")
    token_hash = fields.Char(string="Hash token", required=True, copy=False, index=True)
    token_hint = fields.Char(string="Pista token", readonly=True)
    expires_at = fields.Datetime(string="Caduca", required=True, index=True)
    state = fields.Selection(
        [
            ("pendent", "Pendent"),
            ("acceptada", "Acceptada"),
            ("caducada", "Caducada"),
            ("cancel·lada", "Cancel·lada"),
        ],
        string="Estat",
        default="pendent",
        required=True,
        index=True,
    )
    created_by = fields.Many2one("res.users", string="Creat per", ondelete="set null")
    accepted_user_id = fields.Many2one("res.users", string="Usuari acceptat", ondelete="set null")
    professor_id = fields.Many2one("joc.lector.professor", string="Professor", ondelete="set null")

    _sql_constraints = [
        (
            "joc_lector_professor_invitation_token_unique",
            "unique(token_hash)",
            "El hash de la invitacio ha de ser unic.",
        ),
    ]

    @api.model
    def _normalize_email(self, value):
        if not value:
            return False
        return str(value).strip().lower()

    @api.model
    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @api.model
    def create_invitation(self, centre, email, name=None, created_by=None, days=14):
        raw_token = secrets.token_urlsafe(32)
        expires_at = fields.Datetime.now() + timedelta(days=days)
        invitation = self.create({
            "centre_id": centre.id,
            "email": self._normalize_email(email),
            "name": name or False,
            "token_hash": self._hash_token(raw_token),
            "token_hint": raw_token[-6:],
            "expires_at": expires_at,
            "created_by": created_by.id if created_by else False,
            "state": "pendent",
        })
        return raw_token, invitation

    def refresh_token(self, days=14):
        self.ensure_one()
        raw_token = secrets.token_urlsafe(32)
        expires_at = fields.Datetime.now() + timedelta(days=days)
        self.write({
            "token_hash": self._hash_token(raw_token),
            "token_hint": raw_token[-6:],
            "expires_at": expires_at,
            "state": "pendent",
        })
        return raw_token

    def match_token(self, raw_token):
        self.ensure_one()
        if not raw_token or self.state != "pendent":
            return False
        if self.expires_at and self.expires_at < fields.Datetime.now():
            self.write({"state": "caducada"})
            return False
        return hmac.compare_digest(self.token_hash or "", self._hash_token(str(raw_token).strip()))

    def _find_or_create_user(self):
        self.ensure_one()
        Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        login = self.email
        user = Users.search([("login", "=", login)], limit=1)
        if not user:
            user = Users.search([("email", "=", login)], limit=1)
        if user:
            return user

        return Users.create({
            "name": self.name or self.email,
            "login": login,
            "email": login,
            "notification_type": "email",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })

    def action_acceptar(self):
        self.ensure_one()
        if self.state != "pendent":
            return False

        user = self._find_or_create_user()
        groups = set(user.groups_id.ids)
        groups.add(self.env.ref("joc_lector.group_joc_lector_professor").id)
        user.sudo().write({"groups_id": [(6, 0, list(groups))]})

        Professor = self.env["joc.lector.professor"].sudo()
        professor = Professor.search([
            ("user_id", "=", user.id),
            ("centre_id", "=", self.centre_id.id),
        ], limit=1)
        if professor:
            professor.write({
                "active": True,
                "name": self.name or user.name,
                "rol": "professor",
            })
        else:
            professor = Professor.create({
                "name": self.name or user.name,
                "user_id": user.id,
                "centre_id": self.centre_id.id,
                "rol": "professor",
                "active": True,
            })

        self.env["joc.lector.professor.centre"].sudo().create({
            "professor_id": professor.id,
            "centre_id": self.centre_id.id,
            "state": "active",
            "date_start": fields.Datetime.now(),
        })

        self.write({
            "state": "acceptada",
            "accepted_user_id": user.id,
            "professor_id": professor.id,
        })
        return professor

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("email"):
                vals["email"] = self._normalize_email(vals["email"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("email"):
            vals["email"] = self._normalize_email(vals["email"])
        return super().write(vals)

    def expire_if_needed(self):
        now = fields.Datetime.now()
        expired = self.filtered(lambda inv: inv.state == "pendent" and inv.expires_at and inv.expires_at < now)
        if expired:
            expired.write({"state": "caducada"})
        return True
