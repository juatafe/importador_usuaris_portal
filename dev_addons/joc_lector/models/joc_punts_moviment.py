# -*- coding: utf-8 -*-

from odoo import api, fields, models


class JocLectorPuntsMoviment(models.Model):
    _name = "joc.lector.punts.moviment"
    _description = "Moviments de punts"
    _order = "data desc, id desc"

    alumne_id = fields.Many2one("joc.lector.alumne", string="Alumne", required=True, ondelete="cascade", index=True)
    classe_id = fields.Many2one("joc.lector.classe", string="Classe", ondelete="set null", index=True)
    centre_id = fields.Many2one("joc.lector.centre", string="Centre", ondelete="set null", index=True)

    origen = fields.Selection(
        [
            ("lectura", "Lectura"),
            ("repte", "Repte"),
            ("ajust_manual", "Ajust manual"),
        ],
        string="Origen",
        required=True,
        index=True,
    )

    lectura_id = fields.Many2one("joc.lector.lectura", string="Lectura", ondelete="set null")
    repte_id = fields.Many2one("joc.lector.repte", string="Repte", ondelete="set null")

    punts = fields.Integer(string="Punts", required=True, default=0)
    motiu = fields.Char(string="Motiu")
    data = fields.Datetime(string="Data", default=fields.Datetime.now, required=True, index=True)
    curs_academic = fields.Char(string="Curs acadèmic")

    _sql_constraints = [
        (
            "joc_lector_punts_lectura_unique",
            "unique(lectura_id)",
            "Ja existix un moviment de punts per a esta lectura.",
        ),
    ]

    @api.model
    def _refresh_passaport(self, alumne):
        passaport = self.env["joc.lector.passaport"].search([("alumne_id", "=", alumne.id)], limit=1)
        if not passaport:
            passaport = self.env["joc.lector.passaport"].create({"alumne_id": alumne.id})

        total = sum(self.search([("alumne_id", "=", alumne.id)]).mapped("punts"))
        llibres = self.search_count([
            ("alumne_id", "=", alumne.id),
            ("origen", "=", "lectura"),
            ("punts", ">", 0),
        ])
        nivell = max(1, (total // 100) + 1)

        passaport.write({
            "punts": total,
            "nivell": nivell,
            "llibres_llegits": llibres,
        })
        return passaport

    @api.model
    def create_from_lectura(self, lectura):
        existing = self.search([("lectura_id", "=", lectura.id)], limit=1)
        if existing:
            return existing

        movement = self.create({
            "alumne_id": lectura.alumne_id.id,
            "classe_id": lectura.classe_id.id if lectura.classe_id else False,
            "centre_id": lectura.centre_id.id if lectura.centre_id else False,
            "origen": "lectura",
            "lectura_id": lectura.id,
            "punts": lectura.punts_generats,
            "motiu": "Validació lectura acceptada",
            "curs_academic": lectura.curs_academic,
        })

        self._refresh_passaport(lectura.alumne_id)
        return movement

    @api.model
    def create_from_repte_participacio(self, participacio):
        movement = self.create({
            "alumne_id": participacio.alumne_id.id,
            "classe_id": participacio.classe_id.id if participacio.classe_id else False,
            "centre_id": participacio.centre_id.id if participacio.centre_id else False,
            "origen": "repte",
            "repte_id": participacio.repte_id.id,
            "punts": participacio.punts_generats,
            "motiu": "Repte completat",
            "curs_academic": participacio.repte_id.curs_academic,
        })

        self._refresh_passaport(participacio.alumne_id)
        return movement
