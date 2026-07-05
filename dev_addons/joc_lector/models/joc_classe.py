# -*- coding: utf-8 -*-

import secrets
import unicodedata

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError


MAX_CLASSES_PER_PROFESSOR = 10


class JocLectorClasse(models.Model):
    _name = "joc.lector.classe"
    _description = "Classe del Joc Lector"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "curs_academic desc, name"

    name = fields.Char(string="Nom de la classe", required=True, tracking=True)
    nom_normalitzat = fields.Char(string="Nom normalitzat", readonly=True, index=True, copy=False)

    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        ondelete="restrict",
        tracking=True,
    )

    curs_academic = fields.Char(
        string="Curs acadèmic",
        required=True,
        default="2026-2027",
        tracking=True,
    )
    curs_grup = fields.Char(string="Curs/grup", tracking=True)
    curs_grup_normalitzat = fields.Char(string="Curs/grup normalitzat", readonly=True, index=True, copy=False)

    access_code = fields.Char(
        string="Codi d'entrada",
        required=True,
        copy=False,
        default=lambda self: self._generate_unique_access_code(),
        tracking=True,
    )

    codi_acces = fields.Char(
        string="Codi d'accés",
        related="access_code",
        store=True,
        readonly=False,
    )

    nivell = fields.Char(string="Nivell")

    professor_ids = fields.Many2many(
        "res.users",
        string="Professorat",
    )

    professor_joc_ids = fields.Many2many(
        "joc.lector.professor",
        "joc_lector_professor_classe_rel",
        "classe_id",
        "professor_id",
        string="Professorat (perfils Joc Lector)",
    )

    matricula_ids = fields.One2many(
        "joc.lector.matricula",
        "classe_id",
        string="Matrícules",
    )

    alumne_count = fields.Integer(
        string="Nombre d'alumnes",
        compute="_compute_alumne_count",
    )

    active = fields.Boolean(default=True)

    activa = fields.Boolean(
        string="Activa",
        related="active",
        store=True,
        readonly=False,
    )

    ranking_classe_actiu = fields.Boolean(string="Rànquing classe actiu", default=False)

    _sql_constraints = [
        (
            "access_code_unique",
            "unique(access_code)",
            "El codi d'entrada ha de ser únic.",
        ),
        (
            "joc_lector_classe_centre_nom_curs_grup_unique",
            "unique(centre_id, nom_normalitzat, curs_grup_normalitzat)",
            "Ja existix una classe amb este nom i curs/grup en el centre.",
        ),
    ]

    @api.model
    def _normalize_key(self, value):
        text = str(value or "").strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return " ".join(text.split())

    @api.model
    def _generate_short_code(self, size=5):
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(alphabet) for _ in range(size))

    @api.model
    def _generate_unique_access_code(self):
        for _attempt in range(50):
            code = "JL-" + self._generate_short_code(6)
            if not self.sudo().search_count([("access_code", "=", code)]):
                return code
        return "JL-" + secrets.token_hex(5).upper()

    @api.model
    def _normalized_vals(self, vals):
        vals = dict(vals)
        name = vals.get("name")
        curs_grup = vals.get("curs_grup")
        if not curs_grup:
            curs_grup = vals.get("curs_academic")
            if curs_grup and "curs_grup" not in vals:
                vals["curs_grup"] = curs_grup
        if name is not None:
            vals["nom_normalitzat"] = self._normalize_key(name)
        if curs_grup is not None:
            vals["curs_grup_normalitzat"] = self._normalize_key(curs_grup)
        return vals

    @api.model
    def _with_alternative_name_if_needed(self, vals):
        vals = self._normalized_vals(vals)
        if not vals.get("centre_id") or not vals.get("nom_normalitzat") or not vals.get("curs_grup_normalitzat"):
            return vals

        exists = self.sudo().search_count([
            ("centre_id", "=", vals["centre_id"]),
            ("nom_normalitzat", "=", vals["nom_normalitzat"]),
            ("curs_grup_normalitzat", "=", vals["curs_grup_normalitzat"]),
        ])
        if exists:
            vals["name"] = "%s %s" % (vals["name"], self._generate_short_code(5))
            vals = self._normalized_vals(vals)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for vals in vals_list:
            base_vals = self._with_alternative_name_if_needed(vals)
            for _attempt in range(50):
                candidate = dict(base_vals)
                if not candidate.get("access_code"):
                    candidate["access_code"] = self._generate_unique_access_code()
                try:
                    with self.env.cr.savepoint():
                        records |= super(JocLectorClasse, self).create([candidate])
                    break
                except IntegrityError:
                    base_vals["access_code"] = self._generate_unique_access_code()
                    base_vals["name"] = "%s %s" % (vals.get("name") or base_vals.get("name"), self._generate_short_code(5))
                    base_vals = self._normalized_vals(base_vals)
            else:
                raise ValidationError("No s'ha pogut generar una classe amb nom i codi únics.")
        records._check_professor_assignment_limits()
        return records

    def write(self, vals):
        vals = dict(vals)
        for record in self:
            record_vals = dict(vals)
            if "name" in vals:
                record_vals["nom_normalitzat"] = self._normalize_key(vals.get("name"))
            if "curs_grup" in vals or "curs_academic" in vals:
                curs_grup = vals.get("curs_grup") or record.curs_grup or vals.get("curs_academic") or record.curs_academic
                record_vals["curs_grup_normalitzat"] = self._normalize_key(curs_grup)
                if "curs_grup" not in record_vals and vals.get("curs_academic") and not record.curs_grup:
                    record_vals["curs_grup"] = vals.get("curs_academic")
            super(JocLectorClasse, record).write(record_vals)
        self._check_professor_assignment_limits()
        return True

    def _check_professor_assignment_limits(self):
        professors = self.mapped("professor_joc_ids")
        for professor in professors:
            class_count = self.search_count([
                ("active", "=", True),
                "|",
                ("professor_joc_ids", "in", professor.id),
                ("professor_ids", "in", professor.user_id.id),
            ])
            if class_count > MAX_CLASSES_PER_PROFESSOR:
                raise ValidationError(
                    "El professor %s ja té %s classes assignades. El màxim és %s."
                    % (professor.display_name, class_count, MAX_CLASSES_PER_PROFESSOR)
                )

        for user in self.mapped("professor_ids"):
            class_count = self.search_count([
                ("active", "=", True),
                "|",
                ("professor_ids", "in", user.id),
                ("professor_joc_ids.user_id", "=", user.id),
            ])
            if class_count > MAX_CLASSES_PER_PROFESSOR:
                raise ValidationError(
                    "El professor %s ja té %s classes assignades. El màxim és %s."
                    % (user.display_name, class_count, MAX_CLASSES_PER_PROFESSOR)
                )

    @api.depends("matricula_ids", "matricula_ids.state")
    def _compute_alumne_count(self):
        for record in self:
            record.alumne_count = len(record.matricula_ids.filtered(lambda m: m.state == "active"))
