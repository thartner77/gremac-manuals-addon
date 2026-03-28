#!/usr/bin/env python3
"""
GREMAC Import-Script: Bestehende Hugo-Markdown-Dateien → PocketBase
====================================================================
Parst die alten .de.md / .en.md Dateien, zerlegt sie in Blöcke
und importiert sie in PocketBase (kb_blocks + kb_structure).

Erkennt:
- h2 → Hauptabschnitt (heading_level=2)
- h3 → Unterabschnitt (heading_level=3)
- <img src="..."> → images-Feld des Blocks
- Shared-Blöcke: Titel-Vergleich über alle Manuals

Verwendung:
    python3 import_blocks_from_hugo.py [--dry-run]
"""

import json, re, os, sys
import urllib.request, urllib.parse
from collections import defaultdict

PB_URL = 'http://localhost:8090'
PB_EMAIL = 'admin@gremac.net'
PB_PASSWORD = 'Gremac2026!'

CONTENT_DIR = '/var/www/gremac.net/content/betriebsanleitungen'
IMAGES_BASE = '/images/manuals'

# Manual-Slug → PocketBase Manual-ID
MANUAL_SLUGS = {
    'ezero': 'd4a6b3l0p19p1v0',
    'e1':    'c0ivaz05t14lbts',
    'e2plus':'s02o80ljb6u72rz',
    'e3':    '0d52710r735q5zv',
}

# Alt-Texte für bekannte Bilder (DE | EN)
IMAGE_ALTS = {
    'eZero11.jpg':        'Gremac eZero Übersicht|Gremac eZero overview',
    'eZero-8.jpg':        'Gremac eZero Seitenansicht|Gremac eZero side view',
    'eZero10.jpg':        'Gremac eZero Detail|Gremac eZero detail',
    'eZero-Anschlagpunkte.jpg': 'Anschlagpunkte und Stapleraufnahme|Lifting points and forklift pockets',
    'eZero-Stuetzfuesse-Transport.jpg': 'Stützfüße in Transportstellung|Support feet in transport position',
    'Bedienteil.jpg':     'Bedieneinheit|Control unit',
    'Bedienteil-e1.jpg':  'Bedieneinheit e1|Control unit e1',
    'W001-1.jpg':         'Warnhinweis|Warning notice',
    'Information.jpg':    'Hinweis|Note',
    'Hochdruckreiniger.png': 'Kein Hochdruckreiniger verwenden|Do not use high-pressure cleaner',
    'Bunker-Fuellung.jpg':'Maximale Bunkerfüllung|Maximum hopper fill level',
    'Bunker-Foerdervolumen.jpg': 'Fördervolumen-Diagramm|Conveying volume diagram',
    'Gurtspannung-einstellen.jpg': 'Gurtspannung einstellen|Setting belt tension',
    'Gurt-Durchhang.jpg': 'Gurt-Durchhang|Belt sag',
    'Gurtlauf-links.jpg': 'Gurtlauf nach links korrigieren|Correcting belt run to the left',
    'Gurtlauf-rechts.jpg':'Gurtlauf nach rechts korrigieren|Correcting belt run to the right',
    'Gurtabstreifer.jpg': 'Gurtabstreifer|Belt scraper',
    'Trommelabstreifer.jpg': 'Trommelabstreifer|Drum scraper',
    'Trommelantrieb.jpg': 'Trommelantrieb|Drum drive',
    'Trommelantrieb3.jpg':'Trommelantrieb Detail|Drum drive detail',
    'Trommelantrieb5.jpg':'Trommelantrieb Ausrichtung|Drum drive alignment',
    'Reinigungsbuerste-Einstellmechnismus.jpg': 'Reinigungsbürste Einstellmechanismus|Cleaning brush adjustment mechanism',
    'Reinigungsbuerste-Einstellung-2.jpg': 'Reinigungsbürste Einstellung|Cleaning brush adjustment',
    'Kabelfernbedienung.jpg': 'Kabelfernbedienung|Cable remote control',
    'Seilwinde.jpg':      'Seilwinde|Cable winch',
    'Stuetzfuss.jpg':     'Teleskopstützfuß Detail|Telescopic support foot detail',
    'Wartungstuere.jpg':  'Wartungstüre|Maintenance door',
    'e1-rh6.jpg':         'Gremac e1 Radfahrzeug|Gremac e1 wheeled vehicle',
    'e1-Bunker-2.jpg':    'Gremac e1 Bunker|Gremac e1 hopper',
    'e2-1.jpg':           'Gremac e2+ Übersicht|Gremac e2+ overview',
    'e2-Fahrwerk.jpg':    'Gremac e2+ Fahrwerk|Gremac e2+ undercarriage',
    'e3-3.jpg':           'Gremac e3 Übersicht|Gremac e3 overview',
}

