# -*- coding: utf-8 -*-

from odoo import api, fields, models


class JocLectorLectura(models.Model):
    _name = "joc.lector.lectura"
    _description = "Lectura d'un llibre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

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

    classe_id = fields.Many2one(
        "joc.lector.classe",
        string="Classe",
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
            ("pending", "Pendent"),
            ("reading", "Llegint"),
            ("finished", "Acabada"),
            ("abandoned", "Abandonada"),
        ],
        string="Estat",
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )

    estat = fields.Selection(
        string="Estat (app)",
        related="state",
        store=True,
        readonly=False,
    )

    valoracio = fields.Integer(string="Valoració")
    ressenya = fields.Text(string="Ressenya")
    evidencia_url = fields.Char(string="Evidència URL")
    evidencia_text = fields.Text(string="Evidència text")
    visible_publicament = fields.Boolean(string="Visible públicament", default=False)

    estat_validacio = fields.Selection(
        [
            ("pendent", "Pendent"),
            ("cal_completar", "Cal completar"),
            ("acceptada", "Acceptada"),
            ("no_acceptada", "No acceptada"),
        ],
        string="Estat validació",
        default="pendent",
        required=True,
        index=True,
        tracking=True,
    )

    professor_validador_id = fields.Many2one(
        "joc.lector.professor",
        string="Professor validador",
        ondelete="set null",
    )

    data_validacio = fields.Datetime(string="Data validació")
    punts_generats = fields.Integer(string="Punts generats", default=0)
    client_uid = fields.Char(string="Client UID", index=True, copy=False)

    punts_obtinguts = fields.Integer(
        string="Punts obtinguts",
        default=10,
    )

    points_applied = fields.Boolean(
        string="Punts aplicats al passaport",
        default=False,
        copy=False,
        readonly=True,
    )

    notes = fields.Text(string="Notes internes")

    ressenya_ids = fields.One2many(
        "joc.lector.ressenya",
        "lectura_id",
        string="Ressenyes",
    )

    _sql_constraints = [
        (
            "joc_lector_lectura_client_uid_unique",
            "unique(client_uid)",
            "El client_uid de lectura ha de ser únic.",
        ),
    ]

    @api.onchange("alumne_id")
    def _onchange_alumne_id(self):
        for record in self:
            if record.alumne_id and not record.classe_id:
                record.classe_id = record.alumne_id.current_classe_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("alumne_id") and not vals.get("classe_id"):
                alumne = self.env["joc.lector.alumne"].browse(vals["alumne_id"])
                if alumne.current_classe_id:
                    vals["classe_id"] = alumne.current_classe_id.id

        records = super().create(vals_list)
        records._apply_passaport_rewards_if_needed()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_lectura_rewards"):
            self._apply_passaport_rewards_if_needed()
        return result

    def _get_or_create_passaport(self):
        self.ensure_one()
        Passaport = self.env["joc.lector.passaport"]
        passaport = Passaport.search([("alumne_id", "=", self.alumne_id.id)], limit=1)
        if not passaport:
            passaport = Passaport.create({"alumne_id": self.alumne_id.id})
        return passaport

    def _apply_passaport_rewards_if_needed(self):
        today = fields.Date.context_today(self)

        for lectura in self:
            if lectura.state != "finished" or lectura.points_applied:
                continue

            if lectura.estat_validacio != "acceptada":
                continue

            passaport = lectura._get_or_create_passaport()
            punts_nous = passaport.punts + lectura.punts_obtinguts
            nivell_nou = max(1, (punts_nous // 100) + 1)

            passaport.write({
                "punts": punts_nous,
                "nivell": nivell_nou,
                "llibres_llegits": passaport.llibres_llegits + 1,
            })

            vals = {"points_applied": True}
            if not lectura.date_end:
                vals["date_end"] = today

            lectura.with_context(skip_lectura_rewards=True).write(vals)

    def _compute_validation_points(self):
        self.ensure_one()
        points = 0
        if self.state == "finished":
            points += 30
        if self.ressenya and str(self.ressenya).strip():
            points += 20
        if self.valoracio:
            points += 5
        return points

    def action_validar_per_professor(self, professor, decisio, visible_publicament=False, comentari=None):
        self.ensure_one()

        valid_decisions = {"acceptada", "cal_completar", "no_acceptada"}
        if decisio not in valid_decisions:
            raise ValueError("Decisió de validació no vàlida")

        vals = {
            "estat_validacio": decisio,
            "professor_validador_id": professor.id if professor else False,
            "data_validacio": fields.Datetime.now(),
            "visible_publicament": bool(visible_publicament),
        }

        if comentari:
            note = (self.notes or "").strip()
            if note:
                note += "\n\n"
            vals["notes"] = f"{note}{comentari}"

        if decisio == "acceptada":
            points = self._compute_validation_points()
            vals["punts_generats"] = points
            vals["punts_obtinguts"] = points
            vals["state"] = "finished"
        else:
            vals["punts_generats"] = 0

        self.write(vals)

        if decisio == "acceptada":
            self._sync_approved_review_from_reading(visible_publicament=visible_publicament)
            self.env["joc.lector.punts.moviment"].create_from_lectura(self)
            self.env["joc.lector.repte"].apply_accepted_reading(self)

        return True

    def _sync_approved_review_from_reading(self, visible_publicament=False):
        self.ensure_one()
        text = (self.ressenya or "").strip()
        if not text:
            return False

        Ressenya = self.env["joc.lector.ressenya"].sudo()
        ressenya = Ressenya.search([
            ("lectura_id", "=", self.id),
            ("active", "=", True),
        ], limit=1)

        vals = {
            "alumne_id": self.alumne_id.id,
            "llibre_id": self.llibre_id.id,
            "lectura_id": self.id,
            "classe_id": self.classe_id.id if self.classe_id else False,
            "text": text,
            "valoracio": self.valoracio or 5,
            "publicable": bool(visible_publicament),
            "aprovada": True,
        }

        if ressenya:
            ressenya.write(vals)
            return ressenya
        return Ressenya.create(vals)
