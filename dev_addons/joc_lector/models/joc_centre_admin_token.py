# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorCentreAdminToken(models.Model):
    _name = "joc.lector.centre.admin.token"
    _description = "Token d'admin de centre"
    _order = "create_date desc, id desc"

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
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
            "joc_lector_centre_admin_token_hash_unique",
            "unique(token_hash)",
            "El hash del token ha de ser unic.",
        ),
    ]

    @api.model
    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @api.model
    def create_for_centre(self, centre, days=7):
        raw_token = secrets.token_urlsafe(32)
        now = fields.Datetime.now()
        token = self.create({
            "centre_id": centre.id,
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
        return token.centre_id, token
