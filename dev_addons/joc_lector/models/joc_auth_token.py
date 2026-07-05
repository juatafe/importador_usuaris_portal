# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorAuthToken(models.Model):
    _name = "joc.lector.auth.token"
    _description = "Token d'autenticació del Joc Lector"
    _order = "create_date desc, id desc"

    alumne_id = fields.Many2one(
        "joc.lector.alumne",
        string="Alumne",
        required=True,
        ondelete="cascade",
        index=True,
    )

    token_hash = fields.Char(
        string="Hash del token",
        required=True,
        copy=False,
        index=True,
    )

    token_hint = fields.Char(
        string="Pista del token",
        readonly=True,
        help="Últims caràcters del token, només per identificar-lo sense guardar el token real.",
    )

    device_name = fields.Char(string="Dispositiu")
    active = fields.Boolean(default=True)

    date_created = fields.Datetime(
        string="Data de creació",
        default=fields.Datetime.now,
        required=True,
    )

    date_last_used = fields.Datetime(string="Últim ús")
    date_expires = fields.Datetime(string="Caduca el")

    _sql_constraints = [
        (
            "token_hash_unique",
            "unique(token_hash)",
            "El hash del token ha de ser únic.",
        ),
    ]

    @api.model
    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @api.model
    def create_for_alumne(self, alumne, device_name=None, days=365):
        raw_token = secrets.token_urlsafe(32)
        now = fields.Datetime.now()

        token = self.create({
            "alumne_id": alumne.id,
            "token_hash": self._hash_token(raw_token),
            "token_hint": raw_token[-6:],
            "device_name": device_name or "Dispositiu sense nom",
            "date_created": now,
            "date_expires": now + timedelta(days=days),
            "active": True,
        })

        return raw_token, token

    @api.model
    def authenticate_raw_token(self, raw_token):
        if not raw_token:
            return False, False

        token_hash = self._hash_token(raw_token)

        token = self.sudo().search([
            ("token_hash", "=", token_hash),
            ("active", "=", True),
        ], limit=1)

        if not token:
            return False, False

        now = fields.Datetime.now()

        if token.date_expires and token.date_expires < now:
            token.sudo().write({"active": False})
            return False, False

        token.sudo().write({"date_last_used": now})
        return token.alumne_id, token
