# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorProfessorAuthToken(models.Model):
    _name = "joc.lector.professor.auth.token"
    _description = "Token d'autenticacio docent"
    _order = "create_date desc, id desc"

    professor_id = fields.Many2one(
        "joc.lector.professor",
        string="Professor",
        required=True,
        ondelete="cascade",
        index=True,
    )
    token_hash = fields.Char(string="Hash token", required=True, copy=False, index=True)
    token_hint = fields.Char(string="Pista token", readonly=True)
    active = fields.Boolean(default=True, index=True)
    date_created = fields.Datetime(string="Creat", default=fields.Datetime.now, required=True)
    date_last_used = fields.Datetime(string="Ultim us")
    date_expires = fields.Datetime(string="Caduca")

    _sql_constraints = [
        (
            "joc_lector_professor_auth_token_hash_unique",
            "unique(token_hash)",
            "El hash del token docent ha de ser unic.",
        ),
    ]

    @api.model
    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @api.model
    def create_for_professor(self, professor, days=30):
        raw_token = secrets.token_urlsafe(32)
        now = fields.Datetime.now()
        token = self.create({
            "professor_id": professor.id,
            "token_hash": self._hash_token(raw_token),
            "token_hint": raw_token[-6:],
            "date_created": now,
            "date_expires": now + timedelta(days=days),
            "active": True,
        })
        return raw_token, token

    @api.model
    def authenticate_raw_token(self, raw_token):
        if not raw_token:
            return False, False

        token = self.sudo().search([
            ("token_hash", "=", self._hash_token(raw_token)),
            ("active", "=", True),
        ], limit=1)
        if not token:
            return False, False

        now = fields.Datetime.now()
        if token.date_expires and token.date_expires < now:
            token.sudo().write({"active": False})
            return False, False

        professor = token.professor_id
        if not professor or not professor.active or not professor.centre_id.active:
            token.sudo().write({"active": False})
            return False, False

        token.sudo().write({"date_last_used": now})
        return professor, token

