#!/usr/bin/env python3
"""
Importiert Textblöcke aus den extrahierten Markdown-Dateien in PocketBase.
Läuft auf dem Ben-Server, spricht gegen den GREMAC-VPS via SSH-Tunnel oder direkt.
"""
import json, re, sys
import urllib.request, urllib.parse

PB_URL = "http://127.0.0.1:8090"
PB_EMAIL = "admin@gremac.net"
PB_PASSWORD = "Gremac2026!"

def pb_post(path, data, token=""):
    url = PB_URL + path
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def pb_get(path, token=""):
    url = PB_URL + path
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

# Auth
auth = pb_post("/api/collections/_superusers/auth-with-password",
    {"identity": PB_EMAIL, "password": PB_PASSWORD})
TOKEN = auth.get("token", "")
if not TOKEN:
    print("AUTH FEHLER:", auth)
    sys.exit(1)
print(f"✅ Auth OK")

# Manuals laden
manuals_r = pb_get("/api/collections/kb_manuals/records?perPage=50", TOKEN)
manuals = {m["slug"]: m["id"] for m in manuals_r.get("items", [])}
print(f"Manuals: {list(manuals.keys())}")

def detect_category(title):
    t = title.lower()
    if any(w in t for w in ['sicherheit','gefahr','warnung','achtung','schutz','safety']):
        return 'safety'
    if any(w in t for w in ['wartung','instandhaltung','maintenance','reinigung','inspektion']):
        return 'maintenance'
    if any(w in t for w in ['vorwort','einleitung','introduction','bestimmung','zweck']):
        return 'intro'
    if any(w in t for w in ['bedienung','betrieb','operation','inbetriebnahme','transport']):
        return 'operation'
    if any(w in t for w in ['techni','daten','specification','abmessung','gewicht','maß']):
        return 'technical'
    if any(w in t for w in ['kontakt','adresse','contact','service','vertrieb','hersteller']):
        return 'contact'
    return 'other'

def parse_chapters(filepath):
    with open(filepath) as f:
        content = f.read()
    content = re.sub(r'^---.*?---\n', '', content, flags=re.DOTALL)
    
    lines = content.split('\n')
    chapters = []
    current_title = "Einleitung"
    current_body = []
    
    for line in lines:
        stripped = line.strip()
        is_heading = (stripped and 3 < len(stripped) < 70 and
                      stripped[0].isupper() and
                      not stripped.startswith('#') and
                      not stripped.startswith('-') and
                      not stripped.startswith('*') and
                      not stripped[0].isdigit() and
                      len(stripped.split()) <= 8)
        
        if is_heading and len(current_body) > 5:
            body = '\n'.join(current_body).strip()
            if len(body) > 50:
                chapters.append((current_title, body))
            current_title = stripped
            current_body = []
        else:
            current_body.append(line)
    
    if current_body:
        body = '\n'.join(current_body).strip()
        if len(body) > 50:
            chapters.append((current_title, body))
    
    return chapters

import glob, os

file_map = {
    "gremac-e1-betriebsanleitung.md": "gremac-e1",
    "gremac-e2-betriebsanleitung.md": "gremac-e2plus",
    "gremac-ezero-betriebsanleitung.md": "gremac-ezero",
    "gremac-e3-betriebsanleitung.md": "gremac-e3",
}

base = "/root/.openclaw/workspace/gremac-manuals-addon/content/de"
total_blocks = 0

for fname, slug in file_map.items():
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        print(f"❌ Nicht gefunden: {fname}")
        continue
    
    manual_id = manuals.get(slug)
    if not manual_id:
        print(f"❌ Manual-ID nicht gefunden: {slug}")
        continue
    
    chapters = parse_chapters(fpath)
    print(f"\n📖 {slug}: {len(chapters)} Kapitel erkannt")
    
    for i, (title, body) in enumerate(chapters[:30]):  # Max 30 pro Anleitung
        category = detect_category(title)
        block = pb_post("/api/collections/kb_blocks/records", {
            "title_de": title[:200],
            "title_en": "",
            "content_de": body[:20000],
            "content_en": "",
            "category": category,
            "shared": False
        }, TOKEN)
        
        block_id = block.get("id")
        if not block_id:
            print(f"  ❌ Block-Fehler: {block.get('message','')}")
            continue
        
        # Verknüpfen
        pb_post("/api/collections/kb_structure/records", {
            "manual": manual_id,
            "block": block_id,
            "sort_order": i + 1,
            "heading_level": 2
        }, TOKEN)
        
        total_blocks += 1
        if i < 4:
            print(f"  ✅ [{category}] {title[:50]}")
    
    print(f"  → Fertig")

print(f"\n🎉 Gesamt importiert: {total_blocks} Blöcke")
