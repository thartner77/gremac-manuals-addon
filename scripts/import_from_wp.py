#!/usr/bin/env python3
"""
GREMAC Full Import: WordPress HTML → PocketBase Blöcke
======================================================
Holt vollständigen Inhalt aller 4 Betriebsanleitungen aus WordPress,
zerlegt in strukturierte Blöcke und importiert in PocketBase.

Löscht ERST alle alten kb_structure-Einträge für ein Manual,
dann importiert neu → sauberer, idempotenter Import.

Verwendung:
    python3 import_from_wp.py [--dry-run] [--manual ezero|e1|e2plus|e3]
"""

import json, re, sys, os
import urllib.request, urllib.error
from collections import defaultdict

PB_URL   = 'http://localhost:8090'
WP_BASE  = 'https://service.h2protech.de/wp-json/wp/v2/epkb_post_type_1'
IMAGES_BASE = '/images/manuals'

# Lokale Bilder (verfügbar in /var/www/gremac.net/static/images/manuals/)
LOCAL_IMAGES = set()
LOCAL_IMG_DIR = '/var/www/gremac.net/static/images/manuals'
if os.path.exists(LOCAL_IMG_DIR):
    LOCAL_IMAGES = set(os.listdir(LOCAL_IMG_DIR))

MANUALS = {
    'ezero': {
        'slug_de': 'gremac-ezero-betriebsanleitung',
        'slug_en': 'gremac-ezero-instruction-manual',
        'pb_id':   'd4a6b3l0p19p1v0',
        'title_de': 'Gremac eZero Betriebsanleitung',
        'title_en': 'Gremac eZero Operating Manual',
    },
    'e1': {
        'slug_de': 'gremac-e1-betriebsanleitung',
        'slug_en': 'gremac-e1-operating-manual',
        'pb_id':   'c0ivaz05t14lbts',
        'title_de': 'Gremac e1 Betriebsanleitung',
        'title_en': 'Gremac e1 Operating Manual',
    },
    'e2plus': {
        'slug_de': 'gremac-e2-betriebsanleitung',
        'slug_en': 'gremac-e2-instruction-manual',
        'pb_id':   's02o80ljb6u72rz',
        'title_de': 'Gremac e2+ Betriebsanleitung',
        'title_en': 'Gremac e2+ Operating Manual',
    },
    'e3': {
        'slug_de': 'gremac-e3-betriebsanleitung',
        'slug_en': 'gremac-e3-operating-instructions',
        'pb_id':   '0d52710r735q5zv',
        'title_de': 'Gremac e3 Betriebsanleitung',
        'title_en': 'Gremac e3 Operating Manual',
    },
}

IMG_STYLE = (
    'max-width:100%;height:auto;border-radius:6px;'
    'margin:1.5rem 0;box-shadow:0 2px 10px rgba(0,0,0,.12);display:block;'
)
ICON_STYLE = 'width:80px;height:auto;margin:.5rem 1rem .5rem 0;vertical-align:middle;'

# Symbole die als kleine inline Icons im Text bleiben (NICHT ins images-Feld)
ICON_FILES = {'W001-1.jpg', 'Information.jpg', 'Hochdruckreiniger.png'}
# Diese Dateien werden im Content-HTML belassen und NICHT in extract_images_from_html extrahiert
INLINE_ICONS = ICON_FILES


# ─── PocketBase ───────────────────────────────────────────────────────────────

def get_token():
    data = json.dumps({'identity': 'admin@gremac.net', 'password': 'Gremac2026!'}).encode()
    req = urllib.request.Request(
        f'{PB_URL}/api/collections/_superusers/auth-with-password',
        data=data, headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())['token']

def pb(path, method='GET', data=None, token=None):
    url = f'{PB_URL}{path}'
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise Exception(f'HTTP {e.code}: {e.read().decode()[:300]}')

def get_all(collection, token, filt=None, per_page=500):
    page, items = 1, []
    while True:
        path = f'/api/collections/{collection}/records?perPage={per_page}&page={page}'
        if filt:
            path += f'&filter={urllib.parse.quote(filt)}'
        r = pb(path, token=token)
        items.extend(r.get('items', []))
        if len(items) >= r.get('totalItems', 0):
            break
        page += 1
    return items

import urllib.parse


# ─── WordPress-Fetch ──────────────────────────────────────────────────────────

