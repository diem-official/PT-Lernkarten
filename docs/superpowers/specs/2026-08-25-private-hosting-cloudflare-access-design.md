# Design: Privates Hosting mit passwortlosem Zugriffsschutz (Cloudflare Access)

**Datum:** 2026-08-25
**Status:** Freigegeben

---

## Ziel

Die Anwendung wird bisher öffentlich über GitHub Pages ausgeliefert, das zugehörige GitHub-Repo ist öffentlich. Im `Input/`- und `Bilder/`-Ordner sowie in der Versionsgeschichte liegt Bildmaterial, das nicht lizenziert ist (nicht-kommerzielle Nutzung zu Lernzwecken). Ziel dieses Designs ist, die Anwendung künftig nur noch für einen festen Kreis erlaubter Nutzer (Klassenkameraden) zugänglich zu machen, ohne dass der Betreiber Passwörter verwalten muss — Login erfolgt passwortlos per E-Mail (One-Time-PIN, funktional äquivalent zu einem Magic Link).

**Scope:** Infrastruktur- und Zugriffsschutz-Design. Kein Eingriff in die bestehende Anwendungslogik (Pipeline, Frontend-JS/CSS bleiben unverändert) — die Web-App bleibt eine rein statische Seite ohne eigenen Anwendungs-Server.

**Out of scope / bewusst verschoben:** Das GitHub-Repo auf "Privat" stellen und die bestehende GitHub-Pages-Veröffentlichung abschalten sind **nicht** Teil dieser Umsetzung (siehe Abschnitt 5, Phasenmodell). Diese beiden Schritte führt der Betreiber selbst manuell aus, sobald die neue Infrastruktur validiert ist.

---

## 1. Gesamtarchitektur

Zwei unabhängige Schutzmechanismen für zwei unterschiedliche Probleme:

1. **GitHub-Repo-Sichtbarkeit** (später, manuell) schützt Quellcode und Rohbilder in der Versionsgeschichte vor der Öffentlichkeit.
2. **Cloudflare Access vor der ausgelieferten Seite** (Teil dieser Umsetzung) schützt den laufenden Betrieb: Nur wer auf der E-Mail-Allowlist steht, erreicht die Seite überhaupt.

```
GitHub (öffentlich, Phase 1)      Cloudflare Access            Eigener VPS
┌─────────────────┐   push      ┌──────────────────┐  Tunnel  ┌────────────────┐
│ Source + Pipeline │ ─────────▶│ E-Mail-Allowlist   │◀────────▶│ nginx           │
│                    │  Action    │ One-Time-PIN-Login │          │ + cloudflared   │
└─────────────────┘  (rsync/SSH) │ Session-Cookie      │          │ serviert web/   │
        │                        └──────────────────┘          └────────────────┘
        │ (unverändert,                     ▲
        │  bestehender Job)            Klassenkamerad
        ▼                          (E-Mail auf Liste)
   GitHub Pages
  (läuft parallel weiter,
   bis manuell abgeschaltet)
```

Die Web-App selbst (HTML/CSS/JS, `web/`-Ordner) bleibt unverändert eine rein clientseitige, statische Anwendung. Es wird kein eigener Auth-Code geschrieben — die Zugriffskontrolle liegt vollständig bei Cloudflare Access, vorgelagert vor dem statischen Content.

---

## 2. Zugriffsschutz & Login-Flow (Cloudflare Access)

**Einmalige Einrichtung:**

1. Domain bei Cloudflare hinzufügen (kostenloser Account); Nameserver auf Cloudflare umstellen.
2. `cloudflared` (Tunnel-Client) auf dem VPS installieren und als systemd-Service einrichten. Der Tunnel verbindet `lernen.<domain>` mit `localhost:80` (nginx) auf dem Server. Es muss kein Port nach außen geöffnet werden; TLS wird von Cloudflare terminiert, eine eigene Zertifikatsverwaltung (z. B. certbot) entfällt.
3. In Cloudflare Zero Trust eine **Access Application** für `lernen.<domain>` anlegen mit einer Policy: *Allow*, wenn die eingegebene E-Mail-Adresse in einer festen Liste einzelner, vom Betreiber gepflegter Adressen enthalten ist.
4. Login-Methode: **One-Time PIN per E-Mail** (Cloudflares eingebaute passwortlose Methode). Kein SMTP-Setup, kein Token-Handling, kein Session-Code im eigenen Zuständigkeitsbereich.

**Ablauf für einen Klassenkameraden:**

