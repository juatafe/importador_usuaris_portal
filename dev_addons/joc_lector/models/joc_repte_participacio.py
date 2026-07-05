# -*- coding: utf-8 -*-

from odoo import api, fields, models


class JocLectorRepteParticipacio(models.Model):
    _name = "joc.lector.repte.participacio"
    _description = "Participació en reptes"
    _order = "id desc"

    repte_id = fields.Many2one("joc.lector.repte", string="Repte", required=True, ondelete="cascade")
    alumne_id = fields.Many2one("joc.lector.alumne", string="Alumne", required=True, ondelete="cascade", index=True)
    classe_id = fields.Many2one("joc.lector.classe", string="Classe", ondelete="set null", index=True)
    centre_id = fields.Many2one("joc.lector.centre", string="Centre", ondelete="set null", index=True)

    progres = fields.Float(string="Progrés", default=0.0)
    completat = fields.Boolean(string="Completat", default=False)
    data_completat = fields.Datetime(string="Data completat")

    punts_generats = fields.Integer(string="Punts generats", default=0)
    validat = fields.Boolean(string="Validat", default=False)
    lectura_ids = fields.Many2many(
        "joc.lector.lectura",
        "joc_lector_repte_participacio_lectura_rel",
        "participacio_id",
        "lectura_id",
        string="Lectures que compten",
    )
    bingo_casella_ids = fields.Many2many(
        "joc.lector.repte.casella",
        "joc_lector_repte_participacio_casella_rel",
        "participacio_id",
        "casella_id",
        string="Caselles completades",
    )

    _sql_constraints = [
        (
            "joc_lector_repte_participacio_unique",
            "unique(repte_id, alumne_id)",
            "L'alumne ja participa en este repte.",
        ),
    ]

    def action_marcar_completat(self):
        for record in self:
            if record.completat:
                continue
            record.write({
                "completat": True,
                "data_completat": fields.Datetime.now(),
                "punts_generats": record.repte_id.punts,
                "validat": True,
            })
            self.env["joc.lector.punts.moviment"].create_from_repte_participacio(record)
            record._notify_repte_completed()

    def _notify_repte_completed(self):
        for record in self:
            repte = record.repte_id
            partners = record.classe_id.professor_joc_ids.mapped("user_id.partner_id")
            partners |= record.classe_id.professor_ids.mapped("partner_id")
            if not partners and record.centre_id:
                professors = self.env["joc.lector.professor"].sudo().search([
                    ("centre_id", "=", record.centre_id.id),
                    ("active", "=", True),
                ])
                partners = professors.mapped("user_id.partner_id")
            body = (
                "<p><strong>%s</strong> ha completat el repte <strong>%s</strong>.</p>"
                "<p>Punts atorgats: <strong>%s</strong>.</p>"
            ) % (
                record.alumne_id.display_name,
                repte.display_name,
                record.punts_generats,
            )
            repte.message_post(
                body=body,
                subject="Repte completat: %s" % repte.display_name,
                partner_ids=partners.ids,
            )

    @staticmethod
    def _progress_percent(done, total):
        if not total:
            return 0.0
        return min(100.0, (float(done) / float(total)) * 100.0)

    def _apply_bingo_lectura(self, lectura):
        self.ensure_one()
        if lectura in self.lectura_ids:
            return False

        pending = (self.repte_id.bingo_casella_ids - self.bingo_casella_ids).sorted(key=lambda c: (c.sequence, c.id))
        casella = next((cell for cell in pending if cell.matches_lectura(lectura)), False)
        if not casella:
            return False

        self.write({
            "lectura_ids": [(4, lectura.id)],
            "bingo_casella_ids": [(4, casella.id)],
            "progres": self._progress_percent(len(self.bingo_casella_ids) + 1, len(self.repte_id.bingo_casella_ids)),
        })
        return len(self.bingo_casella_ids) >= len(self.repte_id.bingo_casella_ids)

    def _apply_book_lectura(self, lectura):
        self.ensure_one()
        if lectura in self.lectura_ids or not self.repte_id._book_matches(lectura.llibre_id):
            return False
        self.write({
            "lectura_ids": [(4, lectura.id)],
            "progres": 100.0,
        })
        return True

    @api.model
    def _apply_lectura_to_repte(self, repte, lectura):
        participacio = self.search([
            ("repte_id", "=", repte.id),
            ("alumne_id", "=", lectura.alumne_id.id),
        ], limit=1)
        if not participacio:
            participacio = self.create({
                "repte_id": repte.id,
                "alumne_id": lectura.alumne_id.id,
                "classe_id": lectura.classe_id.id if lectura.classe_id else False,
                "centre_id": lectura.centre_id.id if lectura.centre_id else False,
            })

        if participacio.completat:
            return participacio

        completed = (
            participacio._apply_bingo_lectura(lectura)
            if repte.bingo_casella_ids
            else participacio._apply_book_lectura(lectura)
        )
        if completed:
            participacio.action_marcar_completat()
        return participacio
