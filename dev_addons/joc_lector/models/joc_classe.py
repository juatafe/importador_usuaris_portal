# -*- coding: utf-8 -*-

from uuid import uuid4

from odoo import api, fields, models


class JocLectorClasse(models.Model):
    _name = "joc.lector.classe"
    _description = "Classe del Joc Lector"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "curs_academic desc, name"

    name = fields.Char(string="Nom de la classe", required=True, tracking=True)

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        ondelete="restrict",
        tracking=True,
    )

    curs_academic = fields.Char(
        string="Curs acadèmic",
        required=True,
        default="2026-2027",
        tracking=True,
    )

    access_code = fields.Char(
        string="Codi d'entrada",
        required=True,
        copy=False,
        default=lambda self: "JL-" + uuid4().hex[:6].upper(),
        tracking=True,
    )

    professor_ids = fields.Many2many(
        "res.users",
        string="Professorat",
    )

    matricula_ids = fields.One2many(
        "joc.lector.matricula",
        "classe_id",
        string="Matrícules",
    )

    alumne_count = fields.Integer(
        string="Nombre d'alumnes",
        compute="_compute_alumne_count",
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "access_code_unique",
            "unique(access_code)",
            "El codi d'entrada ha de ser únic.",
        ),
    ]

    @api.depends("matricula_ids", "matricula_ids.active")
    def _compute_alumne_count(self):
        for record in self:
            record.alumne_count = len(record.matricula_ids.filtered(lambda m: m.active))
