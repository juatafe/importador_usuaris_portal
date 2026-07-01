# -*- coding: utf-8 -*-

from odoo import fields, models


class JocLectorCentre(models.Model):
    _name = "joc.lector.centre"
    _description = "Centre educatiu"
    _order = "name"

    name = fields.Char(string="Nom del centre", required=True, index=True)
    code = fields.Char(string="Codi del centre")
    active = fields.Boolean(default=True)

    classe_ids = fields.One2many(
        "joc.lector.classe",
        "centre_id",
        string="Classes",
    )