# ─── PocketBase Helpers ───────────────────────────────────────────────────────

def pb_request(path, method='GET', data=None, token=None):
    url = f'{PB_URL}{path}'
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise Exception(f'HTTP {e.code}: {body}')

def get_token():
    resp = pb_request('/api/collections/_superusers/auth-with-password', 'POST',
                      {'identity': PB_EMAIL, 'password': PB_PASSWORD})
    return resp['token']

def get_all_records(col, token, per_page=500):
    page, items = 1, []
    while True:
        r = pb_request(f'/api/collections/{col}/records?perPage={per_page}&page={page}', token=token)
        items.extend(r.get('items', []))
        if len(items) >= r.get('totalItems', 0):
            break
        page += 1
    return items

# ─── Parser ───────────────────────────────────────────────────────────────────

H2_RE = re.compile(r'<h2[^>]*>.*?<a id=\"([^\"]*)\".*?</a>([^<]+)</h2>', re.IGNORECASE)
H3_RE = re.compile(r'<h3[^>]*>.*?<a id=\"([^\"]*)\".*?</a>([^<]+)</h3>', re.IGNORECASE)
IMG_RE = re.compile(r'<img\s+src="(/images/manuals/([^"]+))"[^>]*>', re.IGNORECASE)

# Entferne den generierten Header-Block am Anfang
HEADER_END_RE = re.compile(r'</div>\s*\n', re.MULTILINE)

def strip_header(content):
    """Entfernt den generierten Header (bis zum ersten h2-Abschnitt)."""
    # Finde ersten echten h2 mit id (nicht den Titel-h2)
    match = re.search(r'\n<h2 style="color:#058B8C', content)
    if match:
        return content[match.start():]
    return content

def parse_blocks(content_de, content_en):
    """
    Parst DE+EN Content und gibt Liste von Block-Dicts zurück:
    [{title_de, title_en, content_de, content_en, heading_level, images, image_alt_de, image_alt_en}]
    """
    content_de = strip_header(content_de)
    content_en = strip_header(content_en) if content_en else ''

    # Zerlege DE in Abschnitte
    blocks_de = split_into_sections(content_de)
    blocks_en = split_into_sections(content_en) if content_en else {}

    result = []
    for key, (title_de, level, body_de) in blocks_de.items():
        body_en = ''
        title_en = ''
        if key in blocks_en:
            title_en, _, body_en = blocks_en[key]

        # Bilder aus DE-Content extrahieren
        images = []
        alts_de = []
        alts_en = []
        for m in IMG_RE.finditer(body_de):
            img_path = m.group(1)
            img_file = m.group(2)
            images.append(img_path)
            alt_str = IMAGE_ALTS.get(img_file, '')
            if '|' in alt_str:
                alt_de, alt_en = alt_str.split('|', 1)
            else:
                alt_de = alt_en = alt_str
            alts_de.append(alt_de)
            alts_en.append(alt_en)

        # Bilder aus Content entfernen (werden über images-Feld gerendert)
        body_de_clean = IMG_RE.sub('', body_de).strip()
        body_en_clean = IMG_RE.sub('', body_en).strip() if body_en else ''

        result.append({
            'title_de': title_de.strip(),
            'title_en': title_en.strip(),
            'content_de': body_de_clean,
            'content_en': body_en_clean,
            'heading_level': level,
            'images': images if images else None,
            'image_alt_de': ' | '.join(alts_de) if alts_de else '',
            'image_alt_en': ' | '.join(alts_en) if alts_en else '',
            '_anchor': key,
        })

    return result

def split_into_sections(content):
    """
    Zerlegt Content in Abschnitte anhand von h2/h3.
    Returns: {anchor: (title, level, body)}
    """
    sections = {}
    current_anchor = '__intro__'
    current_title = ''
    current_level = 2
    current_body = []

    for line in content.splitlines(keepends=True):
        m2 = H2_RE.search(line)
        m3 = H3_RE.search(line)
        if m2 or m3:
            # Speichere vorherigen Block
            if current_body:
                sections[current_anchor] = (current_title, current_level, ''.join(current_body).strip())
            m = m2 or m3
            current_anchor = m.group(1)
            current_title = m.group(2).strip()
            # Bereinige Strong-Tags
            current_title = re.sub(r'</?strong>', '', current_title)
            current_level = 2 if m2 else 3
            current_body = []
        else:
            current_body.append(line)

    # Letzten Block
    if current_body:
        sections[current_anchor] = (current_title, current_level, ''.join(current_body).strip())

    return sections

# ─── Hauptlogik ───────────────────────────────────────────────────────────────

