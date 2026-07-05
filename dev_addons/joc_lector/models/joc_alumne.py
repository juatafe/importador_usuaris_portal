# -*- coding: utf-8 -*-

import secrets
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError


class JocLectorAlumne(models.Model):
    _name = "joc.lector.alumne"
    _description = "Alumne lector"
    _order = "name"

    name = fields.Char(string="Nom visible", required=True, index=True)
    nom_visible = fields.Char(
        string="Nom visible app",
        related="name",
        store=True,
        readonly=False,
    )

    app_uid = fields.Char(
        string="Identificador intern app",
        required=True,
        copy=False,
        default=lambda self: uuid4().hex,
        index=True,
    )
    codi_alumne = fields.Char(
        string="Codi alumne",
        required=True,
        copy=False,
        default=lambda self: self._generate_unique_student_code(),
        index=True,
    )

    avatar_128 = fields.Image(
        string="Avatar",
        max_width=128,
        max_height=128,
    )

    matricula_ids = fields.One2many(
        "joc.lector.matricula",
        "alumne_id",
        string="Historial de classes",
    )

    current_classe_id = fields.Many2one(
        "joc.lector.classe",
        string="Classe actual",
        compute="_compute_current_classe_id",
        store=True,
    )

    classe_actual_id = fields.Many2one(
        "joc.lector.classe",
        string="Classe actual (app)",
        related="current_classe_id",
        store=True,
        readonly=True,
    )

    centre_actual_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre actual",
        compute="_compute_centre_actual_id",
        store=True,
    )

    data_alta = fields.Date(
        string="Data alta",
        compute="_compute_data_alta",
        store=True,
    )

    codi_recuperacio_hash = fields.Char(string="Hash codi recuperació")
    token_hash_ultim = fields.Char(string="Hash últim token", compute="_compute_token_hash_ultim")

    passaport_id = fields.Many2one(
        "joc.lector.passaport",
        string="Passaport lector",
        compute="_compute_passaport_id",
        store=False,
    )

    active = fields.Boolean(default=True)

    actiu = fields.Boolean(
        string="Actiu",
        related="active",
        store=True,
        readonly=False,
    )

    _sql_constraints = [
        (
            "app_uid_unique",
            "unique(app_uid)",
            "L'identificador intern de l'app ha de ser únic.",
        ),
        (
            "codi_alumne_unique",
            "unique(codi_alumne)",
            "El codi d'alumne ha de ser únic.",
        ),
    ]

    @api.model
    def _generate_student_code(self, size=6):
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(alphabet) for _ in range(size))

    @api.model
    def _generate_unique_student_code(self):
        for _attempt in range(50):
            code = self._generate_student_code()
            if not self.sudo().search_count([("codi_alumne", "=", code)]):
                return code
        return secrets.token_hex(4).upper()

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for vals in vals_list:
            base_vals = dict(vals)
            for _attempt in range(50):
                candidate = dict(base_vals)
                candidate.setdefault("app_uid", uuid4().hex)
                candidate.setdefault("codi_alumne", self._generate_unique_student_code())
                try:
                    with self.env.cr.savepoint():
                        records |= super(JocLectorAlumne, self).create([candidate])
                    break
                except IntegrityError:
                    base_vals["app_uid"] = uuid4().hex
                    base_vals["codi_alumne"] = self._generate_unique_student_code()
            else:
                raise ValidationError("No s'ha pogut generar un alumne amb codis únics.")
        return records

    @api.depends("matricula_ids", "matricula_ids.state", "matricula_ids.classe_id")
    def _compute_current_classe_id(self):
        for alumne in self:
            matricula = alumne.matricula_ids.filtered(lambda m: m.state == "active")[:1]
            alumne.current_classe_id = matricula.classe_id if matricula else False

    @api.depends("current_classe_id", "current_classe_id.centre_id")
    def _compute_centre_actual_id(self):
        for alumne in self:
            alumne.centre_actual_id = alumne.current_classe_id.centre_id if alumne.current_classe_id else False

    @api.depends("create_date")
    def _compute_data_alta(self):
        for alumne in self:
            alumne.data_alta = fields.Date.to_date(alumne.create_date) if alumne.create_date else False

    def _compute_passaport_id(self):
        Passaport = self.env["joc.lector.passaport"]
        for alumne in self:
            passaport = Passaport.search([("alumne_id", "=", alumne.id)], limit=1)
            alumne.passaport_id = passaport

    def _compute_token_hash_ultim(self):
        Token = self.env["joc.lector.auth.token"].sudo()
        for alumne in self:
            token = Token.search([
                ("alumne_id", "=", alumne.id),
                ("active", "=", True),
            ], order="date_created desc, id desc", limit=1)
            alumne.token_hash_ultim = token.token_hash if token else False

    def get_ranking_snapshot(self):
        self.ensure_one()
        Mov = self.env["joc.lector.punts.moviment"].sudo()

        total_me = sum(Mov.search([("alumne_id", "=", self.id)]).mapped("punts"))

        def _position(domain):
            rows = Mov.read_group(domain, ["punts:sum"], ["alumne_id"])
            if not rows:
                return 0, 0

            ranking = sorted(rows, key=lambda r: r.get("punts_sum", 0), reverse=True)
            total = len(ranking)
            position = 0
            for idx, row in enumerate(ranking, start=1):
                alumne_ref = row.get("alumne_id")
                if alumne_ref and alumne_ref[0] == self.id:
                    position = idx
                    break
            return position, total

        classe_pos, classe_total = _position([
            ("classe_id", "=", self.current_classe_id.id),
        ]) if self.current_classe_id else (0, 0)

        centre_pos, centre_total = _position([
            ("centre_id", "=", self.centre_actual_id.id),
        ]) if self.centre_actual_id else (0, 0)

        global_pos, global_total = _position([])

        return {
            "punts_totals": total_me,
            "posicio_classe": classe_pos,
            "total_classe": classe_total,
            "posicio_centre": centre_pos,
            "total_centre": centre_total,
            "posicio_global": global_pos,
            "total_global": global_total,
        }
