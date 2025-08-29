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
    'A Coruña': 'A Coruña',
    'Álava': 'Álava',
    'Albacete': 'Albacete',
    'Alicante': 'Alacant (Alicante)',
    'Almería': 'Almería',
    'Asturias': 'Asturias',
    'Ávila': 'Ávila',
    'Badajoz': 'Badajoz',
    'Barcelona': 'Barcelona',
    'Burgos': 'Burgos',
    'Cáceres': 'Cáceres',
    'Cádiz': 'Cádiz',
    'Cantabria': 'Cantabria',
    'Castellón': 'Castelló (Castellón)',
    'Ceuta': 'Ceuta',
    'Ciudad Real': 'Ciudad Real',
    'Córdoba': 'Córdoba',
    'Cuenca': 'Cuenca',
    'Girona': 'Girona',
    'Granada': 'Granada',
    'Guadalajara': 'Guadalajara',
    'Guipúzcoa': 'Guipúscoa',
    'Huelva': 'Huelva',
    'Huesca': 'Huesca',
    'Illes Balears': 'Illes Balears',
    'Jaén': 'Jaén',
    'La Rioja': 'La Rioja',
    'Las Palmas': 'Las Palmas',
    'León': 'León',
    'Lleida': 'Lleida',
    'Lugo': 'Lugo',
    'Madrid': 'Madrid',
    'Málaga': 'Málaga',
    'Melilla': 'Melilla',
    'Murcia': 'Murcia',
    'Navarra': 'Navarra',
    'Ourense': 'Ourense',
    'Palencia': 'Palencia',
    'Pontevedra': 'Pontevedra',
    'Salamanca': 'Salamanca',
    'Santa Cruz de Tenerife': 'Santa Cruz de Tenerife',
    'Segovia': 'Segovia',
    'Sevilla': 'Sevilla',
    'Soria': 'Soria',
    'Tarragona': 'Tarragona',
    'Teruel': 'Teruel',
    'Toledo': 'Toledo',
    'Valencia': 'València (Valencia)',
    'València': 'València (Valencia)',  # també en valencià
    'Valladolid': 'Valladolid',
    'Vizcaya': 'Biscaia (Vizcaya)',
    'Zamora': 'Zamora',
    'Zaragoza': 'Zaragoza'
}
# Mapeig de províncies

df = pd.read_excel(input_file).copy()
df.rename(columns=column_map, inplace=True)
# Normalització de noms de província abans de mapar
df['state_id'] = df['state_id'].astype(str).str.strip().str.title()
df['state_id'] = df['state_id'].replace(prov_map)
prov_no_trobades = df[~df['state_id'].isin(prov_map.values())]['state_id'].unique()
if len(prov_no_trobades) > 0:
    print("⚠️ Províncies no reconegudes:", prov_no_trobades)




# País per defecte per a localitats conegudes
localitats_espanyoles = [
    'TAVERNES DE LA VALLDIGNA', 'PLATJA DE TAVERNES DE LA VALLDIGNA', 'PLATJA TAVERNES DE LA VALLDIGNA',
    'SIMAT DE LA VALLDIGNA', 'SIMAT DE VALLDIGNA', 'BENIFAIRÓ DE LA VALLDIGNA', 'BENIFAIRO DE LA VALLDIGNA',
    'GANDIA', 'XERACO', 'XÀTIVA', 'ALZIRA', 'CARLET', 'VALENCIA', 'VALÈNCIA',
    'SANT BOI DE LLOBREGAT', 'MASSAMAGRELL', 'DÉNIA', 'AGUILAS', 'LA POBLA DE VALLBONA', 'VALTERNA', 'BARXETA'
]

# Normalitzar ciutat
df['city'] = df['city'].astype(str).str.upper().str.strip()

# Assignar país només si city està al conjunt
df['country_id'] = df['city'].apply(lambda x: 'Espanya' if x in localitats_espanyoles else '')



# Barcode únic
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

df['name'] = df['nom_faller'].str.strip() + ' ' + df['cognoms_faller'].str.strip()
df['id'] = df['codifaller'].apply(lambda x: f"res_partner_faller_{int(x):04d}")
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

output_file = os.path.splitext(input_file)[0] + '_odoo_valencia.xlsx'
df.to_excel(output_file, index=False)
print("✅ Fitxer generat correctament:", output_file)