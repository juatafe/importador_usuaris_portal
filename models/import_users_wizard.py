from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import pandas as pd
import io
import hashlib

class ImportUsersWizard(models.TransientModel):
    _name = 'import.users.wizard'
    _description = 'Importar usuaris del portal des d\'Excel'

    file = fields.Binary(string="Fitxer Excel", required=True)
    filename = fields.Char(string="Nom del fitxer")

    def action_import_users(self):
        if not self.file:
            raise UserError(_("Cal seleccionar un fitxer Excel."))

        data = base64.b64decode(self.file)
        df = pd.read_excel(io.BytesIO(data))

        # Validació mínima
        required_cols = ['CodFaller', 'MAIL', 'DNI']
        for col in required_cols:
            if col not in df.columns:
                raise UserError(_("Falta la columna requerida: %s") % col)

        users_created = 0
        users_skipped = 0
        for _, row in df.iterrows():
            codifaller = row['CodFaller']
            email = row['MAIL']
            vat = row['DNI']

            if not email:
                continue

            xml_id = f"res_partner_faller_{int(codifaller):04d}"
            partner = self.env['res.partner'].search([('id', '=', xml_id)], limit=1)
            if not partner:
                continue

            existing_user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
            if existing_user:
                users_skipped += 1
                continue

            self.env['res.users'].create({
                'login': email.strip(),
                'password': hashlib.sha256(str(vat).encode()).hexdigest()[:10] if vat else '',
                'partner_id': partner.id,
                'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
                'active': True,
            })
            users_created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Importació completada"),
                'message': _("Usuaris creats: %d | Ja existien: %d") % (users_created, users_skipped),
                'type': 'success',
                'sticky': False,
            }
        }
