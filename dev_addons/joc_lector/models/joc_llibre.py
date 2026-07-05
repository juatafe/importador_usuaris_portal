# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value)
    value = re.sub(r"^-+|-+$", "", value)
    return value or "llibre"


class JocLectorLlibre(models.Model):
    _name = "joc.lector.llibre"
    _description = "Llibre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Títol", required=True, index=True, tracking=True)
    titol = fields.Char(
        string="Títol (catàleg)",
        related="name",
        store=True,
        readonly=False,
    )
    autor = fields.Char(string="Autor/a", index=True)
    isbn = fields.Char(string="ISBN", index=True)
    editorial = fields.Char(string="Editorial")
    pagines = fields.Integer(string="Pàgines")
    any_publicacio = fields.Integer(string="Any de publicació")
    any = fields.Integer(
        string="Any",
        related="any_publicacio",
        store=True,
        readonly=False,
    )
    idioma = fields.Char(string="Idioma")
    nivell_recomanat = fields.Char(string="Nivell recomanat")
    portada_url = fields.Char(string="URL portada")

    categoria = fields.Char(string="Categoria")
    edat_recomanada = fields.Char(string="Edat recomanada")
    resum = fields.Text(string="Resum")

    portada_1920 = fields.Image(string="Portada")
    slug = fields.Char(string="Slug públic", copy=False, index=True)

    lectura_ids = fields.One2many(
        "joc.lector.lectura",
        "llibre_id",
        string="Lectures",
    )

    ressenya_ids = fields.One2many(
        "joc.lector.ressenya",
        "llibre_id",
        string="Ressenyes",
    )

    lectura_count = fields.Integer(
        string="Lectures acabades",
        compute="_compute_stats",
        store=True,
    )

    ressenya_count = fields.Integer(
        string="Ressenyes aprovades",
        compute="_compute_stats",
        store=True,
    )

    valoracio_mitjana = fields.Float(
        string="Valoració mitjana",
        compute="_compute_stats",
        store=True,
        digits=(16, 2),
    )

    active = fields.Boolean(default=True)

    actiu = fields.Boolean(
        string="Actiu",
        related="active",
        store=True,
        readonly=False,
    )

    _sql_constraints = [
        (
            "slug_unique",
            "unique(slug)",
            "El slug públic del llibre ha de ser únic.",
        ),
    ]

    @api.depends(
        "lectura_ids.state",
        "ressenya_ids.valoracio",
        "ressenya_ids.aprovada",
    )
    def _compute_stats(self):
        for llibre in self:
            lectures_acabades = llibre.lectura_ids.filtered(lambda l: l.state == "finished")
            ressenyes_aprovades = llibre.ressenya_ids.filtered(lambda r: r.aprovada)

            llibre.lectura_count = len(lectures_acabades)
            llibre.ressenya_count = len(ressenyes_aprovades)

            if ressenyes_aprovades:
                llibre.valoracio_mitjana = sum(ressenyes_aprovades.mapped("valoracio")) / len(ressenyes_aprovades)
            else:
                llibre.valoracio_mitjana = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.slug:
                record.slug = "%s-%s" % (slugify(record.name), record.id)
        return records