def main():
    dry_run = '--dry-run' in sys.argv

    print('🔐 PocketBase Auth...')
    token = get_token()

    print('📋 Lade bestehende Blöcke aus PocketBase...')
    existing_blocks = get_all_records('kb_blocks', token)
    existing_by_title = {b['title_de']: b for b in existing_blocks}
    print(f'   {len(existing_blocks)} Blöcke vorhanden')

    print('📋 Lade Struktur...')
    existing_structure = get_all_records('kb_structure', token)
    # Welche (manual_id, sort_order) Kombinationen gibt es schon?
    existing_entries = {(s['manual'], s['sort_order']): s for s in existing_structure}

    for slug, manual_id in MANUAL_SLUGS.items():
        # Dateinamen: eZero.de.md oder ezero.de.md
        de_file = None
        # Suche nach Original-Dateien (Groß/Kleinschreibung)
        slug_map = {'ezero': 'eZero', 'e1': 'e1', 'e2plus': 'e2plus', 'e3': 'e3'}
        canonical = slug_map.get(slug, slug)
        for candidate in [f'{canonical}.de.md', f'{slug}.de.md']:
            if candidate:
                path = os.path.join(CONTENT_DIR, candidate)
                if os.path.exists(path):
                    de_file = path
                    break

        if not de_file:
            print(f'⚠️  Keine DE-Datei für {slug} gefunden, überspringe')
            continue

        en_file = de_file.replace('.de.md', '.en.md')
        en_file_alt = de_file.replace('.de.md', '').replace(slug, slug) + '.en.md'

        content_de = open(de_file).read()
        content_en = open(en_file).read() if os.path.exists(en_file) else ''

        print(f'\n📖 Verarbeite {slug} ({os.path.basename(de_file)})')

        blocks = parse_blocks(content_de, content_en)
        print(f'   {len(blocks)} Blöcke geparst')

        sort_order = 1
        new_blocks = 0
        updated_blocks = 0
        new_structure = 0

        for block_data in blocks:
            title_de = block_data['title_de']
            if not title_de and not block_data['content_de']:
                continue

            # Prüfe ob Block schon existiert (per Titel-Match)
            if title_de in existing_by_title:
                block_id = existing_by_title[title_de]['id']
                # Update falls Bilder fehlen
                if not existing_by_title[title_de].get('images') and block_data.get('images'):
                    if not dry_run:
                        pb_request(f'/api/collections/kb_blocks/records/{block_id}',
                            'PATCH', {
                                'images': block_data['images'],
                                'image_alt_de': block_data['image_alt_de'],
                                'image_alt_en': block_data['image_alt_en'],
                            }, token)
                    updated_blocks += 1
            else:
                # Neuer Block
                payload = {
                    'title_de': title_de or f'{slug}_{sort_order}',
                    'title_en': block_data['title_en'],
                    'content_de': block_data['content_de'],
                    'content_en': block_data['content_en'],
                    'category': 'manual',
                    'shared': False,
                    'images': block_data['images'],
                    'image_alt_de': block_data['image_alt_de'],
                    'image_alt_en': block_data['image_alt_en'],
                }
                if not dry_run:
                    result = pb_request('/api/collections/kb_blocks/records', 'POST', payload, token)
                    block_id = result['id']
                    existing_by_title[title_de] = result
                else:
                    block_id = f'dry_{sort_order}'
                new_blocks += 1

            # Struktur-Eintrag erstellen
            if (manual_id, sort_order) not in existing_entries:
                struct_payload = {
                    'manual': manual_id,
                    'block': block_id,
                    'sort_order': sort_order,
                    'heading_level': block_data['heading_level'],
                }
                if not dry_run:
                    pb_request('/api/collections/kb_structure/records', 'POST', struct_payload, token)
                    existing_entries[(manual_id, sort_order)] = struct_payload
                new_structure += 1

            sort_order += 1

        print(f'   ✅ Neue Blöcke: {new_blocks} | Aktualisiert: {updated_blocks} | Neue Struktur: {new_structure}')

    # Shared-Blöcke identifizieren (gleicher Titel in mehreren Manuals)
    print('\n🔍 Identifiziere Shared-Blöcke...')
    all_blocks_updated = get_all_records('kb_blocks', token)
    all_structure = get_all_records('kb_structure', token)

    block_in_manuals = defaultdict(set)
    for s in all_structure:
        block_in_manuals[s['block']].add(s['manual'])

    shared_count = 0
    for block_id, manuals in block_in_manuals.items():
        if len(manuals) > 1:
            if not dry_run:
                pb_request(f'/api/collections/kb_blocks/records/{block_id}',
                    'PATCH', {'shared': True}, token)
            shared_count += 1

    print(f'   ✅ {shared_count} Shared-Blöcke markiert')

    if dry_run:
        print('\n[DRY RUN - keine Änderungen gespeichert]')
    else:
        print('\n🎉 Import abgeschlossen!')

if __name__ == '__main__':
    main()
