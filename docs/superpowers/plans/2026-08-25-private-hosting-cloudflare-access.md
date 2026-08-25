# Privates Hosting mit Cloudflare Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die statische Web-App zusätzlich auf einem eigenen VPS bereitstellen, geschützt durch Cloudflare Access (E-Mail-Allowlist, passwortloser One-Time-PIN-Login), automatisch deployed per GitHub Actions — parallel zur bestehenden öffentlichen GitHub-Pages-Seite, ohne diese anzutasten.

**Architecture:** Ein zweiter Job im bestehenden GitHub-Actions-Workflow synct `web/` per rsync über SSH auf einen VPS, wo nginx den Ordner statisch ausliefert. Ein Cloudflare Tunnel (`cloudflared`) verbindet den VPS ohne offene Firewall-Ports mit Cloudflare; eine Cloudflare-Access-Application davor lässt nur E-Mail-Adressen einer festen Allowlist durch (Login per Einmal-Code, keine Passwörter, kein eigener Auth-Code). Die bestehende GitHub-Pages-Auslieferung bleibt unverändert bestehen (Phase 1, siehe Spec Abschnitt 5).

**Tech Stack:** GitHub Actions, rsync/SSH, nginx, Cloudflare Tunnel (cloudflared), Cloudflare Zero Trust Access.

**Spec:** [docs/superpowers/specs/2026-08-25-private-hosting-cloudflare-access-design.md](../specs/2026-08-25-private-hosting-cloudflare-access-design.md)

---

## Wichtiger Hinweis für die Ausführung

Dieser Plan hat zwei sehr unterschiedliche Sorten von Aufgaben:

- **Tasks 1–4** ändern nur Dateien in diesem Repo (Workflow-YAML, Config-Vorlage, Dokumentation). Sicher, reversibel, git-verfolgt — geeignet für automatisierte Subagent-Ausführung.
- **Tasks 5–6** erfordern echten SSH-Zugriff auf den produktiven VPS des Nutzers und Klicks im echten Cloudflare-Dashboard des Nutzers. Ein Subagent hat dafür weder Zugangsdaten noch Berechtigung, autonom auf Produktionsinfrastruktur zu wirken. **Diese beiden Tasks müssen interaktiv zusammen mit dem Nutzer ausgeführt werden** — der Nutzer führt Kommandos auf seinem Server selbst aus (ggf. mit Claude Code an seiner Seite in einer separaten, interaktiven Session), Dashboard-Schritte macht er ebenfalls selbst. Ein automatisierter Task-Runner sollte hier stoppen und an den Nutzer übergeben, statt zu raten oder Zugangsdaten zu erfinden.

---

## Vorbereitung: Datei-Übersicht

| Datei | Aktion | Zweck |
|---|---|---|
| `.github/workflows/deploy.yml` | Ändern | Neuer Job `deploy-vps` neben dem bestehenden Pages-Job |
| `deploy/nginx/pt-lernkarten.conf` | Neu | nginx-Server-Block-Vorlage für den VPS |
| `deploy/README.md` | Neu | Runbook: GitHub Secrets, VPS-Einrichtung, Cloudflare-Einrichtung, Testcheckliste, Phase-2-Hinweis |

---

### Task 1: Feature-Branch anlegen

**Files:** keine (reine Git-Operation)

- [ ] **Step 1: Arbeitsstand prüfen**

Run: `git status`

Falls `nothing to commit, working tree clean` — weiter mit Step 2.

Falls uncommitted Änderungen angezeigt werden (unabhängig von diesem Plan
entstanden): **nicht automatisch committen oder verwerfen.** `git checkout -b`
nimmt uncommitted Änderungen mit auf den neuen Branch (sie gehen nicht
verloren), aber das kann unbeabsichtigt fremde Arbeit mit diesem Feature
vermischen. Den Nutzer fragen, ob diese Änderungen (a) getrennt vorher
committet, (b) per `git stash` beiseitegelegt, oder (c) bewusst mit auf den
neuen Branch genommen werden sollen — dann erst mit Step 2 fortfahren.

- [ ] **Step 2: Branch erstellen und wechseln**

```bash
git checkout -b feature/private-hosting-cloudflare-access
```

- [ ] **Step 3: Verifizieren**

Run: `git branch --show-current`
Expected: `feature/private-hosting-cloudflare-access`

Alle folgenden Tasks (Commits) passieren auf diesem Branch.

---

### Task 2: nginx-Konfigurationsvorlage erstellen

**Files:**
- Create: `deploy/nginx/pt-lernkarten.conf`

- [ ] **Step 1: Verzeichnis anlegen und Datei schreiben**

```
deploy/nginx/pt-lernkarten.conf
```

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

