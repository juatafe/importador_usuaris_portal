# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    joc_lector_professor_ids = fields.One2many(
        "joc.lector.professor",
        "user_id",
        string="Perfils Joc Lector",
    )
