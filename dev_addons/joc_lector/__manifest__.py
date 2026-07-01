# -*- coding: utf-8 -*-
{
    "name": "Joc Lector",
    "summary": "Gestió del passaport lector, llibres, ressenyes i reptes de lectura",
    "description": """
Joc Lector
==========

Mòdul per a gestionar:
- alumnat lector
- classes i codis d'accés
- passaport lector permanent
- llibres
- lectures
- ressenyes
- publicació anonimitzada
- API per a app mòbil
    """,
    "version": "16.0.1.1.0",
    "category": "Education",
    "author": "Juan Bautista Talens Felis",
    "website": "https://provestalens.es",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "website",
        "portal",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/joc_centre_views.xml",
        "views/joc_classe_views.xml",
        "views/joc_alumne_views.xml",
        "views/joc_passaport_views.xml",
        "views/joc_lector_menu.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
