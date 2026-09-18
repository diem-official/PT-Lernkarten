# Design: Migration von Cloudflare Access zu Authentik

**Datum:** 2026-09-18
**Status:** Freigegeben

---

## Ziel

Das bestehende Setup ([Design: Cloudflare Access](2026-08-25-private-hosting-cloudflare-access-design.md)) schützt die Anwendung per Cloudflare Access mit passwortlosem E-Mail-Login (One-Time-PIN). Cloudflare Access ist im kostenlosen Zero-Trust-Plan jedoch auf 50 Nutzer begrenzt. Da das System inzwischen für ~100 Nutzer (Schulklassen) gebraucht wird und ein kostenpflichtiger Cloudflare-Plan zu teuer ist, wird Cloudflare Access durch **Authentik** ersetzt — ein selbst gehostetes Identity-Provider-System ohne Nutzerlimit, das denselben passwortlosen E-Mail-Login-Flow abbildet (Magic Link statt One-Time-PIN, funktional äquivalent).

**Scope:** Ersetzt ausschließlich die Zugriffsschutz-Schicht. Keine Änderung an der Anwendungslogik (`web/`-Ordner bleibt unverändert, rein statisch). Cloudflare Tunnel (Exposure + TLS-Terminierung, kostenlos, kein Nutzerlimit) bleibt bestehen — nur Cloudflare Access wird entfernt.

**Out of scope:** Migration bestehender Cloudflare-Access-Nutzerlisten (Neuregistrierung per Self-Service ersetzt die alte Allowlist-Pflege, siehe Abschnitt 3). Eigene TLS-Verwaltung (certbot o. ä.) — bleibt weiterhin Aufgabe von Cloudflare Tunnel.

---

## 1. Gesamtarchitektur

```
        ┌─────────────────────┐
        │  Source + Pipeline    │   GitHub-Repo
        └─────────────────────┘
           │              │
     push  │              │  push, Action (rsync/SSH)
           ▼              ▼
┌──────────────────┐  ┌───────────────────────────────┐
│  GitHub Pages       │  │  VPS: nginx + cloudflared         │
│  (unverändert)        │  │  nginx serviert web/, prüft          │
└──────────────────┘  │  Session per auth_request           │
                       └───────────────────────────────┘
                                    │            │
                              Tunnel│            │Tunnel
                       lernen.<domain>  auth.<domain>
                                    │            ▼
                                    │  ┌──────────────────────┐
                                    │  │  Authentik (Docker)      │
                                    │  │  server + worker           │
                                    │  │  + PostgreSQL + Redis          │
                                    │  │  Magic-Link-Login             │
                                    │  │  Self-Service-Enrollment          │
                                    │  │  (Domain-Policy @schul-domain)      │
                                    │  └──────────────────────┘
                                    ▼                    ▲
                          nginx lässt Zugriff          Schüler
                          nur mit gültiger Session       (E-Mail @schul-domain)
                          durch
```

Cloudflare Access (Application + Policy) entfällt vollständig. Cloudflare Tunnel bekommt einen zweiten Public Hostname für Authentik selbst.

---

## 2. Server-Setup (neu)

Zusätzlich zum bestehenden nginx-Static-Hosting:

- **Docker + Docker Compose** auf dem VPS installieren (bisher nicht benötigt).
- Neuer Compose-Stack `deploy/authentik/docker-compose.yml` mit den Services:
  - `authentik-server` (Web-UI, Login-/Enrollment-Flows, Proxy-Outpost)
  - `authentik-worker` (Hintergrundjobs, u. a. E-Mail-Versand)
  - `postgresql` (Authentik-Datenbank)
  - `redis` (Cache/Sessions)
- `.env`-Datei mit Platzhaltern für `PG_PASS`, `AUTHENTIK_SECRET_KEY`, SMTP-Zugangsdaten (Host/Port/User/Passwort, vom Betreiber selbst gestellt) und erlaubter Schul-Domain — **nur auf dem VPS**, nicht im Repo oder als GitHub Actions Secret, da der `deploy-vps`-Workflow ausschließlich `web/` synct und den Authentik-Stack nicht anfasst.
- VPS-Ressourcencheck bereits durchgeführt: 4 Kerne / 8 GB RAM / 240 GB — ausreichend für den zusätzlichen Stack, keine weiteren Anpassungen nötig.

Ressourcen-Richtwert: Authentik (Server+Worker+Postgres+Redis) benötigt in der Praxis ca. 2 GB RAM — bei 8 GB VPS-RAM unkritisch neben dem bestehenden nginx-Static-Hosting.

---

## 3. Zugriffsschutz & Login-Flow (Authentik)

**Einmalige Einrichtung:**

1. Docker-Compose-Stack auf dem VPS starten, Admin-Account anlegen.
2. SMTP-Zugangsdaten (vom Betreiber bereitgestellt) in Authentik als E-Mail-Notifier hinterlegen.
3. Zweiten Cloudflare-Tunnel-Hostname `auth.<domain>` → `localhost:9000` (Authentik-Server-Port) anlegen.
4. In Authentik einen **Enrollment-Flow** (Self-Service-Registrierung) mit Passwordless-E-Mail-Stage konfigurieren, gebunden an eine **Expression-Policy**, die die eingegebene E-Mail-Adresse gegen `*@<schul-domain>` prüft.
5. **Proxy-Outpost** für `lernen.<domain>` anlegen, der die Session gegen nginx per `auth_request` bereitstellt.
6. In nginx ([deploy/nginx/pt-lernkarten.conf](../../../deploy/nginx/pt-lernkarten.conf)) einen `auth_request`-Block sowie die `/outpost.goauthentik.io/`-Location ergänzen, die bei fehlender Session zu `auth.<domain>` umleitet.

