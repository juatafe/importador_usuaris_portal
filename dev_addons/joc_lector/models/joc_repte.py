# -*- coding: utf-8 -*-

from odoo import api, fields, models


class JocLectorRepte(models.Model):
    _name = "joc.lector.repte"
    _description = "Reptes del Joc Lector"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "data_inici desc, id desc"

    name = fields.Char(string="Nom", required=True, index=True)
    descripcio = fields.Text(string="Descripció")

    centre_id = fields.Many2one("joc.lector.centre", string="Centre", ondelete="cascade")
    classe_id = fields.Many2one("joc.lector.classe", string="Classe", ondelete="cascade")

    curs_academic = fields.Char(string="Curs acadèmic")
    tipus = fields.Selection(
        [
            ("individual", "Individual"),
            ("classe", "Classe"),
            ("centre", "Centre"),
            ("global", "Global"),
            ("bingo", "Bingo lector"),
        ],
        string="Tipus",
        default="individual",
        required=True,
        index=True,
    )

    data_inici = fields.Date(string="Data inici", default=fields.Date.context_today, required=True)
    data_fi = fields.Date(string="Data fi")
    punts = fields.Integer(string="Punts", default=0)

    active = fields.Boolean(default=True)
    actiu = fields.Boolean(string="Actiu", related="active", store=True, readonly=False)
    public = fields.Boolean(string="Públic", default=False)

    llibre_ids = fields.Many2many(
        "joc.lector.llibre",
        "joc_lector_repte_llibre_rel",
        "repte_id",
        "llibre_id",
        string="Llibres del catàleg",
        help="Si s'indiquen llibres, una lectura acceptada d'un d'estos llibres pot completar el repte.",
    )
    bingo_casella_ids = fields.One2many(
        "joc.lector.repte.casella",
        "repte_id",
        string="Caselles de bingo",
    )
    participacio_ids = fields.One2many("joc.lector.repte.participacio", "repte_id", string="Participacions")

    def _matches_scope(self, lectura):
        self.ensure_one()
        if self.classe_id:
            return lectura.classe_id and lectura.classe_id.id == self.classe_id.id
        if self.centre_id:
            return lectura.centre_id and lectura.centre_id.id == self.centre_id.id
        return True

    def _is_active_for_date(self, date_value=None):
        self.ensure_one()
        today = date_value or fields.Date.context_today(self)
        return (
            self.active
            and self.data_inici <= today
            and (not self.data_fi or self.data_fi >= today)
        )

    def _book_matches(self, llibre):
        self.ensure_one()
        return bool(not self.llibre_ids or llibre in self.llibre_ids)

    @api.model
    def _active_auto_reptes_for_lectura(self, lectura):
        today = fields.Date.context_today(self)
        domain = [
            ("active", "=", True),
            ("data_inici", "<=", today),
            "|",
            ("data_fi", "=", False),
            ("data_fi", ">=", today),
            "|",
            ("classe_id", "=", lectura.classe_id.id if lectura.classe_id else False),
            "|",
            ("classe_id", "=", False),
            ("centre_id", "=", lectura.centre_id.id if lectura.centre_id else False),
        ]
        candidates = self.search(domain)
        return candidates.filtered(lambda repte: repte._matches_scope(lectura) and repte._has_auto_criteria())

    def _has_auto_criteria(self):
        self.ensure_one()
        return bool(self.llibre_ids or self.bingo_casella_ids)

    @api.model
    def apply_accepted_reading(self, lectura):
        if not lectura or lectura.estat_validacio != "acceptada" or lectura.state != "finished":
            return self.env["joc.lector.repte.participacio"].browse()

        participacions = self.env["joc.lector.repte.participacio"].browse()
        for repte in self._active_auto_reptes_for_lectura(lectura):
            participacio = self.env["joc.lector.repte.participacio"]._apply_lectura_to_repte(repte, lectura)
            if participacio:
                participacions |= participacio
        return participacions


class JocLectorRepteCasella(models.Model):
    _name = "joc.lector.repte.casella"
    _description = "Casella de bingo lector"
    _order = "repte_id, sequence, id"

    repte_id = fields.Many2one("joc.lector.repte", string="Repte", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Ordre", default=10)
    name = fields.Char(string="Nom", required=True)
    descripcio = fields.Text(string="Descripció")
    llibre_ids = fields.Many2many(
        "joc.lector.llibre",
        "joc_lector_repte_casella_llibre_rel",
        "casella_id",
        "llibre_id",
        string="Llibres acceptats",
        help="Si està buit, qualsevol llibre acceptat pot completar esta casella.",
    )

    def matches_lectura(self, lectura):
        self.ensure_one()
        return bool(not self.llibre_ids or lectura.llibre_id in self.llibre_ids)
