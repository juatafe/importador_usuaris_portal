# -*- coding: utf-8 -*-

from odoo import fields, models


class JocLectorCentreAdminCodeWizard(models.TransientModel):
    _name = "joc.lector.centre.admin.code.wizard"
    _description = "Wizard codi admin centre"

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        readonly=True,
    )
    admin_code = fields.Char(
        string="Codi admin generat",
        required=True,
        readonly=True,
    )
    info_message = fields.Text(
        string="Informacio",
        readonly=True,
        default="Mostra puntual del codi administratiu. Per seguretat no es guarda en text pla.",
    )
