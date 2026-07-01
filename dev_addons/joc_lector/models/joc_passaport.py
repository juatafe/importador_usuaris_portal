# -*- coding: utf-8 -*-

from odoo import fields, models


class JocLectorPassaport(models.Model):
    _name = "joc.lector.passaport"
    _description = "Passaport lector"
    _order = "alumne_id"

    alumne_id = fields.Many2one(
        "joc.lector.alumne",
        string="Alumne",
        required=True,
        ondelete="cascade",
        index=True,
    )

    punts = fields.Integer(string="Punts", default=0)
    nivell = fields.Integer(string="Nivell", default=1)
    llibres_llegits = fields.Integer(string="Llibres llegits", default=0)

    notes = fields.Text(string="Notes internes")

    _sql_constraints = [
        (
            "alumne_passaport_unique",
            "unique(alumne_id)",
            "Cada alumne només pot tindre un passaport lector.",
        ),
    ]