Kein TLS-Block nötig: der Cloudflare Tunnel verbindet sich lokal per HTTP mit nginx, Cloudflare übernimmt HTTPS am Edge (siehe Spec Abschnitt 2).

- [ ] **Step 2: Syntax prüfen**

Falls nginx lokal installiert ist:
Run: `nginx -t -c "$(pwd)/deploy/nginx/pt-lernkarten.conf"`
Expected: keine Syntaxfehler (Warnungen zu fehlendem `events`/`http`-Block sind bei einer reinen Server-Block-Vorlage normal und werden erst auf dem VPS im vollständigen nginx-Kontext relevant)

Falls nginx lokal nicht installiert ist: Diesen Schritt überspringen, die verbindliche Prüfung erfolgt in Task 5 auf dem VPS selbst (`sudo nginx -t`).

- [ ] **Step 3: Committen**

```bash
git add deploy/nginx/pt-lernkarten.conf
git commit -m "Add nginx config template for VPS static hosting"
```

---

### Task 3: GitHub-Actions-Workflow um VPS-Deploy-Job erweitern

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Neuen Job hinzufügen**

Bestehenden `deploy`-Job (Pages) unverändert lassen, folgenden Job am Ende der Datei ergänzen:

```yaml
  deploy-vps:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Install SSH key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.VPS_SSH_KEY }}
      - name: Add VPS to known_hosts
        run: ssh-keyscan -H "${{ secrets.VPS_HOST }}" >> ~/.ssh/known_hosts
      - name: Deploy via rsync
        run: |
          rsync -avz --delete \
            -e "ssh -o StrictHostKeyChecking=yes" \
            web/ \
            "${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }}:/var/www/pt-lernkarten/"
```

Der Job läuft unabhängig und parallel zum bestehenden `deploy`-Job (kein `needs:`), beide werden vom selben `on: push` / `workflow_dispatch`-Trigger ausgelöst. Die Secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` existieren erst nach Task 5 — bis dahin schlägt dieser Job fehl, falls er läuft, was auf dem Feature-Branch unschädlich ist (der Push-Trigger reagiert nur auf `Geminis-Go`, siehe `on.push.branches`).

Die vorhandene `concurrency: group: "pages"`-Einstellung am Kopf der Datei gilt für den gesamten Workflow, also auch für `deploy-vps` (Concurrency-Gruppen sind workflow-, nicht job-spezifisch). Das ist hier unproblematisch/gewollt — verhindert nur, dass zwei parallele Workflow-Läufe gleichzeitig deployen — sollte aber nicht mit einem Bug verwechselt werden, falls bei Task 6 ein zweiter Push während eines laufenden Deploys den ersten Lauf abbricht.

- [ ] **Step 2: YAML-Syntax prüfen**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo OK`
Expected: `OK`

- [ ] **Step 3: Diff prüfen — bestehender Pages-Job unangetastet**

Run: `git diff .github/workflows/deploy.yml`
Expected: Diff zeigt ausschließlich Zeilen-Hinzufügungen (neuer `deploy-vps`-Job), keine Änderung am bestehenden `deploy`-Job.

- [ ] **Step 4: Committen**

```bash
git add .github/workflows/deploy.yml
git commit -m "Add parallel VPS deploy job alongside existing GitHub Pages deploy"
```

---

### Task 4: Deploy-Runbook schreiben

**Files:**
- Create: `deploy/README.md`

- [ ] **Step 1: Runbook schreiben**

```
deploy/README.md
```

```markdown
# Deploy-Runbook: Privates Hosting mit Cloudflare Access

Dieses Dokument beschreibt die **einmalige, manuelle** Einrichtung von VPS und
Cloudflare. Diese Schritte werden nicht automatisiert ausgeführt — sie
erfordern echten SSH-Zugriff auf den produktiven Server und Zugriff auf das
eigene Cloudflare-Konto.

Siehe auch: [Design-Spec](../docs/superpowers/specs/2026-08-25-private-hosting-cloudflare-access-design.md)

## 1. GitHub Secrets anlegen

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Name | Wert |
|---|---|
| `VPS_HOST` | IP-Adresse oder Hostname des VPS |
| `VPS_USER` | `deploy` (siehe Abschnitt 2) |
| `VPS_SSH_KEY` | Privater Teil des in Abschnitt 2 erzeugten SSH-Schlüssels |

## 2. Deploy-User auf dem VPS einrichten

Als root auf dem VPS:

```bash
adduser --disabled-password --gecos "" deploy
mkdir -p /var/www/pt-lernkarten
chown deploy:deploy /var/www/pt-lernkarten
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
```

SSH-Schlüsselpaar lokal erzeugen (nicht ins Repo committen!):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./deploy_key -N ""
```

