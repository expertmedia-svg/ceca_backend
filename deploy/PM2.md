# Déployer CECA-DR avec PM2 sur Debian

Backend : `https://cecadrbackend.yingr-ai.com`, port local `8657`. Frontend : `https://ceca-dr.com`. Exécuter PM2 sous le compte `debian` qui gère vos applications existantes, sans `sudo pm2`.

## Installation et démarrage

```bash
cd ~/apps/ceca_backend
git pull --ff-only
sudo apt update
sudo apt install -y python3-venv python3-pip
/usr/bin/python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 ou supérieur requis'"
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
cp deploy/pm2.env.example .env
chmod 600 .env
```

La copie de `.env` est réservée à la première installation. Lors d'une mise à jour, conserver votre `.env` existant. Python 3.11 ou ultérieur requis. Le chemin /usr/bin/python3 évite les shims pyenv qui peuvent sélectionner une ancienne version. Si le contrôle de version échoue, sélectionner explicitement un Python 3.11 ou supérieur avant de créer le venv. Ne pas continuer après une installation pip en erreur.

Cette configuration utilise SQLite : le fichier `ceca.db` est créé dans le dossier du backend et reste présent après les redémarrages. Un processus PM2 gère l'API. Si vous disposez déjà d'un PostgreSQL, renseigner son `DATABASE_URL` dans `.env` avant les migrations ; aucun service PostgreSQL n'est créé ni modifié automatiquement.

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.bootstrap --email votre-email@example.com
ss -ltn 'sport = :8657'
pm2 start ecosystem.config.js --only ceca-backend
pm2 save
pm2 status ceca-backend
curl -f http://127.0.0.1:8657/health
```

Remplacer l'adresse du compte. Le mot de passe administrateur est demandé dans le terminal sans affichage. Si le port 8657 est déjà utilisé par une autre application, résoudre ce conflit avant le démarrage. Aucune donnée locale de travail n'est importée.

Si PM2 n'est pas installé et Node/npm sont déjà présents : `sudo npm install -g pm2`. Pour le démarrage automatique au reboot, si votre PM2 existant n'est pas déjà configuré : exécuter `pm2 startup`, puis la commande sudo précise qu'il affiche, et `pm2 save`. Ne pas arrêter ou supprimer les autres applications.

En cas d'erreur : `pm2 logs ceca-backend --lines 80`.

## Nginx et HTTPS

Le DNS A de `cecadrbackend.yingr-ai.com` doit pointer sur cette VM. Installer Nginx et Certbot si nécessaire. Les fichiers Nginx du dépôt utilisent déjà le port 8657.

Premier certificat, avec les chemins Debian habituels :

```bash
sudo apt install -y nginx certbot
sudo mkdir -p /var/www/letsencrypt
sudo cp deploy/nginx-http.conf /etc/nginx/sites-available/cecadrbackend
sudo ln -s /etc/nginx/sites-available/cecadrbackend /etc/nginx/sites-enabled/cecadrbackend
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d cecadrbackend.yingr-ai.com
sudo cp deploy/nginx.conf /etc/nginx/sites-available/cecadrbackend
sudo nginx -t
sudo systemctl reload nginx
curl -f https://cecadrbackend.yingr-ai.com/health
sudo certbot renew --dry-run
```

Si le lien Nginx existe déjà, conserver ce lien au lieu de le recréer. Si le certificat existe déjà, passer directement à la copie de `deploy/nginx.conf`. Configurer un hook Certbot de rechargement Nginx après renouvellement. Autoriser les ports publics 80/443 ; garder 8657 lié à localhost.

## Frontend cPanel

Dans le projet React, avant compilation :

```dotenv
VITE_API_URL=https://cecadrbackend.yingr-ai.com
VITE_DATA_MODE=api
```

Publier le contenu de `dist/` avec `.htaccess` sur `ceca-dr.com`. Le dépôt backend ne contient pas le frontend. Vérifier depuis ce domaine : connexion, création/relecture d'un dossier, export et déconnexion.

Les cookies sont `SameSite=None; Secure` pour ces domaines distincts. Certains navigateurs bloquent les cookies tiers : si la connexion ne persiste pas malgré HTTPS et CORS corrects, utiliser un proxy sous le domaine frontend ou un sous-domaine API de `ceca-dr.com`, puis adapter les URLs et Nginx. Voir https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie.

## Mises à jour et sauvegarde

Faire une sauvegarde cohérente de SQLite avant les migrations. Exemple à l'aide de l'outil SQLite natif, installé avec `sudo apt install sqlite3` :

```bash
cd ~/apps/ceca_backend
umask 077
sqlite3 ceca.db ".backup 'ceca-backup.db'"
git pull --ff-only
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m alembic upgrade head
pm2 restart ecosystem.config.js --only ceca-backend --update-env
pm2 save
curl -f http://127.0.0.1:8657/health
```

Conserver les sauvegardes privées hors VM et tester leur restauration. Pour PostgreSQL, utiliser `pg_dump` sur votre base. Ne pas publier `.env`, les bases ni leurs sauvegardes.

Le fichier PM2 a été contrôlé syntaxiquement sur Windows. PM2/Nginx sur votre VM n'ont pas été exécutés depuis ce poste. Référence de configuration : https://pm2.keymetrics.io/docs/usage/application-declaration/.
