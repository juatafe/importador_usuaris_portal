# -*- coding: utf-8 -*-

from odoo import api, fields, models


class JocLectorMatricula(models.Model):
    _name = "joc.lector.matricula"
    _description = "Matrícula de l'alumne en una classe"
    _order = "date_start desc, id desc"

    alumne_id = fields.Many2one(
        "joc.lector.alumne",
        string="Alumne",
        required=True,
        ondelete="cascade",
    )

    classe_id = fields.Many2one(
        "joc.lector.classe",
        string="Classe",
        required=True,
        ondelete="restrict",
    )

    curs_academic = fields.Char(
        related="classe_id.curs_academic",
        string="Curs acadèmic",
        store=True,
        readonly=True,
    )

    date_start = fields.Date(
        string="Data d'inici",
        default=fields.Date.context_today,
        required=True,
    )

    date_end = fields.Date(string="Data de finalització")

    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            altres = self.search([
                ("alumne_id", "=", record.alumne_id.id),
                ("id", "!=", record.id),
                ("active", "=", True),
            ])
            altres.write({
                "active": False,
                "date_end": fields.Date.context_today(self),
            })

            passaport = self.env["joc.lector.passaport"].search([
                ("alumne_id", "=", record.alumne_id.id)
            ], limit=1)

            if not passaport:
                self.env["joc.lector.passaport"].create({
                    "alumne_id": record.alumne_id.id,
                })

        return records
