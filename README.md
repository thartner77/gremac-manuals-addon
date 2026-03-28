# GREMAC Manuals Add-on

Modulares Redaktionssystem für GREMAC Betriebsanleitungen.
**Single Source of Truth: PocketBase**

## Architektur

```
WordPress (Quelle)
     │
     │  import_from_wp.py
     ▼
PocketBase (Datenhaltung)
  kb_manuals    – 4 Maschinen (eZero, e1, e2+, e3)
  kb_blocks     – 333 Inhaltsblöcke (DE + EN + Bilder)
  kb_structure  – Reihenfolge: welcher Block in welchem Manual
     │
     │  build_manuals.py
     ▼
Hugo Markdown (generiert, NICHT manuell bearbeiten!)
  /content/betriebsanleitungen/ezero.de.md
  /content/betriebsanleitungen/ezero.en.md
  ... (8 Dateien total)
     │
     │  hugo --minify
     ▼
preview.gremac.net/betriebsanleitungen/
```

## Workflow: Inhalt ändern

1. Block in PocketBase bearbeiten (http://localhost:8090/_/)
2. Build-Script ausführen:
   ```bash
   ssh root@87.106.11.113
   cd /var/www/gremac.net && python3 scripts/build_manuals.py
   ```
3. Fertig – alle Anleitungen die diesen Block nutzen sind aktuell

## Scripts

### import_from_wp.py
Importiert vollständige Betriebsanleitungen aus WordPress in PocketBase.
- Holt HTML via WP REST API
- Zerlegt in Abschnitte (h2/h3)
- Erkennt automatisch Shared-Blöcke (gleicher Titel in mehreren Anleitungen)
- Weist Bilder den Blöcken zu
- Löscht alte Struktur-Einträge vor dem Re-Import (idempotent)

```bash
python3 scripts/import_from_wp.py              # Alle Anleitungen
python3 scripts/import_from_wp.py --dry-run    # Nur Test
python3 scripts/import_from_wp.py --manual ezero  # Einzelne Anleitung
```

### build_manuals.py
Generiert Hugo-Markdown-Dateien aus PocketBase.
- Holt alle Manuals + Blöcke
- Generiert .de.md und .en.md
- Führt hugo --minify aus

```bash
python3 scripts/build_manuals.py           # Vollständiger Build
python3 scripts/build_manuals.py --no-build  # Nur Markdown generieren
```

## PocketBase Schema

### kb_manuals
| Feld       | Typ    | Beschreibung              |
|------------|--------|---------------------------|
| slug       | text   | z.B. gremac-ezero       |
| title_de   | text   | Deutscher Titel           |
| title_en   | text   | Englischer Titel          |
| machine    | select | Maschinen-Typ             |
| version    | text   | Versions-Nr               |
| published  | bool   | Öffentlich sichtbar       |

### kb_blocks
| Feld         | Typ    | Beschreibung                    |
|--------------|--------|---------------------------------|
| title_de     | text   | Abschnittstitel DE              |
| title_en     | text   | Abschnittstitel EN              |
| content_de   | editor | Inhalt DE (HTML)                |
| content_en   | editor | Inhalt EN (HTML)                |
| category     | select | safety/maintenance/intro/...    |
| shared       | bool   | In mehreren Anleitungen genutzt |
| images       | json   | Array von Bildpfaden            |
| image_alt_de | text   | Alt-Texte DE (| separiert)      |
| image_alt_en | text   | Alt-Texte EN (| separiert)      |

### kb_structure
| Feld          | Typ      | Beschreibung              |
|---------------|----------|---------------------------|
| manual        | relation | → kb_manuals              |
| block         | relation | → kb_blocks               |
| sort_order    | number   | Reihenfolge im Manual     |
| heading_level | number   | 2=h2, 3=h3                |

## Shared-Blöcke (Beispiele)
Folgende Abschnitte kommen in mehreren Anleitungen vor und werden
nur einmal in PocketBase gespeichert:
- Service + Produktion (alle 4 Anleitungen)
- Vertrieb (alle 4 Anleitungen)
- Sicherheitshinweise / Grundsatz (alle 4 Anleitungen)
- Organisatorische Maßnahmen (alle 4 Anleitungen)
- Inhaltsverzeichnis (eZero, e1, e2+)

## Bilder
Liegen in: 
Hugo-Pfad: 
92 Bilder verfügbar.

## Server
- GREMAC-VPS: 87.106.11.113 (Public) / 100.126.216.123 (Tailscale)
- PocketBase: http://localhost:8090
- Hugo-Root: /var/www/gremac.net
- Preview: https://preview.gremac.net/betriebsanleitungen/
