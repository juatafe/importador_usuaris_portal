from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    qty_served = fields.Float(string="Quantitat Servida", default=0.0)
