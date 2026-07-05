# -*- coding: utf-8 -*-

from odoo import fields, models


class JocLectorProfessorCentre(models.Model):
    _name = "joc.lector.professor.centre"
    _description = "Historic professor-centre"
    _order = "date_start desc, id desc"

    professor_id = fields.Many2one(
        "joc.lector.professor",
        string="Professor",
        required=True,
        ondelete="cascade",
        index=True,
    )
    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        ondelete="restrict",
        index=True,
    )
    solicitud_id = fields.Many2one(
        "joc.lector.professor.solicitud",
        string="Sol.licitud origen",
        ondelete="set null",
    )
    state = fields.Selection(
        [
            ("active", "Activa"),
            ("left", "Canviat"),
            ("rejected", "Rebutjada"),
        ],
        string="Estat",
        required=True,
        default="active",
        index=True,
    )
    date_start = fields.Datetime(string="Data inici", default=fields.Datetime.now, required=True)
    date_end = fields.Datetime(string="Data fi")

    _sql_constraints = [
        (
            "joc_lector_professor_centre_unique_start",
            "unique(professor_id, centre_id, date_start)",
            "Ja existix un registre igual de vinculacio professor-centre.",
        ),
    ]
