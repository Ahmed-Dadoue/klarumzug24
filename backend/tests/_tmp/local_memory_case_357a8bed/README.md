# Local Knowledge Memory

Dieses Verzeichnis speichert lokal kontrollierte Wissensartefakte aus Chatgespraechen.

- `raw_knowledge/`: rohe Konversationsbeobachtungen
- `review_queue/`: vom Menschen zu pruefende Wissenskandidaten
- `approved_knowledge/`: freigegebene Wissenseintraege
- `faq_candidates/`: offene FAQ-Kandidaten
- `service_knowledge/`: freigegebenes servicebezogenes Wissen
- `failure_cases/`: bekannte Fehlfaelle
- `repeated_questions/`: wiederholte Fragenmuster
- `useful_approved_answers/`: wiederverwendbare, freigegebene Antworten
- `logs/`: strukturierte Audit-Logs fuer Monitoring und Reports

Die Datei `control.json` erlaubt es, lokale Wissensaufnahme pro Gespraechstyp zu pausieren.