1. Aufruf von `lernen.<domain>`.
2. Cloudflare zeigt eine Login-Seite mit E-Mail-Eingabe.
3. Steht die Adresse auf der Allowlist, verschickt Cloudflare einen Code per Mail; steht sie nicht auf der Liste, wird der Zugriff abgelehnt und keine Mail verschickt.
4. Nach Code-Eingabe setzt Cloudflare ein Session-Cookie (Standard: 24 h, konfigurierbar); innerhalb der Session ist kein erneuter Login nötig.

**Pflege der Allowlist:** Der Betreiber trägt neue Adressen im Cloudflare Zero Trust Dashboard in die Policy ein. Kein Server-Zugriff und keine Code-Änderung nötig.

---

## 3. Server-Setup

Auf dem (aktuell leeren) Linux-VPS mit Root/SSH-Zugriff:

- **nginx**, konfiguriert als einfacher statischer Dateiserver für den Inhalt von `web/`. Kein Docker, keine Anwendungslogik — die Seite bleibt rein statisch wie bisher.
- **cloudflared** als systemd-Service (siehe Abschnitt 2).
- Deploy-Zielverzeichnis, z. B. `/var/www/pt-lernkarten/`, auf das die nginx-Konfiguration zeigt.
- Ein dedizierter **Deploy-User** mit SSH-Key-Login (kein Passwort-Login), beschränkt auf Schreibrechte für dieses eine Verzeichnis — getrennt vom root-Login des Betreibers.

---

## 4. Deployment-Pipeline

Der bestehende Workflow [.github/workflows/deploy.yml](../../../.github/workflows/deploy.yml) bleibt für den GitHub-Pages-Job **unverändert** bestehen (Phase 1, siehe Abschnitt 5) und wird um einen zusätzlichen Job/Step erweitert:

- Bei jedem Push auf den Branch synct ein zusätzlicher Schritt den `web/`-Ordner per `rsync` über SSH auf `/var/www/pt-lernkarten/` auf dem VPS.
- Der private SSH-Key des Deploy-Users wird als verschlüsseltes **GitHub Actions Secret** hinterlegt, nie im Klartext im Repo.
- Der gewohnte Ablauf (Push → automatisch live) bleibt erhalten; es kommt lediglich ein zweites Deploy-Ziel hinzu, parallel zum bestehenden GitHub-Pages-Ziel.

---

## 5. Phasenmodell

GitHub Pages ist für private Repos auf persönlichen GitHub-Free-Accounts nicht verfügbar (nur ab GitHub Pro). Da die bestehende Pages-Seite während der Übergangszeit weiterlaufen soll, ergibt sich ein zweiphasiger Ablauf:

- **Phase 1 (Teil dieser Umsetzung):** Repo bleibt öffentlich. Bestehender GitHub-Pages-Job läuft unverändert weiter. Zusätzlich wird die neue Infrastruktur (Cloudflare Access, VPS-Hosting, erweiterte Deploy-Pipeline) komplett aufgebaut und validiert — sie läuft parallel zur bisherigen öffentlichen Seite.
- **Phase 2 (später, manuell, außerhalb dieser Umsetzung):** Sobald der Betreiber mit der neuen Infrastruktur zufrieden ist, schaltet er selbst GitHub Pages ab (Repo-Settings) und stellt anschließend das Repo auf "Privat" (Settings → Danger Zone → Change visibility). Beide Schritte sind bewusst manuelle, vom Betreiber zu einem selbstgewählten Zeitpunkt ausgelöste Aktionen und nicht Teil des Implementierungsplans.

---

## 6. Testing & Validierung

- Login mit eigener (gelisteter) E-Mail-Adresse testen → Zugriff funktioniert, Session bleibt über Browser-Neustart bestehen.
- Login-Versuch mit einer nicht gelisteten Test-Adresse → wird abgelehnt, keine Mail wird verschickt.
- End-to-End-Deploy-Test: kleine Änderung pushen → beide Jobs (Pages + VPS-Deploy) laufen grün → Änderung ist sowohl auf der alten Pages-URL als auch auf der neuen eigenen Domain sichtbar.
- Manuelle Prüfung nach Phase 2 (zu einem späteren Zeitpunkt, außerhalb dieser Umsetzung): alte GitHub-Pages-URL ist nach Abschalten nicht mehr erreichbar; Repo ist über die alte öffentliche URL nicht mehr einsehbar.

**Bewusst nicht behandelt (YAGNI):**

- Kein Failover, falls Cloudflare-Tunnel oder VPS ausfallen — für ein privates Lernprojekt in diesem Umfang nicht erforderlich.
- Kein Self-Service für neue Nutzer; jede neue Adresse wird vom Betreiber manuell in die Cloudflare-Policy eingetragen (bewusste Entscheidung, siehe Abschnitt 2).
