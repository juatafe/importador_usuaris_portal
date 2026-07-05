# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorRecoveryCode(models.Model):
    _name = "joc.lector.recovery.code"
    _description = "Codi de recuperació del Joc Lector"
    _order = "create_date desc, id desc"

    alumne_id = fields.Many2one(
        "joc.lector.alumne",
        string="Alumne",
        required=True,
        ondelete="cascade",
        index=True,
    )

    code_hash = fields.Char(
        string="Hash del codi",
        required=True,
        copy=False,
        index=True,
    )

    code_salt = fields.Char(
        string="Salt del codi",
        required=True,
        copy=False,
    )

    code_hint = fields.Char(
        string="Pista",
        readonly=True,
        help="Últims dos dígits del codi, només per identificar-lo internament.",
    )

    active = fields.Boolean(default=True)
    used = fields.Boolean(default=False)

    attempts = fields.Integer(string="Intents", default=0)
    max_attempts = fields.Integer(string="Màxim d'intents", default=5)

    date_created = fields.Datetime(
        string="Data de creació",
        default=fields.Datetime.now,
        required=True,
    )

    date_expires = fields.Datetime(
        string="Caduca el",
        required=True,
    )

    date_used = fields.Datetime(string="Data d'ús")

    device_name = fields.Char(string="Dispositiu sol·licitant")

    @api.model
    def _hash_code(self, raw_code, salt):
        return hashlib.sha256(f"{salt}:{raw_code}".encode("utf-8")).hexdigest()

    @api.model
    def _generate_code(self):
        return f"{secrets.randbelow(1000000):06d}"

    @api.model
    def create_for_alumne(self, alumne, device_name=None, minutes=15):
        raw_code = self._generate_code()
        salt = secrets.token_hex(16)
        now = fields.Datetime.now()

        # Desactivem codis anteriors pendents del mateix alumne.
        self.sudo().search([
            ("alumne_id", "=", alumne.id),
            ("active", "=", True),
            ("used", "=", False),
        ]).write({"active": False})

        record = self.sudo().create({
            "alumne_id": alumne.id,
            "code_hash": self._hash_code(raw_code, salt),
            "code_salt": salt,
            "code_hint": raw_code[-2:],
            "date_created": now,
            "date_expires": now + timedelta(minutes=minutes),
            "device_name": device_name or "Dispositiu sense nom",
            "active": True,
            "used": False,
        })

        return raw_code, record

    def validate_code(self, raw_code):
        self.ensure_one()

        now = fields.Datetime.now()

        if not self.active or self.used:
            return False, "used_or_inactive"

        if self.date_expires and self.date_expires < now:
            self.sudo().write({"active": False})
            return False, "expired"

        if self.attempts >= self.max_attempts:
            self.sudo().write({"active": False})
            return False, "too_many_attempts"

        expected_hash = self._hash_code(str(raw_code).strip(), self.code_salt)

        if expected_hash != self.code_hash:
            self.sudo().write({"attempts": self.attempts + 1})
            return False, "invalid_code"

        self.sudo().write({
            "used": True,
            "active": False,
            "date_used": now,
        })

        return True, "ok"
