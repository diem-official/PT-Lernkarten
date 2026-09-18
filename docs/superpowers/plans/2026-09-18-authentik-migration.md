# Authentik-Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cloudflare Access (Free-Tier-Limit: 50 Nutzer) durch selbst gehostetes Authentik ersetzen, damit ~100 Schüler sich weiterhin passwortlos per E-Mail einloggen können — ohne Kosten und ohne Nutzerlimit. Cloudflare Tunnel bleibt für Exposure/TLS bestehen.

**Architecture:** Ein neuer Docker-Compose-Stack (`server`, `worker`, `postgresql` — laut aktueller offizieller Authentik-Doku ohne separaten Redis-Service) läuft auf dem VPS neben nginx, Ports nur auf `127.0.0.1` gebunden. nginx bekommt einen `auth_request`-Block, der jede Anfrage an `lernen.<domain>` gegen den lokalen Authentik-Outpost prüft; ohne gültige Session leitet nginx relativ auf `/outpost.goauthentik.io/start` um — bleibt auf `lernen.<domain>`, da Authentiks „Forward Auth (Single Application)"-Modus die geschützte App-URL selbst als External Host verlangt. Ein zweiter Cloudflare-Tunnel-Hostname `auth.<domain>` (direkt auf `localhost:9000`) dient ausschließlich dem direkten Admin-Zugriff auf Authentik, nicht dem Schüler-Login. In Authentik werden zwei Flows aus Standard-Stages zusammengesetzt (Identification → Email-Stage), da Authentik Magic-Link-Login nicht als fertigen Baustein anbietet: ein Enrollment-Flow (Self-Service-Registrierung, Domain-Policy `*@schul-domain`) und ein Authentication-Flow (wiederkehrender Magic-Link-Login). Cloudflare Access wird erst nach validiertem Parallelbetrieb entfernt.

**Tech Stack:** Docker Compose, Authentik (`ghcr.io/goauthentik/server:2026.8.2`), PostgreSQL 16, nginx (`auth_request`-Modul), Cloudflare Tunnel.

**Spec:** [docs/superpowers/specs/2026-09-18-authentik-migration-design.md](../specs/2026-09-18-authentik-migration-design.md)

---

## Wichtiger Hinweis für die Ausführung

Dieser Plan hat zwei sehr unterschiedliche Sorten von Aufgaben, genau wie beim
[vorherigen Cloudflare-Access-Plan](2026-08-25-private-hosting-cloudflare-access.md):

- **Tasks 1–4** ändern nur Dateien in diesem Repo (Docker-Compose-Vorlage, nginx-Config, Dokumentation). Sicher, reversibel, git-verfolgt — geeignet für automatisierte Subagent-Ausführung.
- **Tasks 5–7** erfordern echten SSH-Zugriff auf den produktiven VPS, Zugriff auf das Cloudflare-Dashboard und Klicks im Authentik-Admin-UI (das erst nach Task 5 Step 1 existiert). Ein Subagent hat dafür weder Zugangsdaten noch Berechtigung, autonom auf Produktionsinfrastruktur zu wirken. **Diese Tasks müssen interaktiv zusammen mit dem Nutzer ausgeführt werden.** Ein automatisierter Task-Runner sollte hier stoppen und an den Nutzer übergeben, statt zu raten oder Zugangsdaten zu erfinden.

Alle nginx- und Docker-Compose-Inhalte in diesem Plan sind gegen die aktuelle
offizielle Authentik-Dokumentation (docs.goauthentik.io, Stand Authentik
2026.8.2) geprüft. Trotzdem: Admin-UI-Menüpfade können sich zwischen
Authentik-Versionen ändern — bei Abweichungen in Task 5 die dortige Live-Doku
als Quelle der Wahrheit behandeln, nicht dieses Dokument.

---

## Vorbereitung: Datei-Übersicht

