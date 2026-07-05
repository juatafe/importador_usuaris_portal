# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value)
    value = re.sub(r"^-+|-+$", "", value)
    return value or "ressenya"


class JocLectorRessenya(models.Model):
    _name = "joc.lector.ressenya"
    _description = "Ressenya de lectura"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    alumne_id = fields.Many2one(
        "joc.lector.alumne",
        string="Alumne",
        required=True,
        ondelete="cascade",
        tracking=True,
    )

    llibre_id = fields.Many2one(
        "joc.lector.llibre",
        string="Llibre",
        required=True,
        ondelete="restrict",
        tracking=True,
    )

    lectura_id = fields.Many2one(
        "joc.lector.lectura",
        string="Lectura relacionada",
        ondelete="set null",
    )

    classe_id = fields.Many2one(
        "joc.lector.classe",
        string="Classe",
        ondelete="restrict",
    )

    curs_academic = fields.Char(
        related="classe_id.curs_academic",
        string="Curs acadèmic",
        store=True,
        readonly=True,
    )

    text = fields.Text(string="Text de la ressenya", required=True)
    valoracio = fields.Integer(string="Valoració", default=5, required=True)

    publicable = fields.Boolean(
        string="Es pot publicar",
        default=False,
        help="Indica si la ressenya pot aparéixer en la web pública de manera anonimitzada.",
    )

    aprovada = fields.Boolean(
        string="Aprovada",
        default=False,
        tracking=True,
    )

    slug = fields.Char(string="Slug públic", copy=False, index=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "slug_ressenya_unique",
            "unique(slug)",
            "El slug públic de la ressenya ha de ser únic.",
        ),
    ]

    @api.constrains("valoracio")
    def _check_valoracio(self):
        for record in self:
            if record.valoracio < 1 or record.valoracio > 5:
                raise ValidationError("La valoració ha d'estar entre 1 i 5.")

    @api.onchange("alumne_id")
    def _onchange_alumne_id(self):
        for record in self:
            if record.alumne_id and not record.classe_id:
                record.classe_id = record.alumne_id.current_classe_id

    @api.onchange("lectura_id")
    def _onchange_lectura_id(self):
        for record in self:
            if record.lectura_id:
                record.alumne_id = record.lectura_id.alumne_id
                record.llibre_id = record.lectura_id.llibre_id
                record.classe_id = record.lectura_id.classe_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("lectura_id"):
                lectura = self.env["joc.lector.lectura"].browse(vals["lectura_id"])
                vals.setdefault("alumne_id", lectura.alumne_id.id)
                vals.setdefault("llibre_id", lectura.llibre_id.id)
                vals.setdefault("classe_id", lectura.classe_id.id)

            if vals.get("alumne_id") and not vals.get("classe_id"):
                alumne = self.env["joc.lector.alumne"].browse(vals["alumne_id"])
                if alumne.current_classe_id:
                    vals["classe_id"] = alumne.current_classe_id.id

        records = super().create(vals_list)
        for record in records:
            if not record.slug:
                record.slug = "%s-%s" % (slugify(record.llibre_id.name), record.id)
        return records
