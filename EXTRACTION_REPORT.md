# Extraktionsbericht – GREMAC Knowledge Base
**Datum:** 27.03.2026  
**Quelle:** https://service.h2protech.de/knowledge-base/

## Gefundene Artikel (12 gesamt)

| ID | Titel | Typ |
|----|-------|-----|
| 4024 | Gremac e1 Betriebsanleitung | Anleitung DE |
| 4023 | Gremac e2+ Betriebsanleitung | Anleitung DE |
| 4022 | Gremac eZero Betriebsanleitung | Anleitung DE |
| 8638 | Gremac e3 Betriebsanleitung | Anleitung DE |
| 4674 | Gremac eZero Gebruiksaanwijzing | Anleitung NL |
| 7955 | Εγχειρίδιο οδηγιών Gremac e2+ | Anleitung GR |
| 1106 | EG-Konformitätserklärung Gremac e1 | Dokument |
| 1122 | EG Konformitätserklärung Gremac e2+ | Dokument |
| 1124 | EG-Konformitätserklärung Gremac eZero | Dokument |
| 10155 | EG Konformitätserklärung Gremac e3 | Dokument |
| 4581 | Getriebemotoren – Ölfüllstände | Shared Block |
| 4638 | Mosa GE 12054 HZDT – Spannungsschwankungen | Shared Block |

## Analyse: Wiederverwendbare Blöcke

Analyse über e1, e2+ und eZero Betriebsanleitungen:

| Kategorie | Anzahl gemeinsamer Blöcke |
|-----------|--------------------------|
| **Sicherheitshinweise** | 71 |
| **Wartung & Inspektion** | 88 |
| **Vorwort & Allgemeines** | 30 |
| **Kontakt/Adressen** | 2 |
| **Sonstige** | 212 |
| **GESAMT (alle 3 Anleitungen)** | **403** |

## Erkenntnisse für das Modulsystem

1. **~403 Blöcke** können als "Shared Blocks" einmal gepflegt und in allen Anleitungen verwendet werden.
2. **Sicherheitshinweise (71)** sind fast identisch in allen Maschinen → perfekter Kandidat für einen zentralen Block.
3. **Wartungsanweisungen (88)** überschneiden sich stark → maschinenspezifische Abweichungen müssen markiert werden.
4. **Mehrsprachigkeit:** NL (eZero) und GR (e2+) Versionen vorhanden → Sprachfeld in PocketBase notwendig.
5. **Separate Dokumente:** Ölfüllstände und Mosa-Spannungshinweise sind eigenständige Blöcke die in mehreren Anleitungen referenziert werden.

## Nächste Schritte
- [ ] PocketBase Schema anlegen (kb_blocks, kb_manuals, kb_structure)
- [ ] Blöcke nach Kategorien in PocketBase importieren
- [ ] Bilder aus WordPress-Mediathek sichern
- [ ] Hugo-Komponenten für Web-Anzeige entwickeln
- [ ] PDF-Export Engine implementieren
