# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


MAX_ALUMNES_PER_CLASSE = 40


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

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        related="classe_id.centre_id",
        store=True,
        readonly=True,
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

    data_inici = fields.Date(
        string="Data inici",
        related="date_start",
        store=True,
        readonly=False,
    )

    date_end = fields.Date(string="Data de finalització")

    data_fi = fields.Date(
        string="Data fi",
        related="date_end",
        store=True,
        readonly=False,
    )

    state = fields.Selection(
        [
            ("active", "Activa"),
            ("closed", "Tancada"),
        ],
        string="Estat",
        default="active",
        required=True,
        index=True,
    )

    activa = fields.Boolean(
        string="Activa",
        compute="_compute_activa",
        inverse="_inverse_activa",
        store=True,
    )

    @api.depends("state")
    def _compute_activa(self):
        for record in self:
            record.activa = record.state == "active"

    def _inverse_activa(self):
        for record in self:
            if record.activa and record.state != "active":
                record.state = "active"
            elif not record.activa and record.state != "closed":
                record.state = "closed"

    def _validate_class_capacity_for_create(self, vals_list):
        incoming_by_class = {}
        for vals in vals_list:
            if vals.get("state", "active") != "active":
                continue
            classe_id = vals.get("classe_id")
            if not classe_id:
                continue
            incoming_by_class[classe_id] = incoming_by_class.get(classe_id, 0) + 1

        for classe_id, incoming in incoming_by_class.items():
            current = self.search_count([
                ("classe_id", "=", classe_id),
                ("state", "=", "active"),
            ])
            if current + incoming > MAX_ALUMNES_PER_CLASSE:
                classe = self.env["joc.lector.classe"].browse(classe_id)
                raise ValidationError(
                    "La classe %s ja té %s alumnes actius. No es poden superar %s alumnes per classe; eixa ràtio és massa gran per a l'app."
                    % (classe.display_name, current, MAX_ALUMNES_PER_CLASSE)
                )

    def _validate_class_capacity_for_write(self, vals):
        if not ({"classe_id", "state", "activa"} & set(vals)):
            return

        incoming_by_class = {}
        for record in self:
            new_state = vals.get("state", record.state)
            if "activa" in vals:
                new_state = "active" if vals.get("activa") else "closed"
            if new_state != "active":
                continue
            classe_id = vals.get("classe_id") or record.classe_id.id
            if not classe_id:
                continue
            incoming_by_class[classe_id] = incoming_by_class.get(classe_id, 0) + 1

        for classe_id, incoming in incoming_by_class.items():
            current = self.search_count([
                ("classe_id", "=", classe_id),
                ("state", "=", "active"),
                ("id", "not in", self.ids),
            ])
            if current + incoming > MAX_ALUMNES_PER_CLASSE:
                classe = self.env["joc.lector.classe"].browse(classe_id)
                raise ValidationError(
                    "La classe %s ja té %s alumnes actius. No es poden superar %s alumnes per classe; eixa ràtio és massa gran per a l'app."
                    % (classe.display_name, current, MAX_ALUMNES_PER_CLASSE)
                )

    @api.model_create_multi
    def create(self, vals_list):
        self._validate_class_capacity_for_create(vals_list)
        records = super().create(vals_list)

        for record in records:
            altres = self.search([
                ("alumne_id", "=", record.alumne_id.id),
                ("id", "!=", record.id),
                ("state", "=", "active"),
            ])
            altres.write({
                "state": "closed",
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

    def write(self, vals):
        self._validate_class_capacity_for_write(vals)
        return super().write(vals)
