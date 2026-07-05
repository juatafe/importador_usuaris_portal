# -*- coding: utf-8 -*-

import base64
import html
import json
import logging

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import Response, request


JOC_LECTOR_EMAIL_FROM = "Joc Lector <joc-lector@provestalens.es>"
MAX_ALUMNES_PER_CLASSE = 40
MAX_CLASSES_PER_PROFESSOR = 10
_logger = logging.getLogger(__name__)


class JocLectorApiV2Controller(http.Controller):
    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False, default=str),
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def _payload(self):
        raw = request.httprequest.data or b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _param(self, name, default=None):
        body = self._payload()
        return request.params.get(name) or body.get(name) or default

    def _param_raw(self, name, default=None):
        body = self._payload()
        if name in request.params:
            return request.params.get(name)
        if name in body:
            return body.get(name)
        return default

    def _has_param(self, name):
        body = self._payload()
        return name in request.params or name in body

    def _error(self, code, message, status=400):
        return self._json({"ok": False, "error": {"code": code, "message": message}}, status=status)

    def _item_get(self, item, aliases, default=None):
        for key in aliases:
            if key in item and item.get(key) not in (None, ""):
                return item.get(key)
        return default

    def _student_list_aliases(self):
        return (
            "alumnes",
            "alumnat",
            "students",
            "student_names",
            "studentNames",
            "noms",
            "alumnos",
            "estudiants",
            "lectors",
            "lectores",
            "readers",
            "pupils",
            "participants",
            "codis",
            "codis_lectura",
            "codisLectura",
            "reading_codes",
            "readingCodes",
            "student_codes",
            "studentCodes",
            "local_students",
            "localStudents",
        )

    def _student_list_param(self, default=None):
        aliases = self._student_list_aliases()
        for alias in aliases:
            value = self._param_raw(alias)
            if value not in (None, ""):
                return value

        body = self._payload()
        containers = ("classe", "class", "group", "grup", "data", "payload", "body", "request")
        for container in containers:
            nested = body.get(container) if isinstance(body, dict) else None
            if not isinstance(nested, dict):
                continue
            for alias in aliases:
                value = nested.get(alias)
                if value not in (None, ""):
                    return value
        return [] if default is None else default

    def _coerce_student_list(self, raw_alumnes):
        if isinstance(raw_alumnes, dict):
            for alias in self._student_list_aliases() + ("items", "values", "records", "rows", "list"):
                value = raw_alumnes.get(alias)
                if value not in (None, ""):
                    return self._coerce_student_list(value)
            return list(raw_alumnes.values())
        return raw_alumnes

    def _student_name_from_item(self, item):
        if isinstance(item, dict):
            explicit_name = (
                self._item_get(
                    item,
                    [
                        "name",
                        "nom",
                        "nom_visible",
                        "nomVisible",
                        "display_name",
                        "displayName",
                        "full_name",
                        "fullName",
                        "nom_complet",
                        "nomComplet",
                        "student_name",
                        "studentName",
                        "lector",
                        "alias",
                        "label",
                        "title",
                        "usuari",
                        "user",
                        "username",
                    ],
                )
                or ""
            ).strip()
            if explicit_name:
                return explicit_name

            id_llista = (self._item_get(item, ["idLlista", "studentLocalId", "localListId"]) or "").strip()
            animal = (self._item_get(item, ["animal", "alias"]) or "").strip()
            if id_llista and animal:
                return "%s · %s" % (id_llista, animal)
            return id_llista or animal or self._student_code_from_item(item)
        return str(item or "").strip()

    def _student_code_from_item(self, item):
        if not isinstance(item, dict):
            return ""
        return (
            self._item_get(
                item,
                [
                    "codi_alumne",
                    "codiAlumne",
                    "student_code",
                    "studentCode",
                    "codiAcces",
                    "accessCode",
                    "code",
                    "codi",
                    "codigo",
                    "credential",
                    "credencial",
                    "reading_code",
                    "readingCode",
                    "codi_lectura",
                    "codiLectura",
                ],
            )
            or ""
        ).strip().upper()

    def _student_app_uid_from_item(self, item):
        if not isinstance(item, dict):
            return ""
        return (
            self._item_get(
                item,
                [
                    "app_uid",
                    "appUid",
                    "uid",
                    "uuid",
                    "local_id",
                    "localId",
                    "client_uid",
                    "clientUid",
                    "id_local",
                    "idLocal",
                ],
            )
            or ""
        ).strip()

    def _student_create_vals_from_item(self, item):
        vals = {"name": self._student_name_from_item(item)}
        code = self._student_code_from_item(item)
        app_uid = self._student_app_uid_from_item(item)
        if code:
            vals["codi_alumne"] = code
        if app_uid:
            vals["app_uid"] = app_uid
        return vals

    def _student_count_param(self):
        value = (
            self._param("nombre_alumnes")
            or self._param("num_alumnes")
            or self._param("alumne_count")
            or self._param("students_count")
            or self._param("studentCount")
            or 0
        )
        try:
            return max(0, int(value))
        except Exception:
            return 0

    def _generated_student_items(self, count):
        return [
            {
                "name": "id%s" % str(index).zfill(2),
            }
            for index in range(1, count + 1)
        ]

    def _payload_keys_summary(self):
        body = self._payload()
        if not isinstance(body, dict):
            return []
        keys = sorted(body.keys())
        nested = []
        for key, value in body.items():
            if isinstance(value, dict):
                nested.append("%s.%s" % (key, ",".join(sorted(value.keys()))))
        return keys + nested


    def _text_or_none(self, value):
        if value is None or value is False:
            return None
        if isinstance(value, bool):
            return None
        text = str(value).strip()
        return text if text else None

    def _as_bool(self, value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")
        return bool(value)

    def _state_to_app(self, internal_state):
        mapping = {
            "pending": "pendent",
            "reading": "llegint",
            "finished": "acabat",
            "abandoned": "abandonat",
        }
        return mapping.get(internal_state, "pendent")

    def _state_from_client(self, value):
        mapping = {
            "pending": "pending",
            "pendent": "pending",
            "reading": "reading",
            "llegint": "reading",
            "finished": "finished",
            "acabat": "finished",
            "acabada": "finished",
            "abandoned": "abandoned",
            "abandonat": "abandoned",
        }
        return mapping.get(str(value or "").strip().lower(), "pending")

    def _validation_from_client(self, value, default="pendent"):
        mapping = {
            "pendent": "pendent",
            "pending": "pendent",
            "cal_completar": "cal_completar",
            "acceptada": "acceptada",
            "accepted": "acceptada",
            "no_acceptada": "no_acceptada",
            "rejected": "no_acceptada",
        }
        return mapping.get(str(value or "").strip().lower(), default)

    def _student_from_auth(self):
        auth = (request.httprequest.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            raw_token = auth.split(" ", 1)[1].strip()
            alumne, _token = request.env["joc.lector.auth.token"].sudo().authenticate_raw_token(raw_token)
            if alumne:
                return alumne

        app_uid = self._param("app_uid")
        if not app_uid:
            codi_alumne = (self._param("codi_alumne") or self._param("student_code") or "").strip().upper()
            if not codi_alumne:
                return False
            return request.env["joc.lector.alumne"].sudo().search([
                ("codi_alumne", "=", codi_alumne),
                ("active", "=", True),
            ], limit=1)

        return request.env["joc.lector.alumne"].sudo().search([
            ("app_uid", "=", app_uid),
            ("active", "=", True),
        ], limit=1)

    def _student_or_401(self):
        alumne = self._student_from_auth()
        if not alumne:
            return None, self._error("unauthorized", "Token, app_uid o codi_alumne invàlid.", status=401)
        return alumne, None

    def _serialize_centre(self, centre):
        if not centre:
            return None
        return {
            "id": centre.id,
            "name": centre.name,
            "codi_centre": centre.codi_centre,
            "municipi": self._text_or_none(centre.municipi),
            "ranking_public": centre.ranking_public,
            "web_publica_activa": centre.web_publica_activa,
        }

    def _serialize_classe(self, classe):
        if not classe:
            return None
        return {
            "id": classe.id,
            "server_id": classe.id,
            "serverId": classe.id,
            "name": classe.name,
            "curs_academic": classe.curs_academic,
            "curs_grup": self._text_or_none(classe.curs_grup),
            "nivell": self._text_or_none(classe.nivell),
            "access_code": classe.access_code,
            "codi_acces": classe.codi_acces,
            "ranking_classe_actiu": classe.ranking_classe_actiu,
            "alumne_count": request.env["joc.lector.matricula"].sudo().search_count([
                ("classe_id", "=", classe.id),
                ("state", "=", "active"),
            ]),
            "limits": {
                "max_alumnes": MAX_ALUMNES_PER_CLASSE,
            },
            "actions": {
                "reenviar_credencials_url": "/joc_lector/api/professor/classe/credencials/reenviar",
            },
            "centre": self._serialize_centre(classe.centre_id),
        }

    def _serialize_professor(self, professor):
        email = self._text_or_none(professor.user_id.email or professor.user_id.login)
        return {
            "id": professor.id,
            "name": professor.name,
            "email": email,
            "user_id": professor.user_id.id,
            "centre_id": professor.centre_id.id,
            "rol": professor.rol,
            "active": professor.active,
        }

    def _serialize_alumne_label(self, alumne, classe):
        return {
            "id": alumne.id,
            "name": alumne.name,
            "usuari": alumne.name,
            "codi_alumne": alumne.codi_alumne,
            "app_uid": alumne.app_uid,
            "classe_id": classe.id,
            "classe": classe.name,
            "codi_classe": classe.access_code,
        }

    def _format_datetime_local(self, value):
        if not value:
            return ""
        local_dt = fields.Datetime.context_timestamp(
            request.env["res.users"].sudo().with_context(tz="Europe/Madrid").browse(request.env.uid),
            value,
        )
        return local_dt.strftime("%d/%m/%Y %H:%M")

    def _normalize_email(self, value):
        if not value:
            return False
        return str(value).strip().lower()

    def _send_template(self, xmlid, record, ctx=None, email_to=None):
        template = request.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.error("Mail template not found: %s", xmlid)
            return False

        email_values = {"email_from": JOC_LECTOR_EMAIL_FROM}
        if email_to:
            email_values["email_to"] = email_to

        return template.sudo().with_context(**(ctx or {})).send_mail(
            record.id,
            force_send=True,
            email_values=email_values,
        )

    def _student_labels_html(self, professor, classe, alumnes):
        from urllib.parse import urlencode

        app_url = "https://provestalens.es/lectures/app/"

        def esc(value):
            return html.escape(str(value or ""))

        def split_student_name(value):
            text = str(value or "").strip()
            if " · " in text:
                parts = text.split(" · ", 1)
                return parts[0].strip(), parts[1].strip()
            return "", text

        def username_part(value):
            import re
            import unicodedata

            text = str(value or "").strip().lower()
            normalized = unicodedata.normalize("NFKD", text)
            ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
            ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
            return ascii_text.strip("-")

        def student_username(student_id, alias, fallback):
            parts = [username_part(part) for part in (student_id, alias)]
            username = "-".join(part for part in parts if part)
            return username or username_part(fallback) or "lector"

        def qr_data_uri_for(target_url):
            try:
                import io
                import qrcode

                image = qrcode.make(target_url)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return "data:image/png;base64,%s" % base64.b64encode(buffer.getvalue()).decode("ascii")
            except Exception:
                _logger.exception("Could not render Joc Lector app QR")
                return ""

        cards = []
        for alumne in alumnes:
            student_id, alias = split_student_name(alumne.name)
            username = student_username(student_id, alias, alumne.name)
            subtitle = "Escriu exactament este nom"
            target_url = "%s?%s" % (
                app_url,
                urlencode({
                    "view": "passaport",
                    "nom_visible": username,
                    "codi_classe": classe.access_code,
                    "codi_alumne": alumne.codi_alumne,
                }),
            )
            qr_src = qr_data_uri_for(target_url)
            qr_html = '<img class="qr-img" src="%s" alt="QR app"/>' % esc(qr_src) if qr_src else '<div class="qr-fallback">App</div>'
            cards.append("""
                <td class="card-cell">
                    <div class="card">
                        <table class="card-top" cellspacing="0" cellpadding="0">
                            <tr>
                                <td class="title-box">
                                    <div class="field-label">1. El teu nom en l'app</div>
                                    <div class="alias">%s</div>
                                    <div class="student-id">%s</div>
                                </td>
                                <td class="qr-box">
                                    %s
                                    <div class="qr-label">Obri passaport</div>
                                    <div class="app-link">https://provestalens.es/lectures/app/</div>
                                </td>
                            </tr>
                        </table>
                        <div class="code-label">2. Codi per entrar</div>
                        <div class="student-code">%s</div>
                        <table class="class-line" cellspacing="0" cellpadding="0">
                            <tr>
                                <td>Classe: <strong>%s</strong></td>
                                <td class="class-code">Codi classe: %s</td>
                            </tr>
                        </table>
                    </div>
                </td>
            """ % (
                esc(username),
                esc(subtitle),
                qr_html,
                esc(alumne.codi_alumne),
                esc(classe.name),
                esc(classe.access_code),
            ))

        rows = []
        for index in range(0, len(cards), 2):
            right = cards[index + 1] if index + 1 < len(cards) else '<td class="card-cell empty"></td>'
            rows.append("<tr>%s%s</tr>" % (cards[index], right))

        return """<!doctype html>
<html>
<head>
    <meta charset="utf-8"/>
    <style>
        @page { size: A4; margin: 8mm 7mm; }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            color: #123F2D;
            background: #F6F0E8;
        }
        .page {
            width: 196mm;
            margin: 0 auto;
        }
        .header-table {
            width: 100%%;
            border-collapse: collapse;
            margin: 0 0 4mm 0;
            color: #123F2D;
        }
        .brand {
            font-size: 15px;
            font-weight: bold;
            letter-spacing: 0;
        }
        .header-meta {
            font-size: 9px;
            color: #6F6F64;
            text-align: right;
            line-height: 1.35;
        }
        .sheet {
            width: 100%%;
            border-collapse: separate;
            border-spacing: 3mm 3mm;
            table-layout: fixed;
        }
        .card-cell {
            width: 50%%;
            height: 50mm;
            padding: 0;
            vertical-align: top;
            page-break-inside: avoid;
        }
        .card-cell.empty {
            border: 0;
        }
        .card {
            height: 50mm;
            border: 0.35mm solid #C8DCC0;
            background: #FFFDF7;
            border-radius: 5mm;
            padding: 3.5mm 4mm 3mm 4mm;
            overflow: hidden;
            page-break-inside: avoid;
        }
        .card-top {
            width: 100%%;
            border-collapse: collapse;
        }
        .title-box {
            padding-left: 0;
            vertical-align: middle;
        }
        .qr-box {
            width: 24mm;
            text-align: right;
            vertical-align: top;
        }
        .qr-img {
            width: 20mm;
            height: 20mm;
            display: inline-block;
            border: 0.25mm solid #DDEAD3;
            background: #FFFFFF;
            padding: 0.8mm;
        }
        .qr-fallback {
            width: 20mm;
            height: 20mm;
            display: inline-block;
            border: 0.25mm solid #DDEAD3;
            color: #174C38;
            font-size: 8px;
            line-height: 20mm;
            text-align: center;
        }
        .qr-label {
            margin-top: 0.4mm;
            font-size: 6.5px;
            color: #6F6F64;
            text-align: center;
        }
        .app-link {
            width: 24mm;
            margin-top: 0.5mm;
            font-size: 5.2px;
            line-height: 1.12;
            color: #174C38;
            text-align: center;
            word-break: break-all;
        }
        .field-label {
            font-size: 7.5px;
            text-transform: uppercase;
            color: #6F6F64;
            letter-spacing: 0.45px;
            margin-bottom: 0.7mm;
        }
        .alias {
            font-size: 14.5px;
            line-height: 1.12;
            font-weight: bold;
            color: #123F2D;
            white-space: nowrap;
            overflow: hidden;
        }
        .student-id {
            margin-top: 1mm;
            font-size: 9px;
            color: #6F6F64;
            white-space: nowrap;
            overflow: hidden;
        }
        .code-label {
            margin-top: 2.5mm;
            font-size: 9px;
            text-transform: uppercase;
            color: #6F6F64;
            letter-spacing: 0.6px;
        }
        .student-code {
            margin-top: 1mm;
            padding: 2mm 2.2mm;
            border-radius: 2.5mm;
            background: #EAF3E4;
            border: 0.25mm solid #BBD6B0;
            font-size: 17px;
            line-height: 1;
            font-weight: bold;
            color: #174C38;
            white-space: nowrap;
            overflow: hidden;
        }
        .class-line {
            width: 100%%;
            margin-top: 2.4mm;
            border-top: 0.25mm solid #DDEAD3;
            padding-top: 1.5mm;
            font-size: 8px;
            color: #6F6F64;
            border-collapse: collapse;
        }
        .class-line td {
            padding-top: 1.5mm;
            white-space: nowrap;
            overflow: hidden;
        }
        .class-code {
            text-align: right;
            color: #174C38;
            font-weight: bold;
        }
        .footer {
            margin-top: 2mm;
            font-size: 8px;
            color: #6F6F64;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="page">
        <table class="header-table" cellspacing="0" cellpadding="0">
            <tr>
                <td class="brand">Joc Lector</td>
                <td class="header-meta">
                    %s · %s<br/>
                    Professor/a: %s
                </td>
            </tr>
        </table>
        <table class="sheet" cellspacing="0" cellpadding="0">%s</table>
        <div class="footer">Privacitat i ús educatiu · Reparteix cada targeta només a l'alumne corresponent.</div>
    </div>
</body>
</html>""" % (
            esc(classe.name),
            esc(classe.curs_academic),
            esc(professor.name),
            "".join(rows),
        )

    def _render_labels_pdf(self, html_content):
        report = request.env["ir.actions.report"].sudo()
        runner = getattr(report, "_run_wkhtmltopdf", None)
        if not runner:
            return None
        try:
            return runner([html_content])
        except Exception:
            _logger.exception("Could not render Joc Lector labels PDF")
            return None

    def _send_student_labels_email(self, professor, classe, alumnes):
        email_to = self._text_or_none(professor.user_id.email or professor.user_id.login)
        if not email_to:
            return False

        labels_html = self._student_labels_html(professor, classe, alumnes)
        attachments = []
        Attachment = request.env["ir.attachment"].sudo()

        pdf_content = self._render_labels_pdf(labels_html)
        if pdf_content:
            pdf_attachment = Attachment.create({
                "name": "etiquetes_joc_lector_%s.pdf" % classe.access_code,
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "mimetype": "application/pdf",
            })
            attachments.append(pdf_attachment.id)
        else:
            html_attachment = Attachment.create({
                "name": "etiquetes_joc_lector_%s.html" % classe.access_code,
                "type": "binary",
                "datas": base64.b64encode(labels_html.encode("utf-8")),
                "mimetype": "text/html",
            })
            attachments.append(html_attachment.id)

        body_html = """
            <p>Hola %s,</p>
            <p>S'han creat %s alumnes per a la classe <strong>%s</strong>.</p>
            <p>Adjunt tens les etiquetes de 60x20 mm amb usuari i codi d'alumne.</p>
        """ % (
            html.escape(professor.name or ""),
            len(alumnes),
            html.escape(classe.name or ""),
        )
        mail = request.env["mail.mail"].sudo().create({
            "subject": "Joc Lector: etiquetes d'alumnat - %s" % classe.name,
            "email_from": JOC_LECTOR_EMAIL_FROM,
            "email_to": email_to,
            "body_html": body_html,
            "attachment_ids": [(6, 0, attachments)],
            "auto_delete": True,
        })
        mail.sudo().send()
        return True

    def _active_alumnes_for_class(self, classe):
        matricules = request.env["joc.lector.matricula"].sudo().search([
            ("classe_id", "=", classe.id),
            ("state", "=", "active"),
            ("alumne_id.active", "=", True),
        ], order="date_start asc, id asc")
        return matricules.mapped("alumne_id").sorted(key=lambda alumne: (alumne.name or "").lower())

    def _find_active_professor_by_email(self, email):
        email = self._normalize_email(email)
        if not email:
            return False
        return request.env["joc.lector.professor"].sudo().search([
            ("active", "=", True),
            ("centre_id.active", "=", True),
            "|",
            ("user_id.login", "=", email),
            ("user_id.email", "=", email),
        ], order="id desc", limit=1)

    def _serialize_lectura(self, lectura):
        llibre = lectura.llibre_id
        return {
            "id": lectura.id,
            "server_id": lectura.id,
            "serverId": lectura.id,
            "client_uid": self._text_or_none(lectura.client_uid),
            "clientUid": self._text_or_none(lectura.client_uid),
            "llibre_id": llibre.id or None,
            "llibreId": llibre.id or None,
            "titol": self._text_or_none(llibre.name),
            "autor": self._text_or_none(llibre.autor),
            "isbn": self._text_or_none(llibre.isbn),
            "editorial": self._text_or_none(llibre.editorial),
            "pagines": llibre.pagines or 0,
            "portadaUrl": self._text_or_none(llibre.portada_url),
            "portada_url": self._text_or_none(llibre.portada_url),
            "categoria": self._text_or_none(llibre.categoria),
            "edat_recomanada": self._text_or_none(llibre.edat_recomanada),
            "nivell_recomanat": self._text_or_none(llibre.nivell_recomanat),
            "estat": lectura.state,
            "estat_app": self._state_to_app(lectura.state),
            "data_inici": lectura.date_start,
            "dataInici": lectura.date_start,
            "data_fi": lectura.date_end,
            "dataFi": lectura.date_end,
            "valoracio": lectura.valoracio,
            "ressenya": self._text_or_none(lectura.ressenya),
            "evidencia_url": self._text_or_none(lectura.evidencia_url),
            "evidencia_text": self._text_or_none(lectura.evidencia_text),
            "visible_publicament": lectura.visible_publicament,
            "estat_validacio": lectura.estat_validacio,
            "estatValidacio": lectura.estat_validacio,
            "punts_generats": lectura.punts_generats,
        }

    def _serialize_sync_lectura(self, lectura, warning=None):
        data = {
            "server_id": lectura.id,
            "serverId": lectura.id,
            "client_uid": self._text_or_none(lectura.client_uid),
            "clientUid": self._text_or_none(lectura.client_uid),
            "estat": lectura.state,
            "estat_app": self._state_to_app(lectura.state),
            "estat_validacio": lectura.estat_validacio,
            "estatValidacio": lectura.estat_validacio,
        }
        if warning:
            data["warning"] = warning
        return data

    def _int_from_item(self, item, aliases, default=0):
        value = self._item_get(item, aliases)
        try:
            return int(value or 0)
        except Exception:
            return default

    def _book_vals_from_item(self, item):
        vals = {}
        simple_fields = {
            "autor": ["autor", "author"],
            "editorial": ["editorial", "publisher"],
            "idioma": ["idioma", "language"],
            "nivell_recomanat": ["nivell_recomanat", "nivellRecomanat", "nivell", "level"],
            "portada_url": ["portada_url", "portadaUrl", "cover_url", "coverUrl"],
            "categoria": ["categoria", "category"],
            "edat_recomanada": ["edat_recomanada", "edatRecomanada", "edat", "age"],
            "resum": ["resum", "sinopsi", "summary", "description"],
        }
        for field, aliases in simple_fields.items():
            value = self._text_or_none(self._item_get(item, aliases))
            if value:
                vals[field] = value

        if not vals.get("categoria"):
            tags = self._item_get(item, ["etiquetes", "tags"])
            if isinstance(tags, list):
                vals["categoria"] = ", ".join(str(tag).strip() for tag in tags if str(tag).strip()) or False
            elif tags:
                vals["categoria"] = self._text_or_none(tags)

        isbn = self._text_or_none(self._item_get(item, ["isbn"]))
        if isbn:
            vals["isbn"] = isbn

        pages = self._int_from_item(item, ["pagines", "pages", "num_pagines", "pageCount"])
        if pages > 0:
            vals["pagines"] = pages

        year = self._int_from_item(item, ["any", "any_publicacio", "anyPublicacio", "year"])
        if year > 0:
            vals["any_publicacio"] = year

        return vals

    def _resolve_or_create_book(self, item):
        Llibre = request.env["joc.lector.llibre"].sudo()
        isbn = (self._item_get(item, ["isbn"]) or "").strip()
        titol = (self._item_get(item, ["titol", "name"]) or "").strip() or "Llibre sense títol"
        book_vals = self._book_vals_from_item(item)

        llibre_id = self._item_get(item, ["llibreId", "llibre_id", "bookId", "book_id"])
        if llibre_id:
            try:
                llibre_by_id = Llibre.search([("id", "=", int(llibre_id))], limit=1)
                if llibre_by_id:
                    vals = {
                        field: value
                        for field, value in book_vals.items()
                        if value and not llibre_by_id[field]
                    }
                    if vals:
                        llibre_by_id.write(vals)
                    return llibre_by_id
            except Exception:
                pass

        llibre = False
        if isbn:
            llibre = Llibre.search([("isbn", "=", isbn)], limit=1)

        if not llibre and titol:
            llibre = Llibre.search([("name", "=", titol)], limit=1)

        if llibre:
            vals = {}
            for field, value in book_vals.items():
                if value and not llibre[field]:
                    vals[field] = value
            if vals:
                llibre.write(vals)
            return llibre

        vals = {
            "name": titol,
            "active": True,
        }
        vals.update(book_vals)
        return Llibre.create(vals)

    @http.route("/joc_lector/api/health", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def health(self, **kwargs):
        return self._json({"ok": True, "service": "joc_lector", "status": "up"})

    @http.route("/joc_lector/api/alumne/entrar_classe", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def alumne_entrar_classe(self, **kwargs):
        codi_classe = (self._param("codi_classe") or "").strip().upper()
        app_uid = (self._param("app_uid") or "").strip()
        codi_alumne = (
            self._param("codi_alumne")
            or self._param("student_code")
            or self._param("codi")
            or ""
        ).strip().upper()
        nom_visible = (self._param("nom_visible") or "").strip()

        if not (codi_classe or codi_alumne) or not (app_uid or codi_alumne):
            return self._error("missing_params", "Cal indicar codi_classe o codi_alumne, i app_uid o codi_alumne.")

        Classe = request.env["joc.lector.classe"].sudo()
        Alumne = request.env["joc.lector.alumne"].sudo()
        Matricula = request.env["joc.lector.matricula"].sudo()
        alumne = False

        classe = False
        if codi_classe:
            classe = Classe.search([
                ("access_code", "=", codi_classe),
                ("active", "=", True),
            ], limit=1)

            # Entrada manual antiga: l'app posava el codi d'alumne en codi_classe.
            if not classe and not codi_alumne:
                codi_alumne = codi_classe
                codi_classe = ""

        if codi_alumne:
            alumne = Alumne.search([("codi_alumne", "=", codi_alumne), ("active", "=", True)], limit=1)
            if not alumne:
                return self._error("student_not_found", "No s'ha trobat cap alumne amb eixe codi.", status=404)

            if classe:
                matricula = Matricula.search([
                    ("alumne_id", "=", alumne.id),
                    ("classe_id", "=", classe.id),
                    ("state", "=", "active"),
                ], limit=1)
                if not matricula:
                    return self._error("student_not_in_class", "El codi d'alumne no pertany a esta classe.", status=404)
            else:
                matricula = Matricula.search([
                    ("alumne_id", "=", alumne.id),
                    ("state", "=", "active"),
                ], order="date_start desc, id desc", limit=1)
                if not matricula or not matricula.classe_id.active:
                    return self._error("active_class_not_found", "Este alumne no té cap classe activa.", status=404)
                classe = matricula.classe_id

        if not alumne and app_uid:
            alumne = Alumne.search([("app_uid", "=", app_uid)], limit=1)

        if not classe:
            return self._error("class_not_found", "No s'ha trobat la classe.", status=404)

        if not alumne:
            alumne = Alumne.create({
                "name": nom_visible or "Lector/a",
                "app_uid": app_uid,
            })
        else:
            vals = {}
            if nom_visible and alumne.name != nom_visible:
                vals["name"] = nom_visible
            if app_uid and not codi_alumne and alumne.app_uid != app_uid:
                vals["app_uid"] = app_uid
            if vals:
                alumne.write(vals)

        if not alumne.current_classe_id or alumne.current_classe_id.id != classe.id:
            try:
                request.env["joc.lector.matricula"].sudo().create({
                    "alumne_id": alumne.id,
                    "classe_id": classe.id,
                })
            except ValidationError as exc:
                return self._error("class_ratio_too_large", str(exc), status=409)

        raw_token, token = request.env["joc.lector.auth.token"].sudo().create_for_alumne(
            alumne,
            device_name=self._param("device_name") or "Flutter",
        )

        return self._json({
            "ok": True,
            "alumne": {
                "id": alumne.id,
                "app_uid": alumne.app_uid,
                "codi_alumne": alumne.codi_alumne,
                "nom_visible": alumne.name,
            },
            "token": {
                "access_token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.date_expires,
            },
            "centre": self._serialize_centre(classe.centre_id),
            "classe": self._serialize_classe(classe),
            "config": {
                "ranking_public": classe.centre_id.ranking_public,
                "ranking_classe_actiu": classe.ranking_classe_actiu,
            },
        })

    @http.route("/joc_lector/api/sync/lectures", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def sync_lectures(self, **kwargs):
        alumne, error = self._student_or_401()
        if error:
            return error

        lectures = self._param("lectures", [])
        if not isinstance(lectures, list):
            return self._error("invalid_payload", "El camp lectures ha de ser una llista.")

        Lectura = request.env["joc.lector.lectura"].sudo()
        results = []

        for item in lectures:
            if not isinstance(item, dict):
                continue

            class_id = alumne.current_classe_id.id if alumne.current_classe_id else False
            server_id = self._item_get(item, ["serverId", "server_id"])
            client_uid = self._text_or_none(self._item_get(item, ["clientUid", "client_uid"])) or False
            llibre = self._resolve_or_create_book(item)
            state = self._state_from_client(self._item_get(item, ["estat", "state"]))
            estat_validacio_in = self._validation_from_client(
                self._item_get(item, ["estatValidacio", "estat_validacio"]),
                default="pendent",
            )

            lectura = False
            if server_id:
                try:
                    lectura = Lectura.search([
                        ("id", "=", int(server_id)),
                        ("alumne_id", "=", alumne.id),
                    ], limit=1)
                except Exception:
                    lectura = False

            if not lectura and client_uid:
                lectura = Lectura.search([
                    ("alumne_id", "=", alumne.id),
                    ("client_uid", "=", client_uid),
                ], limit=1)

                # Evita col·lisions globals de client_uid d'altres alumnes.
                if not lectura:
                    lectura_other = Lectura.search([("client_uid", "=", client_uid)], limit=1)
                    if lectura_other and lectura_other.alumne_id.id != alumne.id:
                        results.append(self._serialize_sync_lectura(
                            lectura_other,
                            warning="client_uid_already_used_by_other_student",
                        ))
                        continue

            if not lectura and not client_uid:
                isbn = (self._item_get(item, ["isbn"]) or "").strip()
                domain = [
                    ("alumne_id", "=", alumne.id),
                    ("classe_id", "=", class_id),
                ]
                if isbn:
                    domain.append(("llibre_id.isbn", "=", isbn))
                else:
                    domain.append(("llibre_id", "=", llibre.id))
                lectura = Lectura.search(domain, limit=1)

            evidencia_text = self._item_get(item, ["evidencia", "evidenciaText", "evidencia_text"])

            vals = {
                "alumne_id": alumne.id,
                "classe_id": class_id,
                "llibre_id": llibre.id,
                "state": state,
                "date_start": self._item_get(item, ["dataInici", "data_inici", "date_start"]) or fields.Date.context_today(request.env.user),
                "date_end": self._item_get(item, ["dataFi", "data_fi", "date_end"]) or False,
                "valoracio": int(self._item_get(item, ["valoracio"], 0) or 0) or False,
                "ressenya": self._item_get(item, ["ressenya"]) or False,
                "evidencia_url": self._item_get(item, ["evidencia_url"]) or False,
                "evidencia_text": evidencia_text or False,
                "visible_publicament": self._as_bool(self._item_get(item, ["visiblePublicament", "visible_publicament"], False), False),
                "client_uid": client_uid or (lectura.client_uid if lectura else False),
            }

            if lectura:
                # Manté acceptacions ja validades per professorat.
                if lectura and lectura.alumne_id.id != alumne.id:
                    results.append(self._serialize_sync_lectura(
                        lectura,
                        warning="client_uid_already_used_by_other_student",
                    ))
                    continue

                if lectura.estat_validacio != "acceptada":
                    vals["estat_validacio"] = estat_validacio_in
                lectura.write(vals)
            else:
                vals["estat_validacio"] = estat_validacio_in
                lectura = Lectura.create(vals)

            results.append(self._serialize_sync_lectura(lectura))

        return self._json({"ok": True, "count": len(results), "lectures": results})

    @http.route("/joc_lector/api/alumne/passaport", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def alumne_passaport(self, **kwargs):
        alumne, error = self._student_or_401()
        if error:
            return error

        lectures = request.env["joc.lector.lectura"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], order="date_start desc, id desc")

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], limit=1)

        return self._json({
            "ok": True,
            "alumne_id": alumne.id,
            "passaport": {
                "punts": passaport.punts if passaport else 0,
                "nivell": passaport.nivell if passaport else 1,
                "llibres_llegits": passaport.llibres_llegits if passaport else 0,
            },
            "lectures": [self._serialize_lectura(lectura) for lectura in lectures],
        })

    @http.route("/joc_lector/api/alumne/importar_passaport", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def alumne_importar_passaport(self, **kwargs):
        alumne, error = self._student_or_401()
        if error:
            return error

        codi_importacio = (
            self._param("codi_importacio")
            or self._param("import_code")
            or self._param("codi")
            or self._param("codi_alumne")
            or ""
        ).strip().upper()
        if not codi_importacio:
            return self._error("missing_import_code", "Cal indicar el codi d'importació.", status=400)

        Alumne = request.env["joc.lector.alumne"].sudo().with_context(active_test=False)
        origen = Alumne.search([("codi_alumne", "=", codi_importacio)], limit=1)
        if not origen:
            return self._error("import_code_not_found", "No s'ha trobat cap passaport amb este codi.", status=404)
        if origen.id == alumne.id:
            return self._error("same_student", "Este codi ja correspon al passaport actual.", status=409)

        Lectura = request.env["joc.lector.lectura"].sudo()
        lectures_origen = Lectura.search([("alumne_id", "=", origen.id)], order="date_start asc, id asc")
        current_class = alumne.current_classe_id
        imported = Lectura.browse()

        for lectura in lectures_origen:
            duplicate_domain = [
                ("alumne_id", "=", alumne.id),
                ("llibre_id", "=", lectura.llibre_id.id),
            ]
            if lectura.date_end:
                duplicate_domain.append(("date_end", "=", lectura.date_end))
            elif lectura.date_start:
                duplicate_domain.append(("date_start", "=", lectura.date_start))

            if Lectura.search_count(duplicate_domain):
                continue

            imported |= Lectura.create({
                "alumne_id": alumne.id,
                "classe_id": current_class.id if current_class else False,
                "llibre_id": lectura.llibre_id.id,
                "state": lectura.state,
                "date_start": lectura.date_start,
                "date_end": lectura.date_end,
                "valoracio": lectura.valoracio,
                "ressenya": lectura.ressenya,
                "evidencia_url": lectura.evidencia_url,
                "evidencia_text": lectura.evidencia_text,
                "visible_publicament": lectura.visible_publicament,
                "estat_validacio": lectura.estat_validacio,
                "punts_generats": lectura.punts_generats,
                "punts_obtinguts": lectura.punts_obtinguts,
                "notes": "Importat del passaport %s." % origen.codi_alumne,
            })

        passaport = request.env["joc.lector.passaport"].sudo().search([
            ("alumne_id", "=", alumne.id),
        ], limit=1)

        return self._json({
            "ok": True,
            "imported_count": len(imported),
            "source_student_id": origen.id,
            "source_code": origen.codi_alumne,
            "passaport": {
                "punts": passaport.punts if passaport else 0,
                "nivell": passaport.nivell if passaport else 1,
                "llibres_llegits": passaport.llibres_llegits if passaport else 0,
            },
            "lectures": [self._serialize_lectura(lectura) for lectura in imported],
        })

    def _serialize_book_catalog(self, llibre):
        tags = [value for value in [self._text_or_none(llibre.categoria)] if value]
        total_ressenyes = llibre.ressenya_count or 0
        suma_valoracions = int(round((llibre.valoracio_mitjana or 0.0) * total_ressenyes))
        return {
            "id": llibre.id,
            "titol": llibre.name,
            "name": llibre.name,
            "autor": self._text_or_none(llibre.autor),
            "isbn": self._text_or_none(llibre.isbn),
            "editorial": self._text_or_none(llibre.editorial),
            "pagines": llibre.pagines or 0,
            "pages": llibre.pagines or 0,
            "any": llibre.any_publicacio,
            "any_publicacio": llibre.any_publicacio,
            "anyPublicacio": llibre.any_publicacio,
            "idioma": self._text_or_none(llibre.idioma),
            "nivell_recomanat": self._text_or_none(llibre.nivell_recomanat),
            "categoria": self._text_or_none(llibre.categoria),
            "etiquetes": tags,
            "tags": tags,
            "edat_recomanada": self._text_or_none(llibre.edat_recomanada),
            "resum": self._text_or_none(llibre.resum),
            "sinopsi": self._text_or_none(llibre.resum),
            "portada_url": self._text_or_none(llibre.portada_url),
            "portadaUrl": self._text_or_none(llibre.portada_url),
            "lectura_count": llibre.lectura_count,
            "totalLecturesAcceptades": llibre.lectura_count,
            "ressenya_count": llibre.ressenya_count,
            "totalRessenyes": total_ressenyes,
            "sumaValoracions": suma_valoracions,
            "valoracio_mitjana": llibre.valoracio_mitjana,
            "actiu": llibre.active,
            "active": llibre.active,
        }

    def _ids_from_value(self, value):
        if value in (None, False, ""):
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                value = [part.strip() for part in value.split(",") if part.strip()]
        if not isinstance(value, list):
            value = [value]

        ids = []
        for item in value:
            if isinstance(item, dict):
                item = item.get("id") or item.get("llibre_id") or item.get("llibreId")
            try:
                item_id = int(item)
            except Exception:
                continue
            if item_id > 0 and item_id not in ids:
                ids.append(item_id)
        return ids

    def _serialize_repte_casella(self, casella, participacio=None):
        completed = bool(participacio and casella in participacio.bingo_casella_ids)
        return {
            "id": casella.id,
            "name": casella.name,
            "nom": casella.name,
            "sequence": casella.sequence,
            "descripcio": self._text_or_none(casella.descripcio),
            "completed": completed,
            "completada": completed,
            "llibre_ids": casella.llibre_ids.ids,
            "llibres": [self._serialize_book_catalog(llibre) for llibre in casella.llibre_ids],
        }

    def _serialize_repte(self, repte, alumne=None):
        participacio = False
        if alumne:
            participacio = request.env["joc.lector.repte.participacio"].sudo().search([
                ("repte_id", "=", repte.id),
                ("alumne_id", "=", alumne.id),
            ], limit=1)

        data = {
            "id": repte.id,
            "name": repte.name,
            "nom": repte.name,
            "descripcio": self._text_or_none(repte.descripcio),
            "tipus": repte.tipus,
            "centre_id": repte.centre_id.id or None,
            "classe_id": repte.classe_id.id or None,
            "curs_academic": self._text_or_none(repte.curs_academic),
            "data_inici": repte.data_inici,
            "data_fi": repte.data_fi,
            "punts": repte.punts,
            "public": repte.public,
            "active": repte.active,
            "llibre_ids": repte.llibre_ids.ids,
            "llibres": [self._serialize_book_catalog(llibre) for llibre in repte.llibre_ids],
            "bingo_caselles": [
                self._serialize_repte_casella(casella, participacio=participacio)
                for casella in repte.bingo_casella_ids
            ],
        }
        if participacio:
            data.update({
                "participacio_id": participacio.id,
                "progres": participacio.progres,
                "completat": participacio.completat,
                "validat": participacio.validat,
                "punts_generats": participacio.punts_generats,
                "lectura_ids": participacio.lectura_ids.ids,
            })
        else:
            data.update({
                "participacio_id": None,
                "progres": 0.0,
                "completat": False,
                "validat": False,
                "punts_generats": 0,
                "lectura_ids": [],
            })
        return data

    def _repte_scope_for_professor(self, profile):
        classes = self._professor_classes(profile)
        return [
            ("active", "in", [True, False]),
            "|",
            ("classe_id", "in", classes.ids or [0]),
            ("centre_id", "=", profile.centre_id.id),
        ]

    @http.route([
        "/joc_lector/api/professor/llibre/guardar",
        "/joc_lector/api/professor/cataleg/guardar",
    ], type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_llibre_guardar(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        Llibre = request.env["joc.lector.llibre"].sudo()
        llibre_id = self._param("id") or self._param("llibre_id") or self._param("llibreId")
        title = self._text_or_none(self._param("titol") or self._param("name") or self._param("title"))
        item = dict(self._payload() or {})
        vals = self._book_vals_from_item(item)
        active_raw = self._param_raw("active", self._param_raw("actiu", None))
        if active_raw is not None:
            vals["active"] = self._as_bool(active_raw, True)

        if title:
            vals["name"] = title

        if not vals.get("name") and not llibre_id:
            return self._error("missing_book_title", "Cal indicar el títol del llibre.")

        llibre = False
        if llibre_id:
            try:
                llibre = Llibre.search([("id", "=", int(llibre_id))], limit=1)
            except Exception:
                llibre = False
            if not llibre:
                return self._error("book_not_found", "No s'ha trobat el llibre.", status=404)
            llibre.write(vals)
        else:
            isbn = vals.get("isbn")
            if isbn:
                llibre = Llibre.search([("isbn", "=", isbn)], limit=1)
            if not llibre and vals.get("name"):
                llibre = Llibre.search([("name", "=", vals["name"])], limit=1)
            if llibre:
                llibre.write(vals)
            else:
                vals.setdefault("active", True)
                llibre = Llibre.create(vals)

        return self._json({
            "ok": True,
            "llibre": self._serialize_book_catalog(llibre),
        })

    @http.route("/joc_lector/api/cataleg", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def cataleg(self, **kwargs):
        llibres = request.env["joc.lector.llibre"].sudo().search([
            ("active", "=", True),
        ], order="name asc", limit=500)

        data = [self._serialize_book_catalog(llibre) for llibre in llibres]

        return self._json({"ok": True, "count": len(data), "cataleg": data})

    @http.route("/joc_lector/api/professor/reptes", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def professor_reptes(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        Reptes = request.env["joc.lector.repte"].sudo()
        reptes = Reptes.search(self._repte_scope_for_professor(profile), order="data_inici desc, id desc", limit=500)
        return self._json({
            "ok": True,
            "count": len(reptes),
            "reptes": [self._serialize_repte(repte) for repte in reptes],
        })

    @http.route("/joc_lector/api/professor/repte/guardar", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_repte_guardar(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        body = self._payload()
        Reptes = request.env["joc.lector.repte"].sudo()
        Llibre = request.env["joc.lector.llibre"].sudo()

        repte_id = self._param("id") or self._param("repte_id") or self._param("repteId")
        name = self._text_or_none(self._param("name") or self._param("nom") or self._param("title") or self._param("titol"))
        tipus = (self._param("tipus") or self._param("type") or "individual").strip()
        punts = self._int_from_item(body, ["punts", "points"], default=0)
        classe_id = self._param("classe_id") or self._param("classeId")
        llibre_ids = self._ids_from_value(
            self._param_raw("llibre_ids")
            or self._param_raw("llibreIds")
            or self._param_raw("llibres")
        )
        caselles_raw = (
            self._param_raw("bingo_caselles")
            or self._param_raw("bingoCaselles")
            or self._param_raw("caselles")
            or []
        )
        if isinstance(caselles_raw, str):
            try:
                caselles_raw = json.loads(caselles_raw)
            except Exception:
                caselles_raw = []
        if not isinstance(caselles_raw, list):
            caselles_raw = []

        if caselles_raw:
            tipus = "bingo"
        if tipus not in ("individual", "classe", "centre", "global", "bingo"):
            return self._error("invalid_challenge_type", "El tipus de repte no és vàlid.")
        if not name and not repte_id:
            return self._error("missing_challenge_name", "Cal indicar el nom del repte.")

        classe = False
        if classe_id:
            try:
                classe = request.env["joc.lector.classe"].sudo().browse(int(classe_id)).exists()
            except Exception:
                classe = False
            if not classe:
                return self._error("class_not_found", "La classe no existeix.", status=404)
            if not self._professor_can_access_class(profile, classe):
                return self._error("forbidden", "La classe no pertany al professorat.", status=403)

        valid_books = Llibre.search([("id", "in", llibre_ids), ("active", "=", True)])
        if len(valid_books) != len(llibre_ids):
            return self._error("book_not_found", "Algun llibre del repte no existeix o no està actiu.", status=404)

        vals = {
            "tipus": tipus,
            "centre_id": (classe.centre_id.id if classe else profile.centre_id.id) or False,
            "classe_id": classe.id if classe else False,
            "llibre_ids": [(6, 0, valid_books.ids)],
        }
        if name:
            vals["name"] = name
        if self._has_param("descripcio") or self._has_param("description"):
            vals["descripcio"] = self._param("descripcio") or self._param("description") or False
        if self._has_param("punts") or self._has_param("points"):
            vals["punts"] = max(0, punts)
        if self._has_param("data_inici") or self._has_param("dataInici"):
            vals["data_inici"] = self._param("data_inici") or self._param("dataInici") or fields.Date.context_today(request.env.user)
        if self._has_param("data_fi") or self._has_param("dataFi"):
            vals["data_fi"] = self._param("data_fi") or self._param("dataFi") or False
        if self._has_param("public"):
            vals["public"] = self._as_bool(self._param_raw("public"), False)
        if self._has_param("active") or self._has_param("actiu"):
            vals["active"] = self._as_bool(self._param_raw("active", self._param_raw("actiu")), True)

        repte = False
        if repte_id:
            try:
                repte = Reptes.search([("id", "=", int(repte_id))], limit=1)
            except Exception:
                repte = False
            if not repte:
                return self._error("challenge_not_found", "No s'ha trobat el repte.", status=404)
            if repte not in Reptes.search(self._repte_scope_for_professor(profile)):
                return self._error("forbidden", "El repte no pertany al professorat.", status=403)
            repte.write(vals)
        else:
            vals.setdefault("name", name)
            vals.setdefault("data_inici", fields.Date.context_today(request.env.user))
            repte = Reptes.create(vals)

        if caselles_raw or self._has_param("bingo_caselles") or self._has_param("bingoCaselles") or self._has_param("caselles"):
            commands = [(5, 0, 0)]
            for index, item in enumerate(caselles_raw, start=1):
                if not isinstance(item, dict):
                    continue
                cell_name = self._text_or_none(item.get("name") or item.get("nom") or item.get("title")) or "Casella %s" % index
                cell_book_ids = self._ids_from_value(item.get("llibre_ids") or item.get("llibreIds") or item.get("llibres"))
                cell_books = Llibre.search([("id", "in", cell_book_ids), ("active", "=", True)])
                if len(cell_books) != len(cell_book_ids):
                    return self._error("book_not_found", "Alguna casella del bingo referencia un llibre inexistent.", status=404)
                commands.append((0, 0, {
                    "name": cell_name,
                    "sequence": int(item.get("sequence") or item.get("ordre") or index * 10),
                    "descripcio": item.get("descripcio") or item.get("description") or False,
                    "llibre_ids": [(6, 0, cell_books.ids)],
                }))
            repte.write({"bingo_casella_ids": commands})

        return self._json({
            "ok": True,
            "repte": self._serialize_repte(repte),
        })

    @http.route("/joc_lector/api/alumne/reptes", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def alumne_reptes(self, **kwargs):
        alumne, error = self._student_or_401()
        if error:
            return error

        today = fields.Date.context_today(request.env.user)
        Repte = request.env["joc.lector.repte"].sudo()
        reptes = Repte.search([
            ("active", "=", True),
            ("data_inici", "<=", today),
            "|",
            ("data_fi", "=", False),
            ("data_fi", ">=", today),
            "|",
            ("classe_id", "=", alumne.current_classe_id.id if alumne.current_classe_id else False),
            "|",
            ("classe_id", "=", False),
            ("centre_id", "=", alumne.current_classe_id.centre_id.id if alumne.current_classe_id else False),
        ], order="data_inici desc, id desc", limit=500)
        classe = alumne.current_classe_id
        centre = classe.centre_id if classe else False
        reptes = reptes.filtered(lambda repte: (
            (repte.classe_id and classe and repte.classe_id.id == classe.id)
            or (not repte.classe_id and (not repte.centre_id or (centre and repte.centre_id.id == centre.id)))
        ))

        return self._json({
            "ok": True,
            "count": len(reptes),
            "reptes": [self._serialize_repte(repte, alumne=alumne) for repte in reptes],
        })

    @http.route("/joc_lector/api/alumne/ranking/meu", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def ranking_meu(self, **kwargs):
        alumne, error = self._student_or_401()
        if error:
            return error

        ranking = alumne.get_ranking_snapshot()
        return self._json({"ok": True, **ranking})

    @http.route([
        "/joc_lector/api/professor/demanar_codi",
        "/joc_lector/api/professor/enviar_codi",
        "/joc_lector/api/professor/reenviar_codi",
    ], type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_demanar_codi(self, **kwargs):
        email = self._normalize_email(
            self._param("email")
            or self._param("professor_email")
            or self._param("correu")
        )
        if not email:
            return self._error("missing_email", "Cal indicar email.", status=400)

        professor = self._find_active_professor_by_email(email)
        if professor:
            raw_code, code = request.env["joc.lector.professor.auth.code"].sudo().create_for_professor(
                professor,
                email=email,
            )
            try:
                self._send_template(
                    "joc_lector.mail_template_joc_lector_professor_auth_code",
                    code,
                    ctx={
                        "professor_code": raw_code,
                        "code_expires_display": self._format_datetime_local(code.date_expires),
                    },
                    email_to=email,
                )
            except Exception:
                _logger.exception("Could not send professor auth code to %s", email)
                return self._error(
                    "mail_send_failed",
                    "No s'ha pogut enviar el codi docent. Revisa la configuracio de correu del servidor.",
                    status=500,
                )

        return self._json({
            "ok": True,
            "message": "Si el correu correspon a professorat actiu, s'ha enviat un codi temporal.",
        })

    @http.route("/joc_lector/api/professor/verificar_codi", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_verificar_codi(self, **kwargs):
        email = self._normalize_email(
            self._param("email")
            or self._param("professor_email")
            or self._param("correu")
        )
        raw_code = (
            self._param("codi")
            or self._param("code")
            or self._param("verification_code")
            or ""
        )
        raw_code = str(raw_code).strip()

        if not email or not raw_code:
            return self._error("missing_params", "Cal indicar email i codi.", status=400)

        professor = self._find_active_professor_by_email(email)
        if not professor:
            return self._error("invalid_code", "Codi docent invalid o caducat.", status=401)

        code = request.env["joc.lector.professor.auth.code"].sudo().search([
            ("professor_id", "=", professor.id),
            ("email", "=", email),
            ("active", "=", True),
            ("used", "=", False),
        ], order="date_created desc, id desc", limit=1)
        if not code:
            return self._error("invalid_code", "Codi docent invalid o caducat.", status=401)

        valid, reason = code.validate_code(raw_code)
        if not valid:
            status = 429 if reason == "too_many_attempts" else 401
            return self._error("invalid_code", "Codi docent invalid o caducat.", status=status)

        raw_token, token = request.env["joc.lector.professor.auth.token"].sudo().create_for_professor(professor)
        professor_data = self._serialize_professor(professor)
        centre_data = self._serialize_centre(professor.centre_id)

        return self._json({
            "ok": True,
            "access_token": raw_token,
            "token_type": "Bearer",
            "expires_at": token.date_expires,
            "token": {
                "access_token": raw_token,
                "token_type": "Bearer",
                "expires_at": token.date_expires,
            },
            "professor": professor_data,
            "centre": centre_data,
        })

    def _professor_profile_or_403(self):
        auth = (request.httprequest.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            raw_token = auth.split(" ", 1)[1].strip()
            profile, _token = request.env["joc.lector.professor.auth.token"].sudo().authenticate_raw_token(raw_token)
            if profile:
                return profile, None
            return None, self._error("unauthorized", "Token docent invalid o caducat.", status=401)

        user = request.env.user
        is_public = bool(user and hasattr(user, "_is_public") and user._is_public())
        if not user or not user.id or is_public:
            return None, self._error("unauthorized", "Cal sessió d'usuari docent.", status=401)

        profile = request.env["joc.lector.professor"].sudo().search([
            ("user_id", "=", user.id),
            ("active", "=", True),
        ], limit=1)
        if not profile:
            return None, self._error("forbidden", "Usuari sense perfil docent de Joc Lector.", status=403)

        return profile, None

    def _professor_classes(self, profile):
        classes = profile.classe_ids.filtered(lambda classe: classe.active)
        fallback = request.env["joc.lector.classe"].sudo().search([
            ("active", "=", True),
            "|",
            ("professor_ids", "in", profile.user_id.id),
            ("professor_joc_ids", "in", profile.id),
        ])
        return (classes | fallback)

    def _professor_can_access_class(self, profile, classe):
        return bool(
            profile in classe.professor_joc_ids
            or profile.user_id in classe.professor_ids
            or classe in profile.classe_ids
        )

    def _professor_class_or_error(self, profile):
        classe_id = (
            self._param("classe_id")
            or self._param("classeId")
            or self._param("server_id")
            or self._param("serverId")
        )
        codi_classe = (
            self._param("codi_classe")
            or self._param("codiClasse")
            or self._param("codi_acces")
            or self._param("access_code")
            or self._param("accessCode")
            or ""
        ).strip().upper()
        Classe = request.env["joc.lector.classe"].sudo()

        classe = False
        if str(classe_id or "").strip().lower() in ("", "false", "none", "null", "undefined"):
            classe_id = None

        if classe_id:
            try:
                classe = Classe.search([
                    ("id", "=", int(classe_id)),
                    ("active", "=", True),
                ], limit=1)
            except Exception:
                if not codi_classe:
                    return None, self._error("invalid_class_id", "classe_id ha de ser numeric.", status=400)

        if not classe and codi_classe:
            classe = Classe.search([
                ("access_code", "=", codi_classe),
                ("active", "=", True),
            ], limit=1)

        if not classe and classe_id and not codi_classe:
            classes = self._professor_classes(profile)
            if len(classes) == 1:
                classe = classes[0]

        if not classe_id and not codi_classe and not classe:
            return None, self._error("missing_class", "Cal indicar classe_id o codi_classe.", status=400)

        if not classe:
            return None, self._error(
                "class_not_found",
                "La classe no existeix o l'app conserva un identificador antic. Actualitza les classes i torna-ho a provar.",
                status=404,
            )

        if not self._professor_can_access_class(profile, classe):
            return None, self._error("forbidden", "La classe no pertany al professorat.", status=403)

        return classe, None

    @http.route("/joc_lector/api/professor/classes", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def professor_classes(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        classes = self._professor_classes(profile)
        return self._json({
            "ok": True,
            "count": len(classes),
            "limits": {
                "max_classes_per_professor": MAX_CLASSES_PER_PROFESSOR,
                "max_alumnes_per_classe": MAX_ALUMNES_PER_CLASSE,
            },
            "classes": [self._serialize_classe(classe) for classe in classes],
        })

    @http.route(
        [
            "/joc_lector/api/docent/classes",
            "/joc_lector/api/professor/classes/crear",
            "/joc_lector/api/professor/classe/crear",
        ],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def professor_classe_crear(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        Classe = request.env["joc.lector.classe"].sudo()
        Matricula = request.env["joc.lector.matricula"].sudo()
        Alumne = request.env["joc.lector.alumne"].sudo()

        name = str(self._param("name") or self._param("nom") or self._param("classe") or "").strip()
        curs_academic = str(
            self._param("curs_academic")
            or self._param("cursAcademic")
            or self._param("curs")
            or ""
        ).strip() or "2026-2027"
        curs_grup = str(
            self._param("curs_grup")
            or self._param("cursGrup")
            or self._param("grup")
            or self._param("group")
            or curs_academic
            or ""
        ).strip()
        nivell = str(self._param("nivell") or self._param("level") or "").strip()

        if not name:
            return self._error("missing_class_name", "Cal indicar el nom de la classe.")
        if not profile.centre_id:
            return self._error("missing_centre", "El perfil docent no té centre assignat.", status=409)

        domain = [
            ("active", "=", True),
            ("centre_id", "=", profile.centre_id.id),
            ("nom_normalitzat", "=", Classe._normalize_key(name)),
            ("curs_grup_normalitzat", "=", Classe._normalize_key(curs_grup)),
        ]
        classe = Classe.search(domain, limit=1)
        created = False
        if not classe:
            try:
                classe = Classe.create({
                    "name": name,
                    "centre_id": profile.centre_id.id,
                    "curs_academic": curs_academic,
                    "curs_grup": curs_grup,
                    "nivell": nivell or False,
                    "professor_joc_ids": [(4, profile.id)],
                    "professor_ids": [(4, profile.user_id.id)],
                })
                created = True
            except ValidationError as exc:
                return self._error("class_limit_exceeded", str(exc), status=409)

        write_vals = {}
        if profile not in classe.professor_joc_ids:
            write_vals["professor_joc_ids"] = [(4, profile.id)]
        if profile.user_id and profile.user_id not in classe.professor_ids:
            write_vals["professor_ids"] = [(4, profile.user_id.id)]
        if classe not in profile.classe_ids:
            try:
                profile.sudo().write({"classe_ids": [(4, classe.id)]})
            except ValidationError as exc:
                return self._error("class_limit_exceeded", str(exc), status=409)
        if write_vals:
            try:
                classe.write(write_vals)
            except ValidationError as exc:
                return self._error("class_limit_exceeded", str(exc), status=409)

        raw_alumnes = self._student_list_param()
        if isinstance(raw_alumnes, str):
            try:
                raw_alumnes = json.loads(raw_alumnes)
            except Exception:
                raw_alumnes = [line.strip() for line in raw_alumnes.splitlines() if line.strip()]
        raw_alumnes = self._coerce_student_list(raw_alumnes)
        if not raw_alumnes:
            raw_alumnes = self._generated_student_items(self._student_count_param())

        alumnes = request.env["joc.lector.alumne"].sudo().browse()
        errors = []
        if raw_alumnes:
            if not isinstance(raw_alumnes, list):
                return self._error("invalid_students", "La llista d'alumnes no és vàlida.")

            student_vals = []
            for index, item in enumerate(raw_alumnes, start=1):
                vals = self._student_create_vals_from_item(item)
                student_name = vals["name"]
                if len(student_name) < 2:
                    errors.append({"index": index, "error": "invalid_name"})
                    continue
                if len(student_name) > 80:
                    errors.append({"index": index, "name": student_name, "error": "name_too_long"})
                    continue
                student_vals.append(vals)

            active_count = Matricula.search_count([
                ("classe_id", "=", classe.id),
                ("state", "=", "active"),
            ])
            if active_count + len(student_vals) > MAX_ALUMNES_PER_CLASSE:
                return self._error(
                    "class_ratio_too_large",
                    "La classe ja té %s alumnes actius i vols afegir-ne %s. El màxim és %s alumnes per classe."
                    % (active_count, len(student_vals), MAX_ALUMNES_PER_CLASSE),
                    status=409,
                )

            for vals in student_vals:
                alumne = Alumne.create(vals)
                try:
                    Matricula.create({
                        "alumne_id": alumne.id,
                        "classe_id": classe.id,
                    })
                except ValidationError as exc:
                    alumne.unlink()
                    return self._error("class_ratio_too_large", str(exc), status=409)
                alumnes |= alumne

        labels_sent = False
        if alumnes:
            try:
                labels_sent = self._send_student_labels_email(profile, classe, alumnes)
            except Exception:
                _logger.exception("Could not send student labels email to professor %s", profile.id)

        return self._json({
            "ok": True,
            "created": created,
            "message": "Classe creada correctament." if created else "Classe sincronitzada correctament.",
            "classe": self._serialize_classe(classe),
            "created_students_count": len(alumnes),
            "alumnes": [self._serialize_alumne_label(alumne, classe) for alumne in alumnes],
            "errors": errors,
            "labels_sent": labels_sent,
            "email_codis_enviat": labels_sent,
        }, status=201 if created else 200)

    @http.route("/joc_lector/api/professor/alumnes/crear", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_alumnes_crear(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        classe, error = self._professor_class_or_error(profile)
        if error:
            return error

        raw_alumnes = self._student_list_param()
        if isinstance(raw_alumnes, str):
            try:
                raw_alumnes = json.loads(raw_alumnes)
            except Exception:
                raw_alumnes = [line.strip() for line in raw_alumnes.splitlines() if line.strip()]
        raw_alumnes = self._coerce_student_list(raw_alumnes)

        if not isinstance(raw_alumnes, list) or not raw_alumnes:
            return self._error("missing_students", "Cal indicar una llista d'alumnes.")

        Alumne = request.env["joc.lector.alumne"].sudo()
        Matricula = request.env["joc.lector.matricula"].sudo()
        created = request.env["joc.lector.alumne"].sudo().browse()
        errors = []
        valid_vals = []

        for index, item in enumerate(raw_alumnes, start=1):
            vals = self._student_create_vals_from_item(item)
            name = vals["name"]

            if len(name) < 2:
                errors.append({"index": index, "error": "invalid_name"})
                continue
            if len(name) > 80:
                errors.append({"index": index, "name": name, "error": "name_too_long"})
                continue
            valid_vals.append(vals)

        active_count = Matricula.search_count([
            ("classe_id", "=", classe.id),
            ("state", "=", "active"),
        ])
        if active_count + len(valid_vals) > MAX_ALUMNES_PER_CLASSE:
            return self._error(
                "class_ratio_too_large",
                "La classe ja té %s alumnes actius i vols afegir-ne %s. L'app està limitada a %s alumnes per classe; eixa ràtio és massa gran."
                % (active_count, len(valid_vals), MAX_ALUMNES_PER_CLASSE),
                status=409,
            )

        for vals in valid_vals:
            alumne = Alumne.create(vals)
            try:
                Matricula.create({
                    "alumne_id": alumne.id,
                    "classe_id": classe.id,
                })
            except ValidationError as exc:
                alumne.unlink()
                return self._error("class_ratio_too_large", str(exc), status=409)
            created |= alumne

        labels_sent = False
        if created:
            try:
                labels_sent = self._send_student_labels_email(profile, classe, created)
            except Exception:
                _logger.exception("Could not send student labels email to professor %s", profile.id)

        return self._json({
            "ok": bool(created),
            "classe": self._serialize_classe(classe),
            "created_count": len(created),
            "error_count": len(errors),
            "alumnes": [self._serialize_alumne_label(alumne, classe) for alumne in created],
            "errors": errors,
            "labels_sent": labels_sent,
        }, status=201 if created else 400)

    @http.route("/joc_lector/api/professor/classe/eliminar", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_classe_eliminar(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        classe, error = self._professor_class_or_error(profile)
        if error:
            return error

        matricules = request.env["joc.lector.matricula"].sudo().search([
            ("classe_id", "=", classe.id),
            ("state", "=", "active"),
        ])
        if matricules:
            matricules.write({
                "state": "closed",
                "date_end": fields.Date.context_today(request.env.user),
            })

        classe.sudo().write({"active": False})
        if classe in profile.classe_ids:
            profile.sudo().write({"classe_ids": [(3, classe.id)]})

        return self._json({
            "ok": True,
            "message": "Classe desactivada correctament.",
            "closed_matricules": len(matricules),
            "classe": {
                "id": classe.id,
                "server_id": classe.id,
                "serverId": classe.id,
                "active": classe.active,
            },
        })

    @http.route("/joc_lector/api/professor/classe/credencials/reenviar", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_classe_credencials_reenviar(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        classe, error = self._professor_class_or_error(profile)
        if error:
            return error

        alumnes = self._active_alumnes_for_class(classe)
        if not alumnes:
            return self._error("empty_class", "La classe no té alumnes actius per enviar credencials.", status=404)

        labels_sent = self._send_student_labels_email(profile, classe, alumnes)
        if not labels_sent:
            return self._error(
                "missing_professor_email",
                "El professor no té cap correu configurat per rebre les credencials.",
                status=409,
            )

        return self._json({
            "ok": True,
            "message": "Credencials del grup reenviades al correu del professor.",
            "alumnes_count": len(alumnes),
            "labels_sent": labels_sent,
        })

    @http.route("/joc_lector/api/professor/validacions_pendents", type="http", auth="public", methods=["GET", "POST"], csrf=False, cors="*")
    def professor_validacions_pendents(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        classes = self._professor_classes(profile)
        lectures = request.env["joc.lector.lectura"].sudo().search([
            ("classe_id", "in", classes.ids),
            ("estat_validacio", "in", ["pendent", "cal_completar", "no_acceptada"]),
        ], order="id desc", limit=500)

        return self._json({
            "ok": True,
            "count": len(lectures),
            "lectures": [self._serialize_lectura(lectura) for lectura in lectures],
        })

    @http.route("/joc_lector/api/professor/validar_lectura", type="http", auth="public", methods=["POST"], csrf=False, cors="*")
    def professor_validar_lectura(self, **kwargs):
        profile, error = self._professor_profile_or_403()
        if error:
            return error

        lectura_id = int(self._param("lectura_id") or 0)
        decisio = (self._param("decisio") or "").strip()
        visible_publicament = bool(self._param("visible_publicament", False))
        comentari = self._param("comentari")

        if not lectura_id or decisio not in ("acceptada", "cal_completar", "no_acceptada"):
            return self._error("invalid_params", "Cal indicar lectura_id i decisio vàlida.")

        classes = self._professor_classes(profile)
        lectura = request.env["joc.lector.lectura"].sudo().search([
            ("id", "=", lectura_id),
            ("classe_id", "in", classes.ids),
        ], limit=1)

        if not lectura:
            return self._error("reading_not_found", "La lectura no pertany a les teues classes.", status=404)

        lectura.action_validar_per_professor(
            profile,
            decisio,
            visible_publicament=visible_publicament,
            comentari=comentari,
        )

        return self._json({
            "ok": True,
            "lectura": self._serialize_lectura(lectura),
        })