def fetch_wp(slug, lang='de'):
    """Holt WP-Artikel per Slug und Sprache."""
    # WPML language parameter
    url = f'{WP_BASE}?slug={slug}&per_page=1&lang={lang}'
    try:
        with urllib.request.urlopen(url) as r:
            data = json.loads(r.read())
        if data:
            return data[0].get('content', {}).get('rendered', '')
    except Exception as e:
        print(f'   ⚠️  WP-Fetch fehlgeschlagen ({slug}, {lang}): {e}')
    return ''


# ─── HTML-Bereinigung ─────────────────────────────────────────────────────────

def clean_wp_html(html):
    """Bereinigt WordPress Gutenberg/UAGB-HTML."""
    # IMH-6310 Hotspot-Blöcke: Hauptbild extrahieren, Rest entfernen
    # Das Hauptbild steckt in einem <img> aus /wp-content/uploads/ (nicht Plugin-Icons)
    def extract_hotspot_img(m):
        block = m.group(0)
        # Nur Upload-Bilder (nicht Plugin-Assets wie zoom-in.png)
        imgs = re.findall(
            r'<img[^>]+src="(https://service\.h2protech\.de/wp-content/uploads/[^"]+\.(?:jpg|png|webp))"',
            block
        )
        if imgs:
            # Erstes Upload-Bild = Hauptbild (nicht die srcset-Varianten)
            fname = imgs[0].split('/')[-1].split('?')[0]
            fname_clean = re.sub(r'-e\d{13}', '', fname)
            fname_clean = re.sub(r'-\d+x\d+', '', fname_clean)
            return f'\n<img src="{IMAGES_BASE}/{fname_clean}" alt="" style="{IMG_STYLE}">\n'
        return ''

    html = re.sub(
        r'<div[^>]+class="imh-6310-annotation-box-wrapper[^"]*"[^>]*>.*?(?=<h[23]|<p class="has-text|</section|$)',
        extract_hotspot_img,
        html,
        flags=re.DOTALL
    )

    # WP Block-Wrapper
    html = re.sub(r'<div[^>]+class="[^"]*wp-block[^"]*"[^>]*>', '', html)
    html = re.sub(r'<div[^>]+class="[^"]*uagb[^"]*"[^>]*>', '', html)
    # Aria-hidden Spacer
    html = re.sub(r'<div[^>]+aria-hidden[^"]*"true"[^>]*[^/]*/>', '', html)
    html = re.sub(r'<div[^>]+style="height:\d+px"[^>]*></div>', '', html)
    # UAGB Überschriften normalisieren
    html = re.sub(r'<h([23]) class="uagb-heading-text">', r'<h\1>', html)
    # WP Block Headings normalisieren
    html = re.sub(r'<h([23]) class="wp-block-heading[^"]*">', r'<h\1>', html)
    # Figure-Tags verarbeiten:
    # - Inline-Icons (W001, Information, Hochdruckreiniger) → kleines inline img
    # - Alle anderen Bilder → normales img (wird später von extract_images_from_html verarbeitet)
    def replace_figure(m):
        full = m.group(0)
        # Inline-Icon?
        for icon in INLINE_ICONS:
            if icon.replace('.jpg','').replace('.png','') in full:
                return f'<img src="{IMAGES_BASE}/{icon}" alt="" style="{ICON_STYLE}">'
        # Normales Upload-Bild extrahieren
        img_m = re.search(
            r'<img[^>]+src="(https://service\.h2protech\.de/wp-content/uploads/[^"]+\.(?:jpg|png|webp))"',
            full
        )
        if img_m:
            src = img_m.group(1)
            fname = src.split('/')[-1].split('?')[0]
            fname = re.sub(r'-e\d{13}', '', fname)
            fname = re.sub(r'-\d+x\d+', '', fname)
            fname = fname.replace('-scaled', '') if fname.replace('-scaled','') else fname
            return f'<img src="{IMAGES_BASE}/{fname}" alt="{fname}" style="{IMG_STYLE}">'
        return ''

    # Figure → img (VOR div-Bereinigung!)
    html = re.sub(
        r'<figure[^>]*>.*?</figure>',
        replace_figure,
        html,
        flags=re.DOTALL
    )
    # Restliche Figcaptions
    html = re.sub(r'<figcaption[^>]*>.*?</figcaption>', '', html, flags=re.DOTALL)
    html = re.sub(r'<figure[^>]*>', '', html)
    html = re.sub(r'</figure>', '', html)
    # Schließende divs
    html = re.sub(r'</div>', '\n', html)
    # Leere p-Tags
    html = re.sub(r'<p[^>]*>\s*</p>', '', html)
    # Mehrfache Leerzeilen
    html = re.sub(r'\n{4,}', '\n\n\n', html)
    return html.strip()