| Datei | Aktion | Zweck |
|---|---|---|
| `deploy/authentik/docker-compose.yml` | Neu | Authentik-Stack (server, worker, postgresql) |
| `deploy/authentik/.env.example` | Neu | Platzhalter-Vorlage für Secrets/SMTP — echte `.env` bleibt nur auf dem VPS |
| `.gitignore` | Ändern | `deploy/authentik/.env` ausschließen |
| `deploy/nginx/pt-lernkarten.conf` | Ändern | `auth_request`-Gate gegen Authentik ergänzen |
| `deploy/README.md` | Ändern | Abschnitt 4 ergänzt (zweiter Tunnel-Hostname), Abschnitt 5 komplett durch „Authentik einrichten" ersetzt, Abschnitt 6 entfällt |

---

### Task 1: Feature-Branch anlegen

**Files:** keine (reine Git-Operation)

- [ ] **Step 1: Arbeitsstand prüfen**

Run: `git status`

Falls `nothing to commit, working tree clean` — weiter mit Step 2.

Falls uncommitted Änderungen angezeigt werden (unabhängig von diesem Plan
entstanden): **nicht automatisch committen oder verwerfen.** Den Nutzer
fragen, ob diese Änderungen vorher committet, per `git stash` beiseitegelegt,
oder bewusst mitgenommen werden sollen — erst danach mit Step 2 fortfahren.

- [ ] **Step 2: Branch erstellen und wechseln**

```bash
git checkout -b feature/authentik-migration
```

- [ ] **Step 3: Verifizieren**

Run: `git branch --show-current`
Expected: `feature/authentik-migration`

---

### Task 2: Authentik Docker-Compose-Stack erstellen

**Files:**
- Create: `deploy/authentik/docker-compose.yml`
- Create: `deploy/authentik/.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Verzeichnis anlegen und Compose-Datei schreiben**

```
deploy/authentik/docker-compose.yml
```

```yaml
# Authentik-Stack für PT Lernkarten. Basiert auf dem offiziellen
# Compose-Template (https://docs.goauthentik.io/compose.yml, Stand
# Authentik 2026.8.2) — kein separater Redis-Service nötig, dieser wurde in
# aktuellen Authentik-Versionen entfernt.
#
# Sicherheitsabweichung vom offiziellen Template: die Ports werden per
# Default an 127.0.0.1 statt 0.0.0.0 gebunden (siehe COMPOSE_PORT_HTTP/
# COMPOSE_PORT_HTTPS unten). Der VPS hat keine offene Firewall nach außen
# (siehe deploy/README.md) — nur nginx (Port 80, lokal von cloudflared
# erreicht) und Authentik selbst (Port 9000, ebenfalls nur von cloudflared
# über den zweiten Tunnel-Hostname erreicht) dürfen lokal ansprechbar sein,
# nie direkt aus dem Internet.
services:
  postgresql:
    image: docker.io/library/postgres:16-alpine
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${PG_DB:-authentik}
      POSTGRES_USER: ${PG_USER:-authentik}
      POSTGRES_PASSWORD: ${PG_PASS:?database password required}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d $${POSTGRES_DB} -U $${POSTGRES_USER}"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 20s
    volumes:
      - database:/var/lib/postgresql/data

  server:
    image: ${AUTHENTIK_IMAGE:-ghcr.io/goauthentik/server}:${AUTHENTIK_TAG:-2026.8.2}
    restart: unless-stopped
    command: server
    env_file:
      - .env
    environment:
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY:?secret key required}
      AUTHENTIK_POSTGRESQL__HOST: postgresql
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
    volumes:
      - ./data:/data
      - ./custom-templates:/templates
    ports:
      - "${COMPOSE_PORT_HTTP:-127.0.0.1:9000}:9000"
      - "${COMPOSE_PORT_HTTPS:-127.0.0.1:9443}:9443"
    shm_size: 512mb
    depends_on:
      postgresql:
        condition: service_healthy

  worker:
    image: ${AUTHENTIK_IMAGE:-ghcr.io/goauthentik/server}:${AUTHENTIK_TAG:-2026.8.2}
    restart: unless-stopped
    command: worker
    user: root
    env_file:
      - .env
    environment:
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY:?secret key required}
      AUTHENTIK_POSTGRESQL__HOST: postgresql
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/data
      - ./certs:/certs
      - ./custom-templates:/templates
    shm_size: 512mb
    depends_on:
      postgresql:
        condition: service_healthy

