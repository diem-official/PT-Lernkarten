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
