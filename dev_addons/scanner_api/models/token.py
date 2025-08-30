from odoo import models, fields

class ScannerApiToken(models.Model):
    _name = "scanner.api.token"
    _description = "Scanner API Token"
    _rec_name = "user_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    token = fields.Char(required=True, index=True)
    expires = fields.Datetime(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("token_unique", "unique(token)", "Token must be unique."),
    ]

    def is_valid(self):
        """Check if token is still valid"""
        now = fields.Datetime.now()
        return self.active and self.expires > now

    def cleanup_tokens(self):
        """Desactiva tokens caducats"""
        expired = self.search([("expires", "<", fields.Datetime.now()), ("active", "=", True)])
        expired.write({"active": False})