# ─── Bild-Extraktion ──────────────────────────────────────────────────────────

def extract_images_from_html(html):
    """
    Extrahiert img-Tags, normalisiert auf lokale Dateipfade.
    Gibt Liste von dicts: {path, filename, style}
    Filtert Plugin-Assets heraus (nur /wp-content/uploads/ oder lokale manuals-Pfade).
    """
    results = []
    for m in re.finditer(r'<img[^>]+src="([^"]*)"[^>]*>', html, re.IGNORECASE):
        src = m.group(1)
        # Plugin-Assets herausfiltern
        if '/plugins/' in src:
            continue
        if 'zoom-in' in src or 'zoom-out' in src:
            continue
        fname = src.split('/')[-1].split('?')[0]
        if not fname or '.' not in fname:
            continue
        # WP Timestamp-Suffix entfernen
        fname_clean = re.sub(r'-e\d{13}', '', fname)
        # Größen-Suffix entfernen: -1024x661
        fname_clean = re.sub(r'-\d+x\d+', '', fname_clean)
        # Scaling-Suffix
        if fname_clean not in LOCAL_IMAGES:
            alt = fname_clean.replace('-scaled', '')
            if alt in LOCAL_IMAGES:
                fname_clean = alt
        # Inline-Icons bleiben im Content-Text — nicht ins images-Feld extrahieren
        if fname_clean in INLINE_ICONS:
            continue
        local_path = f'{IMAGES_BASE}/{fname_clean}'
        results.append({'path': local_path, 'filename': fname_clean, 'style': IMG_STYLE})
    return results


def images_to_html(images):
    """Wandelt Image-Dicts in HTML um."""
    parts = []
    for img in images:
        parts.append('<img src="' + img['path'] + '" alt="" style="' + img['style'] + '">\n')
    return ''.join(parts)


# ─── Abschnitt-Parser ─────────────────────────────────────────────────────────

def parse_sections(html):
    """
    Zerlegt bereinigtes HTML in Abschnitte.
    Gibt Liste von: {title, level, content_html, images}
    """
    sections = []
    current_title = ''
    current_level = 0
    current_lines = []

    def flush():
        if not (current_lines or current_title):
            return
        body = '\n'.join(current_lines).strip()
        images = extract_images_from_html(body)
        # NUR Block-Bilder aus Content entfernen (nicht Inline-Icons!)
        # Inline-Icons (W001, Information, Hochdruckreiniger) bleiben im Content
        def remove_non_inline_imgs(html):
            def keep_or_remove(m):
                src = re.search(r'src="([^"]*)"', m.group(0))
                if src:
                    fname = src.group(1).split('/')[-1]
                    if any(icon in fname for icon in INLINE_ICONS):
                        return m.group(0)  # Behalten
                return ''  # Entfernen
            return re.sub(r'<img[^>]+>', keep_or_remove, html)
        body_no_img = remove_non_inline_imgs(body)
        body_no_img = re.sub(r'\n{3,}', '\n\n', body_no_img).strip()
        sections.append({
            'title': current_title,
            'level': current_level,
            'content_html': body_no_img,
            'images': images,
        })

    for line in html.splitlines():
        m2 = re.match(r'\s*<h2[^>]*>(.*?)</h2>\s*$', line, re.IGNORECASE)
        m3 = re.match(r'\s*<h3[^>]*>(.*?)</h3>\s*$', line, re.IGNORECASE)
        if m2 or m3:
            flush()
            m = m2 or m3
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            title = re.sub(r'\s+', ' ', title)
            current_title = title
            current_level = 2 if m2 else 3
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return sections


# ─── Shared-Block-Erkennung ───────────────────────────────────────────────────

def find_shared_blocks(all_sections_by_manual):
    """
    Erkennt Blöcke die identisch in mehreren Anleitungen vorkommen.
    Vergleich per Titel (Groß-/Kleinschreibung ignoriert).
    """
    title_count = defaultdict(list)
    for manual_key, sections in all_sections_by_manual.items():
        for s in sections:
            if s['title']:
                title_count[s['title'].lower()].append(manual_key)
    return {t: manuals for t, manuals in title_count.items() if len(manuals) > 1}


# ─── Hauptimport ──────────────────────────────────────────────────────────────

