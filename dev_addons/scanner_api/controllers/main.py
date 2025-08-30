import logging
import datetime
import secrets
import json

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class ScannerAPI(http.Controller):

    # ------------------------------
    # LOGIN
    # ------------------------------
    @http.route('/scanner/api/login', type='json', auth='public', methods=['POST'], csrf=False)
    def login(self, **kw):
        try:
            body = request.httprequest.get_data(as_text=True) or "{}"
            data = json.loads(body) if body.strip().startswith("{") else {}
        except Exception:
            data = {}

        user = data.get("user") or kw.get("user")
        password = data.get("password") or kw.get("password")

        _logger.info("[scanner_api] login -> user=%s", user)

        if not user or not password:
            return {"error": "Missing credentials"}

        try:
            uid = request.session.authenticate(request.session.db, user, password)
        except Exception as e:
            _logger.warning("[scanner_api] login failed: %s", e)
            return {"error": "Invalid credentials"}

        if not uid:
            return {"error": "Invalid credentials"}

        # Generar token temporal
        token_value = secrets.token_hex(32)
        expires = fields.Datetime.now() + datetime.timedelta(hours=1)

        request.env["scanner.api.token"].sudo().create({
            "user_id": uid,
            "token": token_value,
            "expires": expires,
        })

        return {"token": token_value, "expires": expires.isoformat()}

    # ------------------------------
    # VALIDACIÓ TOKEN
    # ------------------------------
    def _check_token(self):
        hdr = request.httprequest.headers.get("Authorization")
        if not hdr or not hdr.startswith("Bearer "):
            return None

        token_value = hdr.split(" ", 1)[1]
        token_rec = request.env["scanner.api.token"].sudo().search([
            ("token", "=", token_value),
            ("active", "=", True),
        ], limit=1)

        if not token_rec or not token_rec.is_valid():
            return None
        return token_rec.user_id.id

    # ------------------------------
    # PING
    # ------------------------------
    @http.route('/scanner/api/ping', type='json', auth='public', methods=['POST'], csrf=False)
    def ping(self, **kw):
        uid = self._check_token()
        if not uid:
            return {"error": "Unauthorized"}
        return {"status": "ok", "uid": uid}

    # ------------------------------
    # CHECK BARCODE
    # ------------------------------
    @http.route('/scanner/api/check', type='json', auth='public', methods=['POST'], csrf=False)
    def check_code(self, **kw):
        uid = self._check_token()
        if not uid:
            return {"error": "Unauthorized"}

        try:
            body = request.httprequest.get_data(as_text=True) or "{}"
            data = json.loads(body) if body.strip().startswith("{") else {}
        except Exception:
            data = {}

        barcode = data.get("barcode") or kw.get("barcode")
        if not barcode:
            return {"error": "No barcode provided"}

        partner = request.env['res.partner'].sudo().search([('barcode_ean13', '=', barcode)], limit=1)
        if not partner:
            return {"error": "Contacte no trobat"}

        return {"partner": {"id": partner.id, "name": partner.name}}

    @http.route('/scanner/api/logout', type='json', auth='public', methods=['POST'], csrf=False)
    def logout(self, **kw):
        uid = self._check_token()
        if not uid:
            return {"error": "Unauthorized"}

        hdr = request.httprequest.headers.get("Authorization")
        token_value = hdr.split(" ", 1)[1]
        token_rec = request.env["scanner.api.token"].sudo().search([("token", "=", token_value)], limit=1)
        if token_rec:
            token_rec.write({"active": False})

        return {"status": "logged_out"}

    @http.route('/scanner/api/test', type='json', auth='public', methods=['POST'], csrf=False)
    def test_endpoint(self, **kw):
        return {"status": "ok"}


    # ------------------------------
    # GET TICKETS
    # ------------------------------

    @http.route('/scanner/api/tickets', type='json', auth='public', methods=['POST'], csrf=False)
    def get_tickets(self, **kw):
        uid = self._check_token()
        if not uid:
            return {"error": "Unauthorized"}

        try:
            body = request.httprequest.get_data(as_text=True) or "{}"
            data = json.loads(body) if body.strip().startswith("{") else {}
        except Exception:
            data = {}

        partner_id = data.get("partner_id") or kw.get("partner_id")
        event_id   = data.get("event_id") or kw.get("event_id")

        if not partner_id:
            return {"error": "Missing partner_id"}

        partner = request.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists():
            return {"error": "Partner not found"}

        # 🔑 Obtenir tots els membres de la família a través de familia.miembro
        member = request.env['familia.miembro'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        if member and member.familia_id:
            family_members = member.familia_id.miembros_ids.mapped('partner_id')
        else:
            family_members = partner  # si no té família, sols ell

        # 1) Busca comandes confirmades (no draft, no cancel)
        domain = [
            ('partner_id', 'in', family_members.ids),
            ('state', '=', 'sale'),
        ]
        if event_id:
            domain.append(('event_id', '=', int(event_id)))

        orders = request.env['sale.order'].sudo().search(domain)

        tickets = []
        for order in orders:
            for line in order.order_line:
                if not line.product_id:
                    continue
                if line.product_id.detailed_type != 'event':
                    continue

                total = int(line.product_uom_qty)
                served = int(line.qty_served or 0)

                tickets.append({
                    "type": f"line:{line.id}",
                    "name": line.product_id.display_name,
                    "total": total,
                    "served": served,
                    "remaining": max(total - served, 0),
                    "order_partner": order.partner_id.name,
                    "event": order.event_id.name if hasattr(order, "event_id") and order.event_id else None,
                })

        return {
            "partner": {"id": partner.id, "name": partner.name},
            "tickets": tickets
        }


    @http.route('/scanner/api/serve', type='json', auth='public', methods=['POST'], csrf=False)
    def serve_ticket(self, **kw):
        uid = self._check_token()
        if not uid:
            return {"error": "Unauthorized"}

        try:
            body = request.httprequest.get_data(as_text=True) or "{}"
            data = json.loads(body) if body.strip().startswith("{") else {}
        except Exception:
            data = {}

        line_id = data.get("line_id")
        qty = float(data.get("qty") or 1.0)

        if not line_id:
            return {"error": "Missing line_id"}

        line = request.env['sale.order.line'].sudo().browse(int(line_id))
        if not line.exists():
            return {"error": "Line not found"}

        order = line.order_id

        # Incrementar quantitat servida
        line.sudo().write({
            "qty_served": line.qty_served + qty
        })

        # Crear log de servei
        request.env['scanner.ticket.service'].sudo().create({
            "partner_id": order.partner_id.id,
            "event_id": order.event_id.id if order.event_id else False,
            "ticket_key": f"l:{line.id}",
            "qty": qty,
            "order_id": order.id,
            "line_id": line.id,
        })

        # Comprovar si totes les línies estan completades
        all_served = all(l.qty_served >= l.product_uom_qty for l in order.order_line)
        if all_served:
            order.sudo().write({"state": "done"})

        return {
            "status": "ok",
            "order_id": order.id,
            "line_id": line.id,
            "qty_served": line.qty_served,
            "pending": max(0, line.product_uom_qty - line.qty_served),
            "order_state": order.state,
        }


    # dins ScannerAPI
    @http.route('/scanner/api/events', type='json', auth='public', methods=['POST'], csrf=False)
    def get_events(self, **kw):
        uid = self._check_token()
        if not uid:
            return {"error": "Unauthorized"}

        Event = request.env['event.event'].sudo()
        now = fields.Datetime.now()

        # 🔹 Només filtrem per dates (actius en aquest moment)
        events = Event.search([
            ('date_begin', '<=', now),
            ('date_end', '>=', now),
        ])

        result = []
        for ev in events:
            # 👇 Evitem error si no té camp 'state'
            state = getattr(ev, 'state', None)
            _logger.info(f"[scanner_api] Event {ev.id} '{ev.name}' → state={state}")

            result.append({
                "id": ev.id,
                "name": ev.name,
                "date_begin": ev.date_begin,
                "date_end": ev.date_end,
                "state": state,   # pot ser None
            })

        return {"events": result}