**Ablauf für einen Schüler:**

1. Aufruf von `lernen.<domain>`.
2. nginx erkennt fehlende Session (`auth_request` schlägt fehl) → Redirect zu `auth.<domain>`.
3. Authentik zeigt E-Mail-Eingabe:
   - **Neue Adresse** (Domain-Policy prüft `@<schul-domain>`): Enrollment-Flow verschickt Bestätigungslink → Klick erstellt Account und loggt gleichzeitig ein. Adresse außerhalb der erlaubten Domain wird mit klarer Fehlermeldung abgelehnt, kein Mail-Versand.
   - **Bekannte Adresse**: Passwordless-E-Mail-Stage verschickt Magic-Link → Klick loggt ein. Aus Sicherheitsgründen ist die Rückmeldung ("Link verschickt") in beiden Fällen (Adresse existiert / existiert nicht) identisch, um kein Adress-Enumeration zu ermöglichen.
4. Nach erfolgreichem Login Redirect zurück zu `lernen.<domain>`, nginx lässt durch.
5. Session-Dauer: 24 h (wie bisher bei Cloudflare Access), danach erneuter E-Mail-Login.

**Kein Passwort:** Authentik speichert für diese Nutzer keine Passwort-Hashes — Authentifizierung läuft ausschließlich über die Passwordless-E-Mail-Stage (Magic Link).

**Pflege der Zugangsberechtigung:** Kein manuelles Eintragen mehr nötig — jede Adresse mit der korrekten Schul-Domain-Endung kann sich selbst registrieren. Der Betreiber pflegt nur noch die erlaubte Domain in der Expression-Policy (Änderung nur nötig, falls sich die Schul-Domain ändert).

---

## 4. Deployment-Pipeline

[.github/workflows/deploy.yml](../../../.github/workflows/deploy.yml) bleibt unverändert — der `deploy-vps`-Job synct weiterhin nur `web/` per rsync. Der Authentik-Compose-Stack ist kein Teil dieser Pipeline; Aufbau und Updates erfolgen manuell auf dem VPS (analog zur bisherigen manuellen nginx-Einrichtung).

---

## 5. Migration & Cutover

Parallelbetrieb statt Big-Bang, um das bestehende System für aktuelle Nutzer nicht zu unterbrechen:

1. Authentik-Stack aufsetzen und isoliert testen (`auth.<domain>` erreichbar, Enrollment + Login mit eigener Test-Adresse), **während Cloudflare Access weiterhin aktiv bleibt**.
2. nginx-`auth_request`-Änderung einspielen — ab hier ist Authentik das eigentliche Gate; Cloudflare Access bleibt vorerst als zusätzliche äußere Schicht bestehen (doppelte Absicherung, kein Risiko für bestehende Nutzer).
3. Test mit einigen echten Nutzern (Enrollment + wiederkehrender Login).
4. Nach erfolgreicher Validierung: Cloudflare-Access-Application und -Policy im Zero-Trust-Dashboard löschen — Cloudflare Tunnel bleibt unverändert bestehen.
5. [deploy/README.md](../../../deploy/README.md) aktualisieren: bisherigen Abschnitt 5 ("Cloudflare Access einrichten") durch "Authentik einrichten" ersetzen (Docker Compose, SMTP, Enrollment-Flow, Domain-Policy, zweiter Tunnel-Hostname); Abschnitt 6 ("Neue Adressen hinzufügen") entfällt, da Self-Service.

**Rollback:** Solange Cloudflare Access in Schritt 4 noch nicht gelöscht ist, kann die nginx-`auth_request`-Änderung bei Problemen einfach zurückgesetzt werden — Cloudflare Access greift dann wieder wie gehabt, ohne Datenverlust auf Authentik-Seite.

---

## 6. Testing & Validierung

- Enrollment mit gültiger Schul-Domain-Adresse → Magic-Link kommt an, Klick erstellt Account und loggt ein.
- Enrollment mit ungültiger Domain → wird abgelehnt, generische Fehlermeldung, kein Mail-Versand.
- Bereits registrierter Nutzer → Magic-Link-Login (kein erneutes Enrollment nötig).
- Session-Ablauf nach 24 h → erneuter Login wird verlangt.
- nginx liefert bei fehlender/abgelaufener Session korrekt zu Authentik um; kein direkter Zugriff auf `lernen.<domain>` ohne gültige Session möglich.
- SMTP-Ausfall-Szenario: Authentik zeigt weiterhin generische "Link verschickt"-Meldung (kein Nutzer-seitiger Fehler sichtbar), tatsächlicher Fehler landet im Worker-Log.

**Bewusst nicht behandelt (YAGNI):**

- Kein Failover, falls Authentik-Stack oder VPS ausfallen — für dieses Projekt in diesem Umfang nicht erforderlich (wie schon im Cloudflare-Access-Design).
- Kein WebAuthn/Passkey-Login — Magic-Link-E-Mail deckt den gewünschten passwortlosen Flow bereits vollständig ab.
- Keine automatisierte Provisionierung des Authentik-Stacks über die GitHub-Actions-Pipeline — manuelle VPS-Einrichtung ist für diesen Umfang ausreichend (analog zur bisherigen manuellen nginx/Cloudflare-Einrichtung).
