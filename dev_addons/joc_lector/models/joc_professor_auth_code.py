# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models


class JocLectorProfessorAuthCode(models.Model):
    _name = "joc.lector.professor.auth.code"
    _description = "Codi temporal d'acces docent"
    _order = "create_date desc, id desc"
    _blocked_demo_codes = {
        "000000",
        "111111",
        "123123",
        "123456",
        "654321",
    }

    professor_id = fields.Many2one(
        "joc.lector.professor",
        string="Professor",
        required=True,
        ondelete="cascade",
        index=True,
    )
    email = fields.Char(string="Email", required=True, index=True)
    code_hash = fields.Char(string="Hash del codi", required=True, copy=False, index=True)
    code_salt = fields.Char(string="Salt del codi", required=True, copy=False)
    code_hint = fields.Char(string="Pista", readonly=True)
    active = fields.Boolean(default=True, index=True)
    used = fields.Boolean(default=False, index=True)
    attempts = fields.Integer(string="Intents", default=0)
    max_attempts = fields.Integer(string="Maxim d'intents", default=5)
    date_created = fields.Datetime(string="Creat", default=fields.Datetime.now, required=True)
    date_expires = fields.Datetime(string="Caduca", required=True)
    date_used = fields.Datetime(string="Usat")

    @api.model
    def _normalize_email(self, value):
        if not value:
            return False
        return str(value).strip().lower()

    @api.model
    def _hash_code(self, raw_code, salt):
        return hashlib.sha256(("%s:%s" % (salt, raw_code)).encode("utf-8")).hexdigest()

    @api.model
    def _generate_code(self):
        code = "%06d" % secrets.randbelow(1000000)
        while code in self._blocked_demo_codes:
            code = "%06d" % secrets.randbelow(1000000)
        return code

    @api.model
    def create_for_professor(self, professor, email=None, minutes=15):
        raw_code = self._generate_code()
        salt = secrets.token_hex(16)
        now = fields.Datetime.now()
        email = self._normalize_email(email or professor.user_id.login or professor.user_id.email)

        self.sudo().search([
            ("professor_id", "=", professor.id),
            ("active", "=", True),
            ("used", "=", False),
        ]).write({"active": False})

        record = self.sudo().create({
            "professor_id": professor.id,
            "email": email,
            "code_hash": self._hash_code(raw_code, salt),
            "code_salt": salt,
            "code_hint": raw_code[-2:],
            "date_created": now,
            "date_expires": now + timedelta(minutes=minutes),
            "active": True,
            "used": False,
        })
        return raw_code, record

    def validate_code(self, raw_code):
        self.ensure_one()
        now = fields.Datetime.now()
        raw_code = str(raw_code or "").strip()

        if raw_code in self._blocked_demo_codes:
            return False, "blocked_demo_code"

        if not self.active or self.used:
            return False, "used_or_inactive"

        if self.date_expires and self.date_expires < now:
            self.sudo().write({"active": False})
            return False, "expired"

        if self.attempts >= self.max_attempts:
            self.sudo().write({"active": False})
            return False, "too_many_attempts"

        expected_hash = self._hash_code(raw_code, self.code_salt)
        if expected_hash != self.code_hash:
            self.sudo().write({"attempts": self.attempts + 1})
            return False, "invalid_code"

        self.sudo().write({
            "used": True,
            "active": False,
            "date_used": now,
        })
        return True, "ok"
