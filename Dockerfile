FROM odoo:16.0
USER root
RUN pip uninstall jinja2 markupsafe -y && \
    pip install jinja2==3.1.2 markupsafe==2.1.1 requests pandas && \
    mkdir -p /var/log/odoo && \
    chown -R odoo:odoo /var/log/odoo
COPY ./scripts/patch_odoo_werkzeug.py /tmp/patch_odoo_werkzeug.py
RUN python3 /tmp/patch_odoo_werkzeug.py && rm /tmp/patch_odoo_werkzeug.py
COPY ./dev_addons/* /mnt/extra-addons/
USER odoo
WORKDIR /mnt/extra-addons
