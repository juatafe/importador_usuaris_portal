# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


MAX_CLASSES_PER_PROFESSOR = 10
MAX_PROFESSORS_PER_CENTRE = 150


class JocLectorProfessor(models.Model):
    _name = "joc.lector.professor"
    _description = "Professorat del Joc Lector"
    _order = "name"

    name = fields.Char(string="Nom", required=True, index=True)
    user_id = fields.Many2one(
        "res.users",
        string="Usuari Odoo",
        required=True,
        ondelete="restrict",
        index=True,
    )
    centre_id = fields.Many2one(
        "joc.lector.centre",
        string="Centre",
        required=True,
        ondelete="restrict",
        index=True,
    )
    rol = fields.Selection(
        [
            ("admin_sistema", "Admin sistema"),
            ("admin_centre", "Admin centre"),
            ("professor", "Professor"),
        ],
        string="Rol",
        default="professor",
        required=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    actiu = fields.Boolean(
        string="Actiu",
        related="active",
        store=True,
        readonly=False,
    )

    classe_ids = fields.Many2many(
        "joc.lector.classe",
        "joc_lector_professor_classe_rel",
        "professor_id",
        "classe_id",
        string="Classes assignades",
    )

    centre_history_ids = fields.One2many(
        "joc.lector.professor.centre",
        "professor_id",
        string="Historic centres",
    )

    _sql_constraints = [
        (
            "joc_lector_professor_user_centre_unique",
            "unique(user_id, centre_id)",
            "Ja existix un perfil de professor per a este usuari en este centre.",
        ),
    ]

    @api.constrains("active", "centre_id")
    def _check_active_professor_has_centre(self):
        for record in self:
            if record.active and not record.centre_id:
                raise ValidationError("No pot existir professorat actiu sense centre assignat.")

    @api.constrains("active", "centre_id", "classe_ids")
    def _check_joc_lector_limits(self):
        Classe = self.env["joc.lector.classe"].sudo()
        for record in self:
            if record.active:
                class_count = Classe.search_count([
                    ("active", "=", True),
                    "|",
                    ("professor_joc_ids", "in", record.id),
                    ("professor_ids", "in", record.user_id.id),
                ])
                if class_count > MAX_CLASSES_PER_PROFESSOR:
                    raise ValidationError(
                        "Un professor no pot tindre més de %s classes actives assignades."
                        % MAX_CLASSES_PER_PROFESSOR
                    )

            if not record.active or not record.centre_id:
                continue

            active_count = self.search_count([
                ("centre_id", "=", record.centre_id.id),
                ("active", "=", True),
                ("id", "!=", record.id),
            ])
            if active_count >= MAX_PROFESSORS_PER_CENTRE:
                raise ValidationError(
                    "El centre %s ja té %s professors actius. No es poden superar %s professors per centre."
                    % (record.centre_id.display_name, active_count, MAX_PROFESSORS_PER_CENTRE)
                )