`deploy_key.pub` (öffentlicher Teil) auf den VPS in
`/home/deploy/.ssh/authorized_keys` eintragen — auf **diesen** Nutzer
beschränkt mit `rrsync`, damit der Deploy-User ausschließlich in
`/var/www/pt-lernkarten/` schreiben kann (kein voller Shell-Zugriff):

```bash
# Auf modernen Debian/Ubuntu-Versionen (rsync >= 3.2.x) liegt rrsync bereits
# ausführbar bei, erst prüfen:
which rrsync
# Erwartet: /usr/bin/rrsync — falls vorhanden, direkt diesen Pfad verwenden
# und den folgenden Block überspringen.

# Nur falls `which rrsync` nichts findet (sehr alte Distribution):
dpkg -L rsync | grep rrsync   # Pfad zur ggf. gepackten Skript-Datei ermitteln
# je nach gefundenem Pfad z.B.:
sudo cp /usr/share/doc/rsync/scripts/rrsync.gz /usr/local/bin/rrsync.gz
sudo gunzip /usr/local/bin/rrsync.gz
sudo chmod +x /usr/local/bin/rrsync
```

`/home/deploy/.ssh/authorized_keys` (Pfad zu `rrsync` durch das Ergebnis von
`which rrsync` ersetzen, z. B. `/usr/bin/rrsync`; `-wo` beschränkt den
Deploy-User zusätzlich auf Schreiben, kein Zurücklesen des Verzeichnisses
über diesen Schlüssel):

```
command="/usr/bin/rrsync -wo /var/www/pt-lernkarten/",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA...deploy_key.pub-Inhalt hier einfügen
```

```bash
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
```

Inhalt von `deploy_key` (privater Teil, **ohne** Passphrase) als
`VPS_SSH_KEY`-Secret in GitHub hinterlegen (siehe Abschnitt 1), danach lokale
Kopien beider Schlüsseldateien löschen.

> Hinweis: `rrsync` erzwingt das erlaubte Zielverzeichnis serverseitig —
> unabhängig davon, welchen Pfad der rsync-Client aus der GitHub Action
> übergibt, landen Dateien ausschließlich in `/var/www/pt-lernkarten/`.

## 3. nginx einrichten

```bash
sudo apt update && sudo apt install -y nginx
```

Die Config-Vorlage liegt nur im Repo, nicht automatisch auf dem VPS — der
Deploy-User aus Abschnitt 2 hat dafür bewusst keinen Zugriff (nur
`rsync`-Schreibrechte auf `/var/www/pt-lernkarten/`). Vom eigenen Rechner
aus mit den **eigenen** (Admin-)SSH-Zugangsdaten übertragen, nicht mit dem
Deploy-Key:

```bash
scp deploy/nginx/pt-lernkarten.conf <dein-admin-user>@<VPS_HOST>:/tmp/pt-lernkarten.conf
```

Auf dem VPS:

```bash
sudo mv /tmp/pt-lernkarten.conf /etc/nginx/sites-available/pt-lernkarten.conf
sudo $EDITOR /etc/nginx/sites-available/pt-lernkarten.conf   # "lernen.<domain>" durch echte Domain ersetzen
sudo ln -s /etc/nginx/sites-available/pt-lernkarten.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 4. Cloudflare Tunnel einrichten

1. Cloudflare Zero Trust Dashboard → **Networks → Tunnels → Create a tunnel**
   → Connector-Typ „Cloudflared" → Name z. B. `pt-lernkarten`.
2. Das Dashboard zeigt ein Install-Kommando für Debian/Ubuntu (fügt
   Cloudflares Paketquelle hinzu, installiert `cloudflared`, registriert den
   Tunnel als Service). Dieses Kommando als root auf dem VPS ausführen.
3. Im Tunnel unter **Public Hostname**: Hostname `lernen.<domain>` →
   Service-Typ `HTTP`, URL `localhost:80`.
4. Prüfen: `systemctl status cloudflared` → `active (running)`; Tunnel zeigt
   im Dashboard Status „Healthy".

## 5. Cloudflare Access einrichten

1. Zero Trust Dashboard → **Access → Applications → Add an application** →
   „Self-hosted".
2. Domain: `lernen.<domain>`.
3. Policy anlegen: Name z. B. „Klassenkameraden", Action `Allow`, Include-Regel
   „Emails" → jede erlaubte Adresse einzeln eintragen.
4. Unter **Settings → Authentication** prüfen, dass „One-time PIN" als
   Login-Methode aktiv ist (Standard-Einstellung).
5. Session-Dauer der Application nach Bedarf einstellen (Standard 24 h ist
   für dieses Projekt ausreichend).

## 6. Neue Adressen später hinzufügen

Zero Trust Dashboard → Access → Applications → Policy „Klassenkameraden" →
neue E-Mail-Adresse zur Include-Liste hinzufügen. Kein Server-Zugriff nötig.

## Phase 2 (später, nicht Teil dieser Umsetzung)

Sobald die neue Infrastruktur validiert ist und nicht mehr gebraucht wird,
GitHub Pages abzuschalten:

1. Repo → Settings → Pages → Source auf „None" setzen (oder Pages-Job aus
   `.github/workflows/deploy.yml` entfernen).
2. Repo → Settings → General → Danger Zone → „Change visibility" → Private.

Diese beiden Schritte bewusst **manuell und zeitlich unabhängig** vom
restlichen Plan — siehe Spec Abschnitt 5.
```