volumes:
  database:
    driver: local
```

- [ ] **Step 2: `.env.example` schreiben**

```
deploy/authentik/.env.example
```

```
# Vor dem Einsatz auf dem VPS nach deploy/authentik/.env kopieren und alle
# Platzhalter ersetzen. Diese Datei (.env, ohne .example) NIEMALS committen —
# sie liegt nur auf dem VPS (siehe .gitignore).

# Generieren mit:
#   openssl rand -base64 36 | tr -d '\n'   (PG_PASS)
#   openssl rand -base64 60 | tr -d '\n'   (AUTHENTIK_SECRET_KEY)
PG_PASS=changeme-generate-with-openssl
AUTHENTIK_SECRET_KEY=changeme-generate-with-openssl

# SMTP-Zugangsdaten des eigenen Mail-Providers (für Magic-Link-Versand)
AUTHENTIK_EMAIL__HOST=smtp.example.com
AUTHENTIK_EMAIL__PORT=587
AUTHENTIK_EMAIL__USERNAME=changeme
AUTHENTIK_EMAIL__PASSWORD=changeme
AUTHENTIK_EMAIL__USE_TLS=true
AUTHENTIK_EMAIL__USE_SSL=false
AUTHENTIK_EMAIL__FROM=authentik@<domain>

