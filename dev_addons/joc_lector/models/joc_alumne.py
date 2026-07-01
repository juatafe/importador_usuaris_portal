# -*- coding: utf-8 -*-

from uuid import uuid4

from odoo import api, fields, models


class JocLectorAlumne(models.Model):
    _name = "joc.lector.alumne"
    _description = "Alumne lector"
    _order = "name"

    name = fields.Char(string="Nom visible", required=True, index=True)

    app_uid = fields.Char(
        string="Identificador intern app",
        required=True,
        copy=False,
        default=lambda self: uuid4().hex,
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

    passaport_id = fields.Many2one(
        "joc.lector.passaport",
        string="Passaport lector",
        compute="_compute_passaport_id",
        store=False,
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "app_uid_unique",
            "unique(app_uid)",
            "L'identificador intern de l'app ha de ser únic.",
        ),
    ]

    @api.depends("matricula_ids", "matricula_ids.active", "matricula_ids.classe_id")
    def _compute_current_classe_id(self):
        for alumne in self:
            matricula = alumne.matricula_ids.filtered(lambda m: m.active)[:1]
            alumne.current_classe_id = matricula.classe_id if matricula else False

    def _compute_passaport_id(self):
        Passaport = self.env["joc.lector.passaport"]
        for alumne in self:
            passaport = Passaport.search([("alumne_id", "=", alumne.id)], limit=1)
            alumne.passaport_id = passaport