- [ ] **Step 2: Committen**

```bash
git add deploy/README.md
git commit -m "Add deploy runbook for VPS + Cloudflare Access setup"
```

---

### Task 5: Manuelle Infrastruktur-Einrichtung (interaktiv mit dem Nutzer)

**⚠️ Nicht automatisiert ausführen.** Dieser Task braucht echte SSH-Zugangsdaten
zum VPS des Nutzers und Zugriff auf dessen Cloudflare-Konto. Führe ihn
zusammen mit dem Nutzer aus, Schritt für Schritt anhand von
`deploy/README.md`.

**Files:** keine (läuft vollständig auf VPS + Cloudflare-Dashboard, nicht im Repo)

- [ ] **Step 1:** GitHub Secrets anlegen (Runbook Abschnitt 1)
- [ ] **Step 2:** Deploy-User + `rrsync`-Beschränkung auf dem VPS einrichten (Runbook Abschnitt 2)
- [ ] **Step 3:** nginx installieren und Config aktivieren (Runbook Abschnitt 3)
- [ ] **Step 4:** Cloudflare Tunnel einrichten (Runbook Abschnitt 4)
- [ ] **Step 5:** Cloudflare Access Application + Allowlist-Policy einrichten (Runbook Abschnitt 5)
- [ ] **Step 6:** Verifizieren, dass `systemctl status cloudflared` und `systemctl status nginx` beide `active (running)` zeigen

---

### Task 6: End-to-End-Validierung (interaktiv mit dem Nutzer)

**⚠️ Setzt Task 5 voraus.** Läuft gegen die echte, produktive Infrastruktur.

**Files:** keine

- [ ] **Step 1: Workflow manuell auslösen**

GitHub → Actions → Workflow „Deploy static content to GitHub Pages" →
„Run workflow" → Branch `feature/private-hosting-cloudflare-access` → Run.

(Der bestehende Workflow hat bereits einen `workflow_dispatch`-Trigger — so
lässt sich `deploy-vps` testen, ohne vorher auf `Geminis-Go` zu mergen.)

Expected: Beide Jobs (`deploy` und `deploy-vps`) laufen grün durch.

- [ ] **Step 2: Dateirechte nach dem ersten echten Deploy prüfen**

Run: `sudo -u www-data test -r /var/www/pt-lernkarten/index.html && echo OK`
Expected: `OK` (unter dem Standard-umask 022 des `deploy`-Users normalerweise
unproblematisch, aber ein bekannter Stolperstein bei dedizierten
Deploy-Usern)

- [ ] **Step 3: Login mit erlaubter Adresse testen**

`https://lernen.<domain>` im Browser aufrufen, eigene (gelistete)
E-Mail-Adresse eingeben.
Expected: Code-Mail kommt an, nach Eingabe ist die Seite erreichbar,
Session bleibt nach Browser-Neustart bestehen.

- [ ] **Step 4: Login mit nicht gelisteter Adresse testen**

Eine Test-Adresse eingeben, die nicht auf der Allowlist steht.
Expected: Zugriff wird abgelehnt, keine Mail wird verschickt.

- [ ] **Step 5: Parallelbetrieb bestätigen**

Alte GitHub-Pages-URL und neue Domain `lernen.<domain>` beide im Browser
aufrufen.
Expected: Beide zeigen den aktuellen Stand der Seite (Pages weiterhin
öffentlich erreichbar, eigene Domain nur nach Login).

---

## Nach Abschluss

Sobald alle Tasks abgeschlossen und Task 6 erfolgreich validiert ist, steht
eine Entscheidung an, wie der Branch integriert wird (Merge nach
`Geminis-Go`, Pull Request, o. ä.) — dafür die Skill
`superpowers:finishing-a-development-branch` verwenden.

Phase 2 (GitHub Pages abschalten, Repo auf Privat stellen) bleibt bewusst
ein separater, vom Nutzer selbst zu wählender späterer Zeitpunkt (siehe
`deploy/README.md`, Abschnitt „Phase 2").