AUTHENTIK_ERROR_REPORTING__ENABLED=false
```

- [ ] **Step 3: `.gitignore` ergänzen**

Am Ende von [.gitignore](../../../.gitignore) ergänzen:

```
# Authentik-Secrets (nur auf dem VPS, nie im Repo)
deploy/authentik/.env
```

- [ ] **Step 4: Compose-Syntax prüfen**

Falls Docker lokal installiert ist:
Run: `cd deploy/authentik && cp .env.example .env.tmp-check && docker compose --env-file .env.tmp-check config >/dev/null && echo OK; rm .env.tmp-check`
Expected: `OK`

Falls Docker lokal nicht verfügbar ist: Diesen Schritt überspringen, die
verbindliche Prüfung erfolgt in Task 5 auf dem VPS selbst (`docker compose
up -d` schlägt bei Syntaxfehlern sofort sichtbar fehl).

- [ ] **Step 5: Committen**

```bash
git add deploy/authentik/docker-compose.yml deploy/authentik/.env.example .gitignore
git commit -m "Add Authentik Docker Compose stack for VPS"
```

---

### Task 3: nginx-Config um Authentik-Gate erweitern

**Files:**
- Modify: `deploy/nginx/pt-lernkarten.conf`

- [ ] **Step 1: `auth_request`-Block ergänzen**

Bestehenden Inhalt von [deploy/nginx/pt-lernkarten.conf](../../../deploy/nginx/pt-lernkarten.conf):

```nginx
# Vorlage für den VPS. Vor dem Einsatz auf dem Server nach
# /etc/nginx/sites-available/pt-lernkarten.conf kopieren und
# "lernen.<domain>" durch die echte (Sub-)Domain ersetzen.
server {
    listen 80;
    listen [::]:80;
    server_name lernen.<domain>;

    root /var/www/pt-lernkarten;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~* \.(?:css|js|jpg|jpeg|png|gif|svg|woff2?)$ {
        expires 7d;
        add_header Cache-Control "public";
    }

    access_log /var/log/nginx/pt-lernkarten.access.log;
    error_log  /var/log/nginx/pt-lernkarten.error.log;
}
```

Komplett ersetzen durch:

```nginx
# Vorlage für den VPS. Vor dem Einsatz auf dem Server nach
# /etc/nginx/sites-available/pt-lernkarten.conf kopieren und
# "lernen.<domain>" durch die echte (Sub-)Domain ersetzen.
# Schützt die gesamte Seite per Authentik-Session-Check (auth_request) —
# siehe Design-Spec Abschnitt 3
# (docs/superpowers/specs/2026-09-18-authentik-migration-design.md).
#
# Login-/Enrollment-Seiten bleiben auf dieser Domain (lernen.<domain>) —
# Authentiks "Forward Auth (Single Application)"-Modus verlangt laut
# offizieller Doku, dass External Host = diese App-URL selbst ist, nicht
# eine separate Authentik-Domain. Redirects unten sind deshalb relativ,
# nicht auf auth.<domain>. Konfiguration folgt dem offiziellen
# nginx-Beispiel (docs.goauthentik.io/add-secure-apps/providers/proxy/server_nginx/,
# "Standalone nginx / Single Application").
server {
    listen 80;
    listen [::]:80;
    server_name lernen.<domain>;

    root /var/www/pt-lernkarten;
    index index.html;

    # Größere Puffer für die Cookie-/Header-Größen, die Authentik zurückgibt.
    proxy_buffers 8 16k;
    proxy_buffer_size 32k;

    location / {
        auth_request /outpost.goauthentik.io/auth/nginx;
        error_page 401 = @goauthentik_proxy_signin;
        auth_request_set $auth_cookie $upstream_http_set_cookie;
        add_header Set-Cookie $auth_cookie;

        try_files $uri $uri/ =404;
    }

    location ~* \.(?:css|js|jpg|jpeg|png|gif|svg|woff2?)$ {
        auth_request /outpost.goauthentik.io/auth/nginx;
        error_page 401 = @goauthentik_proxy_signin;
        auth_request_set $auth_cookie $upstream_http_set_cookie;
        add_header Set-Cookie $auth_cookie;

        expires 7d;
        add_header Cache-Control "public";
    }

    # Proxied zum lokal per Docker Compose laufenden Authentik-Server
    # (deploy/authentik/docker-compose.yml, Port nur an 127.0.0.1
    # gebunden). Dient sowohl als Ziel von auth_request oben (Session-Check)
    # als auch als öffentlich erreichbarer Pfad für die Login-/
    # Enrollment-Seiten selbst — deshalb NICHT "internal": der Browser lädt
    # diese Seiten direkt unter lernen.<domain>/outpost.goauthentik.io/...
    location /outpost.goauthentik.io {
        proxy_pass              http://127.0.0.1:9000/outpost.goauthentik.io;
        proxy_set_header        Host $host;
        proxy_set_header        X-Original-URL $scheme://$host$request_uri;
        add_header              Set-Cookie $auth_cookie;
        auth_request_set        $auth_cookie $upstream_http_set_cookie;
        proxy_pass_request_body off;
        proxy_set_header        Content-Length "";
    }

    location @goauthentik_proxy_signin {
        internal;
        add_header Set-Cookie $auth_cookie;
        return 302 /outpost.goauthentik.io/start?rd=$scheme://$host$request_uri;
    }

    access_log /var/log/nginx/pt-lernkarten.access.log;
    error_log  /var/log/nginx/pt-lernkarten.error.log;
}
```

- [ ] **Step 2: Syntax prüfen**

Falls nginx lokal installiert ist:
Run: `nginx -t -c "$(pwd)/deploy/nginx/pt-lernkarten.conf"`
Expected: keine Syntaxfehler (Warnungen zu fehlendem `events`/`http`-Block
sind bei einer reinen Server-Block-Vorlage normal).

Falls nginx lokal nicht installiert ist: überspringen — verbindliche Prüfung
erfolgt in Task 5 auf dem VPS (`sudo nginx -t`).

- [ ] **Step 3: Diff prüfen**

Run: `git diff deploy/nginx/pt-lernkarten.conf`
Expected: `server_name`, `root`, `index`, Kommentare und die beiden
bestehenden `location`-Blöcke sind inhaltlich unverändert (bis auf die neu
ergänzten `auth_request`-Zeilen); zwei neue Blöcke (`location
/outpost.goauthentik.io`, `location @goauthentik_proxy_signin`) kommen
hinzu; `<domain>` kommt in dieser Datei nur noch einmal vor (`server_name`)
— kein `auth.<domain>` mehr in der nginx-Config.

- [ ] **Step 4: Committen**

```bash
git add deploy/nginx/pt-lernkarten.conf
git commit -m "Add Authentik auth_request gate to nginx config"
```

---

### Task 4: Deploy-Runbook aktualisieren

**Files:**
- Modify: `deploy/README.md`

- [ ] **Step 1: Abschnitt 4 („Cloudflare Tunnel einrichten") um zweiten Hostname ergänzen**

Nach dem bestehenden Punkt 3 in [deploy/README.md](../../../deploy/README.md)
(„Im Tunnel unter **Public Hostname**: Hostname `lernen.<domain>` →
Service-Typ `HTTP`, URL `localhost:80`.") folgenden Punkt einfügen (wird
neuer Punkt 4, bisheriger Punkt 4 „Prüfen: ..." rückt zu Punkt 5):

```markdown
4. Im selben Tunnel einen zweiten **Public Hostname** anlegen: Hostname
   `auth.<domain>` → Service-Typ `HTTP`, URL `localhost:9000` (Authentik,
   siehe Abschnitt 5). Beide Hostnames laufen über denselben Tunnel, kein
   zweiter Tunnel nötig.
