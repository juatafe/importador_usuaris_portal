# -*- coding: utf-8 -*-

import hashlib
import hmac
import re
import secrets

from odoo import api, fields, models


OFFICIAL_EMAIL_PATTERN = re.compile(r"^\d+@edu\.gva\.es$")
JOC_LECTOR_EMAIL_FROM = "Joc Lector <joc-lector@provestalens.es>"


class JocLectorCentre(models.Model):
    _name = "joc.lector.centre"
    _description = "Centre educatiu"
    _order = "name"

    name = fields.Char(string="Nom del centre", required=True, index=True)
    code = fields.Char(string="Codi del centre")
    codi_centre = fields.Char(
        string="Codi centre",
        related="code",
        store=True,
        readonly=False,
    )
    municipi = fields.Char(string="Municipi")
    email_oficial = fields.Char(string="Email oficial", index=True, copy=False)
    official_email = fields.Char(
        string="Official email",
        related="email_oficial",
        store=True,
        readonly=False,
    )
    tic_nom = fields.Char(string="Nom contacte TIC")
    tic_email = fields.Char(string="Email contacte TIC")
    admin_code_hash = fields.Char(string="Hash codi administracio", copy=False)
    admin_code_expires_at = fields.Datetime(string="Caducitat codi admin", copy=False)
    admin_code_last_sent = fields.Datetime(string="Ultim enviament codi admin")
    admin_verified = fields.Boolean(string="Admin centre verificat", default=False, copy=False)
    admin_user_id = fields.Many2one(
        "res.users",
        string="Usuari admin centre",
        ondelete="set null",
        copy=False,
    )
    estat = fields.Selection(
        [
            ("esborrany", "Esborrany"),
            ("actiu", "Actiu"),
            ("bloquejat", "Bloquejat"),
        ],
        string="Estat",
        required=True,
        default="actiu",
        index=True,
    )
    admin_login_fail_count = fields.Integer(string="Intents login fallits", default=0)
    admin_login_blocked_until = fields.Datetime(string="Login bloquejat fins")
    ranking_public = fields.Boolean(string="Rànquing públic", default=False)
    web_publica_activa = fields.Boolean(string="Web pública activa", default=False)
    active = fields.Boolean(default=True)
    actiu = fields.Boolean(
        string="Actiu",
        related="active",
        store=True,
        readonly=False,
    )

    classe_ids = fields.One2many(
        "joc.lector.classe",
        "centre_id",
        string="Classes",
    )

    professor_solicitud_ids = fields.One2many(
        "joc.lector.professor.solicitud",
        "centre_id",
        string="Sol.licituds professorat",
    )

    _sql_constraints = [
        (
            "joc_lector_centre_email_oficial_unique",
            "unique(email_oficial)",
            "Ja existix un centre amb este email oficial.",
        ),
    ]

    @api.model
    def _normalize_email(self, value):
        if not value:
            return False
        return str(value).strip().lower()

    @api.model
    def _is_valid_official_email(self, value):
        email = self._normalize_email(value)
        return bool(email and OFFICIAL_EMAIL_PATTERN.match(email))

    @api.model
    def _hash_admin_code(self, raw_code):
        return hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    @api.model
    def _generate_admin_code(self, size=10):
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(alphabet) for _ in range(size))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("email_oficial"):
                vals["email_oficial"] = self._normalize_email(vals["email_oficial"])
            if vals.get("tic_email"):
                vals["tic_email"] = self._normalize_email(vals["tic_email"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("email_oficial"):
            vals["email_oficial"] = self._normalize_email(vals["email_oficial"])
        if vals.get("tic_email"):
            vals["tic_email"] = self._normalize_email(vals["tic_email"])
        return super().write(vals)

    def check_admin_code(self, raw_code):
        self.ensure_one()
        if not raw_code or not self.admin_code_hash:
            return False
        if self.admin_code_expires_at and self.admin_code_expires_at < fields.Datetime.now():
            return False
        return hmac.compare_digest(self.admin_code_hash, self._hash_admin_code(str(raw_code).strip()))

    def consume_login_attempt(self, success):
        self.ensure_one()
        now = fields.Datetime.now()

        if success:
            self.write({
                "admin_login_fail_count": 0,
                "admin_login_blocked_until": False,
                "estat": "actiu",
            })
            return

        next_count = (self.admin_login_fail_count or 0) + 1
        vals = {"admin_login_fail_count": next_count}
        if next_count >= 5:
            vals.update({
                "admin_login_blocked_until": fields.Datetime.add(now, minutes=15),
                "estat": "bloquejat",
            })
        self.write(vals)

    def is_login_blocked(self):
        self.ensure_one()
        now = fields.Datetime.now()
        return bool(self.admin_login_blocked_until and self.admin_login_blocked_until > now)

    def set_new_admin_code(self):
        self.ensure_one()
        raw_code = self._generate_admin_code()
        self.write({
            "admin_code_hash": self._hash_admin_code(raw_code),
            "admin_code_expires_at": fields.Datetime.add(fields.Datetime.now(), days=7),
            "admin_code_last_sent": fields.Datetime.now(),
            "admin_verified": False,
            "estat": "actiu",
        })
        return raw_code

    def action_regenerate_admin_code(self):
        self.ensure_one()
        raw_code = self.set_new_admin_code()
        template = self.env.ref("joc_lector.mail_template_joc_lector_admin_code_regenerated", raise_if_not_found=False)
        if template:
            template.sudo().with_context(admin_code=raw_code).send_mail(
                self.id,
                force_send=True,
                email_values={"email_from": JOC_LECTOR_EMAIL_FROM},
            )

        wizard = self.env["joc.lector.centre.admin.code.wizard"].sudo().create({
            "centre_id": self.id,
            "admin_code": raw_code,
        })

        return {
            "type": "ir.actions.act_window",
            "name": "Nou codi admin",
            "res_model": "joc.lector.centre.admin.code.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