def main():
    dry_run  = '--dry-run'  in sys.argv
    only_manual = None
    if '--manual' in sys.argv:
        idx = sys.argv.index('--manual')
        if idx + 1 < len(sys.argv):
            only_manual = sys.argv[idx + 1]

    print('🔐 PocketBase Auth...')
    token = get_token()
    print('   ✅ OK')

    # Bestehende Blöcke laden (für Deduplizierung)
    print('📦 Lade bestehende Blöcke...')
    existing_blocks = get_all('kb_blocks', token)
    blocks_by_title = {}
    for b in existing_blocks:
        t = (b.get('title_de', '') or '').lower().strip()
        if t:
            blocks_by_title[t] = b
    print(f'   {len(existing_blocks)} Blöcke vorhanden')

    # ── Alle WP-Inhalte holen ──
    print('\n🌐 Hole WordPress-Inhalte...')
    all_sections = {}
    for key, manual in MANUALS.items():
        if only_manual and key != only_manual:
            continue
        html_de = fetch_wp(manual['slug_de'], 'de')
        html_en = fetch_wp(manual['slug_en'], 'en')
        if not html_de:
            # Fallback: gecachte Datei
            cached = f'/tmp/wp_{key}_de.html'
            if os.path.exists(cached):
                html_de = open(cached).read()
                print(f'   {key} DE: aus Cache')
            else:
                print(f'   ⚠️  {key} DE: kein Inhalt!')
                continue
        else:
            open(f'/tmp/wp_{key}_de.html', 'w').write(html_de)

        if html_en:
            open(f'/tmp/wp_{key}_en.html', 'w').write(html_en)
        else:
            html_en = open(f'/tmp/wp_{key}_en.html').read() if os.path.exists(f'/tmp/wp_{key}_en.html') else ''

        sections_de = parse_sections(clean_wp_html(html_de))
        sections_en = parse_sections(clean_wp_html(html_en))
        # EN nach Titel indexieren für Matching
        en_by_title = {s['title'].lower(): s for s in sections_en}

        all_sections[key] = {
            'manual': manual,
            'sections_de': sections_de,
            'en_by_title': en_by_title,
        }
        print(f'   {key}: {len(sections_de)} DE-Abschnitte, {len(sections_en)} EN-Abschnitte')

    # ── Shared-Blöcke erkennen ──
    print('\n🔍 Erkenne Shared-Blöcke...')
    shared_titles = find_shared_blocks({k: v['sections_de'] for k, v in all_sections.items()})
    print(f'   {len(shared_titles)} Titel kommen in >1 Anleitung vor')
    if shared_titles:
        for t, manuals in list(shared_titles.items())[:5]:
            print(f'   "{t[:50]}" in: {manuals}')

    # ── Import pro Manual ──
    print()
    shared_block_cache = {}  # title_lower → block_id (damit shared Blöcke nur 1x erstellt werden)

    for key, data in all_sections.items():
        manual = data['manual']
        sections_de = data['sections_de']
        en_by_title = data['en_by_title']
        manual_id = manual['pb_id']

        print(f'📖 Importiere {key} ({len(sections_de)} Abschnitte)...')

        # Alte Struktur-Einträge löschen (clean re-import)
        old_structure = get_all('kb_structure', token, filt=f'manual="{manual_id}"')
        if old_structure and not dry_run:
            print(f'   🗑️  Lösche {len(old_structure)} alte Struktur-Einträge...')
            for s in old_structure:
                pb(f'/api/collections/kb_structure/records/{s["id"]}', 'DELETE', token=token)

        new_blocks = 0
        reused_blocks = 0
        sort_order = 1

        for section in sections_de:
            title_de = section['title']
            title_lower = title_de.lower().strip()
            level = section['level']
            content_de = section['content_html']

            # EN-Entsprechung suchen
            en_section = en_by_title.get(title_lower, {})
            title_en = en_section.get('title', '')
            content_en = en_section.get('content_html', '')

            # Bilder
            images = section['images']
            image_paths = [img['path'] for img in images] if images else None
            alt_de = ' | '.join(img['filename'].rsplit('.', 1)[0] for img in images) if images else ''
            alt_en = alt_de  # Vorerst gleich, kann später manuell gepflegt werden

            # Nur als shared markieren wenn der Block KEINE Bilder hat
            # Blöcke mit Bildern sind maschinenspezifisch → nie shared
            is_shared = (title_lower in shared_titles) and not image_paths

            # Überspringe leere Blöcke ohne Titel und Inhalt
            if not title_de and not content_de.strip():
                continue

            # Category aus Titel/Inhalt ableiten
            def guess_category(title, content):
                t = (title + ' ' + content).lower()
                if any(w in t for w in ['sicherheit', 'warnung', 'gefahr', 'vorsicht', 'safety', 'warning']):
                    return 'safety'
                if any(w in t for w in ['wartung', 'instandhaltung', 'maintenance', 'schmierung', 'inspektion']):
                    return 'maintenance'
                if any(w in t for w in ['einleitung', 'vorwort', 'produktbeschreibung', 'introduction', 'description']):
                    return 'intro'
                if any(w in t for w in ['bedienung', 'betrieb', 'inbetriebnahme', 'starten', 'operation', 'start']):
                    return 'operation'
                if any(w in t for w in ['technisch', 'daten', 'technical', 'abmessung', 'gewicht']):
                    return 'technical'
                if any(w in t for w in ['kontakt', 'adresse', 'vertrieb', 'contact', 'address']):
                    return 'contact'
                return 'other'

            # Block-ID bestimmen
            if is_shared and title_lower in shared_block_cache:
                block_id = shared_block_cache[title_lower]
                reused_blocks += 1
            elif title_lower in blocks_by_title:
                existing = blocks_by_title[title_lower]
                existing_images = existing.get('images') or []
                # Bilder-Konflikt: existierender Block hat andere Bilder → neuer Block
                # (maschinenspezifische Abschnitte mit gleichem Titel aber verschiedenen Bildern)
                if image_paths and existing_images and set(image_paths) != set(existing_images):
                    cat = guess_category(title_de, content_de)
                    block_data = {
                        'title_de': title_de or f'Block {sort_order}',
                        'title_en': title_en or title_de or f'Block {sort_order}',
                        'content_de': content_de or ' ',
                        'content_en': content_en or ' ',
                        'category': cat,
                        'shared': False,
                        'images': image_paths,
                        'image_alt_de': alt_de,
                        'image_alt_en': alt_en,
                    }
                    if not dry_run:
                        result = pb('/api/collections/kb_blocks/records', 'POST', block_data, token)
                        block_id = result['id']
                    else:
                        block_id = f'dry_new_{sort_order}'
                    new_blocks += 1
                else:
                    # Block wiederverwenden
                    block_id = existing['id']
                    update_data = {
                        'content_de': content_de or ' ',
                        'content_en': content_en or ' ',
                        'shared': is_shared,
                    }
                    # Bilder nur aktualisieren wenn dieser Import welche hat
                    # → kein Bild im aktuellen Manual = bestehendes Bild behalten
                    if image_paths:
                        update_data['images'] = image_paths
                        update_data['image_alt_de'] = alt_de
                        update_data['image_alt_en'] = alt_en
                    if not dry_run:
                        pb(f'/api/collections/kb_blocks/records/{block_id}', 'PATCH', update_data, token)
                    if is_shared:
                        shared_block_cache[title_lower] = block_id
                    reused_blocks += 1
            else:
                # Neuer Block
                cat = guess_category(title_de, content_de)
                block_data = {
                    'title_de': title_de or f'Block {sort_order}',
                    'title_en': title_en or title_de or f'Block {sort_order}',
                    'content_de': content_de or ' ',
                    'content_en': content_en or ' ',
                    'category': cat,
                    'shared': is_shared,
                    'images': image_paths,
                    'image_alt_de': alt_de,
                    'image_alt_en': alt_en,
                }
                if not dry_run:
                    result = pb('/api/collections/kb_blocks/records', 'POST', block_data, token)
                    block_id = result['id']
                    blocks_by_title[title_lower] = result
                    if is_shared:
                        shared_block_cache[title_lower] = block_id
                else:
                    block_id = f'dry_{sort_order}'
                    if is_shared:
                        shared_block_cache[title_lower] = block_id
                new_blocks += 1

            # Struktur-Eintrag
            if not dry_run:
                pb('/api/collections/kb_structure/records', 'POST', {
                    'manual': manual_id,
                    'block': block_id,
                    'sort_order': sort_order,
                    'heading_level': level,
                }, token)

            sort_order += 1

        print(f'   ✅ Neue Blöcke: {new_blocks} | Wiederverwendet: {reused_blocks} | Gesamt: {sort_order-1}')

    if dry_run:
        print('\n[DRY RUN – keine Änderungen gespeichert]')
    else:
        print('\n🎉 Import abgeschlossen!')
        print('   Führe jetzt build_manuals.py aus um Hugo-Dateien zu generieren.')

if __name__ == '__main__':
    main()
