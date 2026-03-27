# Usermanual Add-on for gremac.net

Modulares Redaktionssystem zur Verwaltung und Generierung von Betriebsanleitungen.

## Features
- **Block-basiertes Content Management:** Wiederverwendbare Textbausteine.
- **Multi-Language:** Unterstützung für DE, EN, FR, etc.
- **PDF-Generator:** A4 Export mit Inhaltsverzeichnis.
- **API-First:** Datenhaltung in PocketBase, Anzeige in Hugo.

## Struktur
- `/content`: Markdown-Rohdaten der extrahierten Blöcke.
- `/scripts`: Crawler und PDF-Generator-Logik.
- `/schema`: PocketBase Tabellen-Definitionen.
