# preparar_fallers_importacio.py
# -*- coding: utf-8 -*-
import pandas as pd
import sys
import os
import re
import hashlib
import random

if len(sys.argv) < 2:
    print("❗ Has d'indicar el nom del fitxer Excel. Exemple:\n")
    print("   python preparar_fallers_importacio.py nom_del_fitxer.xlsx")
    sys.exit(1)

input_file = sys.argv[1]

if not os.path.exists(input_file):
    print(f"❗ No s'ha trobat el fitxer: {input_file}")
    sys.exit(1)

column_map = {
    'CodFaller': 'codifaller',
    'Nombre': 'nom_faller',
    'Apellidos': 'cognoms_faller',
    'Direccion': 'street',
    'Poblacion': 'city',
    'CP': 'zip',
    'Provincia': 'state_id',
    'TMovil': 'telefon_mobil_orig',
    'Telefono': 'telefon_fix_orig',
    'DNI': 'vat',
    'FechaNacimiento': 'data_naixement',
    'HomeDona': 'sexe',
    'CodiP': 'codi_postal_personalitzat',
    'Alta': 'alta',
    'FechaAlta': 'data_alta',
    'FechaBaja': 'data_baixa',
    'NºFamilia': 'numero_familia',
    'MAIL': 'email',
    'Regina Major': 'es_regina_major',
    'Fallera Major Infantil': 'fallera_major_infantil',
    'Regina Infantil': 'regina_infantil',
    'Comentari': 'comment',
    'NComissions': 'n_comissions',
    'AntiguitatPrevia': 'antiguitat_previa',
    'Baremacio': 'baremacio',
    'Regina/o Infantil': 'regina_o_infantil',
    'Regina/o Major': 'regina_o_major'
}

prov_map = {
    'Valencia': 'València (Valencia)',
    'València': 'València (Valencia)',
    # ... resta del map original ...
}
# Afegeix la resta del map de províncies complet aquí si el talles

df = pd.read_excel(input_file).copy()
df.rename(columns=column_map, inplace=True)
df['state_id'] = df['state_id'].astype(str).str.strip().str.title()
df['state_id'] = df['state_id'].replace(prov_map)
prov_no_trobades = df[~df['state_id'].isin(prov_map.values())]['state_id'].unique()
if len(prov_no_trobades) > 0:
    print("⚠️ Províncies no reconegudes:", prov_no_trobades)

localitats_espanyoles = [
    'TAVERNES DE LA VALLDIGNA', 'PLATJA DE TAVERNES DE LA VALLDIGNA', 'SIMAT DE LA VALLDIGNA',
    'BENIFAIRÓ DE LA VALLDIGNA', 'GANDIA', 'XERACO', 'XÀTIVA', 'ALZIRA',
    'CARLET', 'VALENCIA', 'VALÈNCIA', 'DÉNIA', 'AGUILAS'
]

df['city'] = df['city'].astype(str).str.upper().str.strip()
df['country_id'] = df['city'].apply(lambda x: 'Espanya' if x in localitats_espanyoles else '')

barcodes_generats = set()
dnivistos = set()

def generar_barcode_unic_des_de_vat(vat):
    prefix = "899"
    if not isinstance(vat, str) or vat.strip() == "" or vat in dnivistos:
        while True:
            randpart = f"{random.randint(999000000, 999999999)}"
            barcode = prefix + randpart
            if barcode not in barcodes_generats:
                barcodes_generats.add(barcode)
                return barcode
    else:
        vat_net = vat.strip().upper().replace('-', '').replace(' ', '')
        hash_part = hashlib.sha256(vat_net.encode()).hexdigest()
        numeric_part = int(hash_part[:9], 16) % 1000000000
        barcode = f"{prefix}{numeric_part:09d}"
        while barcode in barcodes_generats:
            numeric_part = (numeric_part + 1) % 1000000000
            barcode = f"{prefix}{numeric_part:09d}"
        barcodes_generats.add(barcode)
        dnivistos.add(vat)
        return barcode

df['barcode'] = df['vat'].apply(generar_barcode_unic_des_de_vat)
df['name'] = (df['nom_faller'].fillna('') + ' ' + df['cognoms_faller'].fillna('')).str.strip()
df = df[df['name'] != '']

# df['name'] = df['nom_faller'].str.strip() + ' ' + df['cognoms_faller'].str.strip()
df['id'] = df['codifaller']
df['company_type'] = 'person'
df['customer_rank'] = 1

boolean_cols = [
    'alta', 'es_regina_major', 'fallera_major_infantil', 'regina_infantil',
    'baremacio', 'regina_o_infantil', 'regina_o_major'
]
for col in boolean_cols:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.upper().map({
            'VERDADERO': True, 'FALSO': False, '1': True, '0': False
        }).fillna(False).infer_objects(copy=False)

def neteja_numero(num):
    if pd.isna(num):
        return ''
    num = re.sub(r'\D', '', str(num))
    if num.startswith('0034'):
        num = num[4:]
    elif num.startswith('34'):
        num = num[2:]
    return num[-9:] if len(num) >= 9 else ''

def classifica(num):
    if not num:
        return 'dubte'
    if num.startswith('9'):
        return 'fix'
    elif num[0] in ['5', '6', '7', '8']:
        return 'mobil'
    return 'dubte'

df['phone'] = ''
df['mobile'] = ''
for idx, row in df.iterrows():
    possibles = [row.get('telefon_fix_orig', ''), row.get('telefon_mobil_orig', '')]
    for num in possibles:
        net = neteja_numero(num)
        tipus = classifica(net)
        if tipus == 'fix' and not df.at[idx, 'phone']:
            df.at[idx, 'phone'] = net
        elif tipus == 'mobil' and not df.at[idx, 'mobile']:
            df.at[idx, 'mobile'] = net
        elif tipus == 'dubte' and not df.at[idx, 'phone']:
            df.at[idx, 'phone'] = net

for date_col in ['data_naixement', 'data_alta', 'data_baixa']:
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%d/%m/%Y')

df.drop(columns=['telefon_fix_orig', 'telefon_mobil_orig'], inplace=True, errors='ignore')
df.drop(columns=['provincia'], inplace=True, errors='ignore')

# 🔐 Afegir camps per a usuaris del portal (res.users)
df['login'] = df['email'].fillna('').str.strip()
df['password'] = df['vat'].fillna('').apply(lambda x: hashlib.sha256(x.encode()).hexdigest()[:10] if x else '')
df['groups_id/id'] = 'base.group_portal'
df['partner_id/id'] = df['id']
df['active'] = True

# 📁 Fitxer complet de contactes (res.partner)
output_partner = os.path.splitext(input_file)[0] + '_res_partner_fallers_COMPLET.xlsx'
df.to_excel(output_partner, index=False)

# 📁 Fitxer separat per a usuaris (res.users)
df_users = df[df['login'] != ''].copy()
df_users_final = df_users[['login', 'password', 'groups_id/id', 'partner_id/id', 'active']]
output_users = os.path.splitext(input_file)[0] + '_res_users_portal.xlsx'
df_users_final.to_excel(output_users, index=False)

print("✅ Contactes generats:", output_partner)
print("✅ Usuaris del portal generats:", output_users)
