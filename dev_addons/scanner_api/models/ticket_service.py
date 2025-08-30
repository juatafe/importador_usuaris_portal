from odoo import models, fields

class ScannerTicketService(models.Model):
    _name = "scanner.ticket.service"
    _description = "Log de tiquets servits"
    _order = "create_date desc"

    partner_id = fields.Many2one("res.partner", required=True, index=True)
    event_id   = fields.Many2one("event.event")
    ticket_key = fields.Char(required=True, index=True)  # p.ex. "et:12" o "p:57"
    qty        = fields.Integer(default=0)
    user_id    = fields.Many2one("res.users", default=lambda s: s.env.user, required=True)
    order_id   = fields.Many2one("sale.order")
    line_id    = fields.Many2one("sale.order.line")
    date       = fields.Datetime(default=fields.Datetime.now)