```

- [ ] **Step 2: Abschnitt 5 komplett ersetzen**

Bisherigen Abschnitt „## 5. Cloudflare Access einrichten" (5 Punkte, von „1.
Zero Trust Dashboard..." bis „...für dieses Projekt ausreichend.") komplett
löschen und durch folgenden Abschnitt ersetzen:

```markdown
## 5. Authentik einrichten

Siehe auch: [Design-Spec](../docs/superpowers/specs/2026-09-18-authentik-migration-design.md)

### 5.1 Docker + Compose-Stack starten

```bash
# Docker installieren, falls noch nicht vorhanden:
curl -fsSL https://get.docker.com | sudo sh

sudo mkdir -p /opt/authentik
sudo chown $(whoami) /opt/authentik
```

`deploy/authentik/docker-compose.yml` und `deploy/authentik/.env.example`
vom eigenen Rechner mit den **eigenen** Admin-SSH-Zugangsdaten übertragen
(nicht mit dem Deploy-Key aus Abschnitt 2, der hat keinen Zugriff auf
dieses Verzeichnis):

```bash
scp deploy/authentik/docker-compose.yml deploy/authentik/.env.example \
    <dein-admin-user>@<VPS_HOST>:/opt/authentik/
```

Auf dem VPS:

```bash
cd /opt/authentik
mv .env.example .env
echo "PG_PASS=$(openssl rand -base64 36 | tr -d '\n')" >> .env
echo "AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n')" >> .env
$EDITOR .env   # restliche Platzhalter ersetzen: SMTP-Zugangsdaten, <domain>

sudo docker compose pull
sudo docker compose up -d
sudo docker compose ps   # alle drei Services "running"/"healthy" erwartet
```

### 5.2 Admin-Account anlegen

`http://localhost:9000` ist vom VPS selbst aus erreichbar (Port ist an
`127.0.0.1` gebunden, siehe `docker-compose.yml`). Per SSH-Tunnel vom
eigenen Rechner aus öffnen:

```bash
ssh -L 9000:localhost:9000 <dein-admin-user>@<VPS_HOST>
```

Dann lokal `http://localhost:9000/if/flow/initial-setup/` im Browser
aufrufen und Passwort für den `akadmin`-Nutzer setzen.

### 5.3 SMTP-Notifier prüfen

Die SMTP-Zugangsdaten aus der `.env` (Abschnitt 5.1) werden von Authentik
automatisch für System-E-Mails verwendet. Im Admin-Interface unter
**System → Notifications** eine Test-Benachrichtigung auslösen, um den
SMTP-Versand zu verifizieren, bevor die Flows in 5.4 darauf aufbauen.

### 5.4 Enrollment- und Authentication-Flow anlegen

Im Authentik-Admin-Interface (**Flows and Stages**):

1. **Expression Policy** anlegen (Name z. B. `schul-domain-policy`), die
   prüft, dass `request.context["email"]` auf `@<schul-domain>` endet
   (Policy-Editor, Python-Expression, z. B.
   `return request.context.get("email", "").endswith("@<schul-domain>")`).
2. **Enrollment-Flow** anlegen: Identification-Stage (E-Mail-Eingabe) →
   Email-Stage (Bestätigungslink, Modus „Enrollment") → User-Write-Stage →
   User-Login-Stage. Die Expression Policy aus Punkt 1 an die
   Identification-Stage binden.
3. **Authentication-Flow** anlegen: Identification-Stage → Email-Stage
   (Modus „Authentication", Magic-Link statt Code) → User-Login-Stage.
4. Beide Flows unter **Enrollment**/**Authentication** in den jeweiligen
   Stage-Bindings als Standard für die im nächsten Schritt angelegte
   Application festlegen.

(Exakte Feldnamen im Editor können je nach Authentik-Version leicht
abweichen — falls ein Feld hier nicht wie beschrieben zu finden ist, in der
aktuellen Live-Doku unter `docs.goauthentik.io` nach „Email stage" bzw.
„Identification stage" suchen.)

### 5.5 Proxy-Provider + Outpost anlegen

1. **Applications → Providers → Create** → Typ „Proxy Provider".
2. Modus: „Forward auth (single application)".
3. **External Host: `https://lernen.<domain>`** (die geschützte App-URL
   selbst — nicht `auth.<domain>`. Der Single-Application-Modus verlangt
   laut offizieller Authentik-Doku ausdrücklich die eigene App-URL hier,
   damit Login-/Enrollment-Seiten auf `lernen.<domain>` bleiben, siehe
   nginx-Config in Task 3).
4. Authentication flow: der in 5.4 angelegte Authentication-Flow.
5. **Applications → Applications → Create**: an den Provider aus Punkt 1–4
   binden, Launch-URL `https://lernen.<domain>`.
6. **Applications → Outposts**: Standard-Outpost („authentik Embedded
   Outpost") prüfen — die neue Application sollte automatisch zugewiesen
   sein (Embedded Outpost übernimmt alle Provider ohne expliziten
   Outpost-Assign). Falls nicht: Application manuell zum Outpost
   hinzufügen.

`auth.<domain>` (Cloudflare-Tunnel-Hostname aus Runbook-Abschnitt 4) wird
hier **nicht** verwendet — das ist ausschließlich der direkte Zugriffsweg
auf das Authentik-Admin-Interface selbst (z. B. für 5.2–5.4), nicht Teil
des Schüler-Login-Ablaufs.

### 5.6 nginx-Config ausrollen

Wie bisher (siehe frühere Fassung dieses Abschnitts): Vom eigenen Rechner
mit Admin-SSH-Zugangsdaten übertragen, `<domain>`-Platzhalter ersetzen,
aktivieren:

```bash
scp deploy/nginx/pt-lernkarten.conf <dein-admin-user>@<VPS_HOST>:/tmp/pt-lernkarten.conf
```

Auf dem VPS:

```bash
sudo mv /tmp/pt-lernkarten.conf /etc/nginx/sites-available/pt-lernkarten.conf
sudo $EDITOR /etc/nginx/sites-available/pt-lernkarten.conf   # lernen.<domain> ersetzen
sudo nginx -t
sudo systemctl reload nginx
```
```

- [ ] **Step 3: Abschnitt 6 („Neue Adressen später hinzufügen") entfernen**

Kompletten Abschnitt „## 6. Neue Adressen später hinzufügen" (die drei
Zeilen von „Zero Trust Dashboard..." bis „...Kein Server-Zugriff nötig.")
löschen — entfällt durch Self-Service-Enrollment (siehe Design-Spec
Abschnitt 3).

- [ ] **Step 4: Diff prüfen**

Run: `git diff deploy/README.md`
Expected: Abschnitt 1–3 („GitHub Secrets", „Deploy-User", „nginx") und
„Phase 2" am Ende unverändert; Abschnitt 4 um einen Punkt erweitert;
Abschnitt 5 komplett neuer Inhalt; Abschnitt 6 entfernt.

- [ ] **Step 5: Committen**

```bash
git add deploy/README.md
git commit -m "Replace Cloudflare Access runbook section with Authentik setup"
```

---

### Task 5: Manuelle Infrastruktur-Einrichtung (interaktiv mit dem Nutzer)

**⚠️ Nicht automatisiert ausführen.** Erfordert echten SSH-Zugriff auf den
VPS und Zugriff auf das Cloudflare- sowie (nach Step 1) das
Authentik-Admin-Interface. Schritt für Schritt anhand von
`deploy/README.md` Abschnitt 4–5.

**Files:** keine (läuft auf VPS + Cloudflare-Dashboard + Authentik-Admin-UI, nicht im Repo)

- [ ] **Step 1:** Docker-Compose-Stack aufsetzen und starten (Runbook 5.1)
- [ ] **Step 2:** Admin-Account anlegen (Runbook 5.2)
- [ ] **Step 3:** SMTP-Notifier per Test-Benachrichtigung verifizieren (Runbook 5.3)
- [ ] **Step 4:** Enrollment- und Authentication-Flow inkl. Domain-Policy anlegen (Runbook 5.4)
- [ ] **Step 5:** Proxy-Provider + Application + Outpost anlegen (Runbook 5.5)
- [ ] **Step 6:** Zweiten Cloudflare-Tunnel-Hostname `auth.<domain>` → `localhost:9000` anlegen (Runbook Abschnitt 4, neuer Punkt 4)
- [ ] **Step 7:** Isolierter Test **vor** nginx-Umstellung (Spec Abschnitt 5, Schritt 1): die Flow-URL des Enrollment-Flows direkt aufrufen (`https://auth.<domain>/if/flow/<enrollment-flow-slug>/` — Slug aus 5.4 Punkt 2), mit einer beliebigen neuen Test-Adresse der Schul-Domain (nicht auf der alten Cloudflare-Allowlist) durchlaufen — Magic-Link kommt an, Klick erstellt Account und loggt ein. Das testet die Flow-/Policy-Logik isoliert, noch unabhängig vom Proxy-Provider/nginx-Redirect (der erst in Task 6 zum Einsatz kommt).
- [ ] **Step 8:** Test mit ungültiger Domain (Spec Abschnitt 6): Enrollment mit Adresse außerhalb `@<schul-domain>` → wird abgelehnt, keine Mail verschickt.

Cloudflare Access bleibt während dieses gesamten Tasks unverändert aktiv vor
`lernen.<domain>` — der produktive Zugriff für bestehende Nutzer ist zu
keinem Zeitpunkt unterbrochen.

---

### Task 6: nginx-Cutover und Integrationstest (interaktiv mit dem Nutzer)

**⚠️ Setzt Task 5 voraus.**

**Files:** keine

- [ ] **Step 1:** nginx-Config ausrollen (Runbook 5.6)
- [ ] **Step 2:** `https://lernen.<domain>` mit einer Adresse aufrufen, die
      bereits auf der alten Cloudflare-Access-Allowlist steht (Spec
      Abschnitt 5, Schritt 2–3). Erwartet: Cloudflare-Access-Login zuerst,
      danach Redirect zu `/outpost.goauthentik.io/start` (Authentik-Login,
      bleibt auf `lernen.<domain>`), nach Login zurück zur eigentlichen
      Seite, wird angezeigt.
- [ ] **Step 3:** Session-Verhalten prüfen: Seite neu laden ohne
      erneuten Login → weiterhin erreichbar (Session-Cookie greift).
- [ ] **Step 4:** Bei Problemen: **Rollback** — nginx-Änderung aus Task 3
      auf dem VPS zurücksetzen (`sudo nginx -t` mit der vorherigen
      Config-Version, `sudo systemctl reload nginx`), Cloudflare Access
      bleibt unverändert aktiv. Kein Datenverlust auf Authentik-Seite (Spec
      Abschnitt 5, „Rollback").

---

### Task 7: Cloudflare Access entfernen (interaktiv mit dem Nutzer)

**⚠️ Setzt Task 6 voraus — erst nach erfolgreichem Integrationstest ausführen.**

**Files:** keine

- [ ] **Step 1:** Cloudflare Zero Trust Dashboard → Access → Applications →
      die `lernen.<domain>`-Application löschen (inkl. Policy).
- [ ] **Step 2:** Cloudflare Tunnel bleibt unverändert bestehen — nur die
      Access-Application wird entfernt, nicht der Tunnel selbst.
      `systemctl status cloudflared` auf dem VPS weiterhin `active
      (running)` erwartet.
- [ ] **Step 3:** Self-Service-Enrollment jetzt mit einer komplett neuen,
      nicht vorher registrierten Schul-Domain-Adresse über `https://lernen.
      <domain>` end-to-end testen (kein Cloudflare-Access-Login mehr davor).
      Erwartet: direkter Redirect zu Authentik, Enrollment funktioniert,
      Zugriff auf die Seite danach möglich.
- [ ] **Step 4:** Login mit einer Adresse außerhalb der Schul-Domain über
      `https://lernen.<domain>` testen. Erwartet: wird von Authentik
      abgelehnt, kein Zugriff auf die Seite.

Ab diesem Punkt ist das 50-Nutzer-Limit aufgehoben — beliebig viele
Schul-Domain-Adressen können sich selbst registrieren.

**Bewusst nicht als eigener Checklisten-Schritt (spätere Spot-Checks statt
synchronem Test):**

- Der 24h-Session-Ablauf aus Spec Abschnitt 6 lässt sich nicht sinnvoll
  synchron in Task 6/7 abhaken (erfordert Warten oder künstliches
  Session-Cookie-Löschen). Bei Gelegenheit einmal nach >24h Nutzung
  stichprobenartig verifizieren, dass ein erneuter Login verlangt wird.
- Das SMTP-Ausfall-Szenario aus Spec Abschnitt 6 lässt sich nur durch
  bewusstes Kaputtmachen der SMTP-Zugangsdaten reproduzieren — kein Schritt
  in diesem Plan, da es die produktive SMTP-Konfiguration antasten würde.
  Bei einem echten SMTP-Ausfall (z. B. sichtbar an ausbleibenden
  Test-Mails in 5.3) das Worker-Log (`docker compose logs worker`) als
  ersten Debugging-Schritt heranziehen.

---

## Nach Abschluss

Sobald alle Tasks abgeschlossen und Task 7 erfolgreich validiert ist, steht
eine Entscheidung an, wie der Branch integriert wird — dafür die Skill
`superpowers:finishing-a-development-branch` verwenden.
