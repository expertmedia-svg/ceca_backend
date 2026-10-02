# Déploiement recommandé : PM2

Le déploiement utilisé est **PM2**, sur le port local **8657**, avec Nginx pour **cecadrbackend.yingr-ai.com**. Suivre [le guide PM2](deploy/PM2.md). Configuration : [ecosystem.config.js](ecosystem.config.js) et [deploy/pm2.env.example](deploy/pm2.env.example). Le guide Docker ci-dessous reste une alternative facultative.

# CECA-DR — backend

API FastAPI indépendante du frontend. Dépôt destiné à la VM OVH : **https://cecadrbackend.yingr-ai.com**. Frontend React hébergé sur cPanel : **https://ceca-dr.com**.

Python 3.12, PostgreSQL 17 en production, SQLAlchemy/Alembic, authentification Argon2, sessions révocables, cookie HttpOnly/Secure, CSRF, sept rôles et restrictions par projet. Rapports PDF/Excel calculés par le serveur. Aucun mot de passe local, base locale ou frontend n'est inclus dans ce dépôt.

## Déployer sur la VM

Prérequis : VM Linux avec Docker et le plugin Compose, Nginx et Certbot ; accès sudo. Créer un enregistrement DNS A pour `cecadrbackend.yingr-ai.com` pointant vers l'IP de la VM. Autoriser HTTP/HTTPS dans les pare-feu OVH et du système. Adapter le chemin ci-dessous si nécessaire.

```sh
sudo git clone https://github.com/expertmedia-svg/ceca_backend.git /opt/ceca_backend
cd /opt/ceca_backend/deploy
sudo cp .env.example .env
sudo chmod 600 .env
```

Éditer `.env` et remplacer `POSTGRES_PASSWORD` par un secret long et alphanumérique. Génération possible avec `openssl rand -hex 32`. Conserver `CORS_ORIGINS=https://ceca-dr.com,https://www.ceca-dr.com`. Ne pas publier `.env`.

```sh
sudo docker compose up -d --build
sudo docker compose ps
curl -f http://127.0.0.1:8657/health
sudo docker compose exec api python -m app.bootstrap --email votre-adresse@example.org
```

Le mot de passe du premier SUPER_ADMIN est demandé sans affichage dans le terminal. Les migrations sont appliquées automatiquement avant le démarrage. La base de production est vide : créer les projets, comptes et dossiers depuis la plateforme. Aucun compte local ni donnée de travail n'est importé.

Le réseau Docker utilise `172.30.55.0/24`, gateway `172.30.55.1`. Si ce subnet est déjà utilisé, adapter `compose.yaml` et l'adresse de proxy de confiance dans le Dockerfile. PostgreSQL n'a aucun port public. L'API n'écoute sur l'hôte qu'en `127.0.0.1:8657`.

### Nginx et HTTPS : premier démarrage

Ces commandes supposent Nginx Debian/Ubuntu avec `sites-available`, `sites-enabled` et `/etc/nginx/proxy_params`. Le domaine doit déjà résoudre vers la VM.

```sh
sudo mkdir -p /var/www/letsencrypt
sudo cp nginx-http.conf /etc/nginx/sites-available/cecadrbackend
sudo ln -s /etc/nginx/sites-available/cecadrbackend /etc/nginx/sites-enabled/cecadrbackend
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d cecadrbackend.yingr-ai.com
sudo cp nginx.conf /etc/nginx/sites-available/cecadrbackend
sudo nginx -t
sudo systemctl reload nginx
curl -f https://cecadrbackend.yingr-ai.com/health
sudo certbot renew --dry-run
```

Si le lien `sites-enabled/cecadrbackend` existe déjà, conserver ce lien au lieu de le recréer. Configurer un hook de renouvellement Certbot qui recharge Nginx après renouvellement du certificat. La configuration finale utilise les certificats `/etc/letsencrypt/live/cecadrbackend.yingr-ai.com/` et limite les tentatives sur les formulaires publics et la connexion.

### Configuration du frontend sur cPanel

Dans le projet React, avant `npm run build` :

```dotenv
VITE_API_URL=https://cecadrbackend.yingr-ai.com
VITE_DATA_MODE=api
```

Transférer le contenu de `dist/` avec `.htaccess` dans `public_html/` du domaine `ceca-dr.com`. Ce dépôt GitHub ne contient pas le frontend.

Les domaines `ceca-dr.com` et `yingr-ai.com` sont des sites distincts : le backend utilise `SameSite=None; Secure` et des origines CORS précises, avec validation CSRF. Certains navigateurs peuvent bloquer les cookies tiers malgré cette configuration. Pour une connexion indépendante de ce blocage, utiliser un proxy API sous le domaine frontend ou un domaine backend tel que `api.ceca-dr.com` dirigé vers la VM, puis adapter Nginx et l'URL React. Référence : https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#samesitesamesite-value

Tester après déploiement depuis le vrai frontend : connexion, création/relecture d'un dossier, exports PDF/Excel et déconnexion. Le déploiement distant n'a pas été exécuté depuis le poste Windows.

## Installation locale depuis ce dépôt seul

```sh
python -m venv .venv
# Linux :
.venv/bin/python -m pip install -r requirements.lock.txt
cp .env.example .env
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.bootstrap --email votre-adresse@example.org
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Sous Windows utiliser `.venv/Scripts/python.exe`. Les valeurs `.env.example` sont locales (SQLite, cookies non Secure et SameSite=lax), sans chargement de données de travail. Documentation locale : http://localhost:8000/docs. Documentation désactivée en production.

`setup_local.py` sert au workspace React d'origine avec un fichier `work-data.json` externe au dépôt ; il n'est pas nécessaire pour ce déploiement. `app.seed` ne s'exécute pas automatiquement et les données de travail sont interdites en production.

## Fonctionnalités et routes

- `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/change-password` : comptes et sessions ; changements de mot de passe révoquant toutes les sessions.
- `/impact/producteurs`, `/impact/menages`, `/impact/transformateurs`, `/impact/parcelles`, `/impact/productions`, `/impact/organisations`, `/impact/indicateurs`, `/impact/utilisateurs` : CRUD.
- `/impact/projects`, `/impact/content` : projets et contenus publiés.
- `/impact/dashboard`, `/impact/map` : agrégats et coordonnées autorisées.
- `/reports`, `/reports/export/pdf`, `/reports/export/xlsx` : calcul et exports serveur.
- `/impact/producteurs/:id/consent`, `/impact/producteurs/:id/economic.pdf` : consentement tracé et export économique.
- `/public/catalog`, `/projects`, `/projects/:slug`, `/public/zones` : catalogue sans dossiers ni coordonnées individuelles.
- `/contact`, `/newsletter` : réception en base ; `/impact/messages`, `/impact/newsletter`, `/impact/audit` : consultation privée.

Les exports acceptent `?transport=json` pour éviter l'interception des réponses binaires par des logiciels locaux de téléchargement. Le fichier est encodé en base64 avec son type MIME ; les autorisations restent identiques au transfert binaire.

SUPER_ADMIN : comptes et gestion globale. DIRECTION/SUIVI_EVALUATION : données globales. CHEF_PROJET/AGENT_TERRAIN : projets assignés. COMMUNICATION : contenus, sans dossiers personnels. PARTENAIRE : agrégats assignés, sans mutation ni dossiers individuels. Le dernier administrateur actif est protégé. Les parcelles/productions doivent référencer un producteur du même projet.

Les dossiers utilisent un modèle projet/dossier avec payload métier JSON validé. Les informations économiques absentes ne sont pas inventées. La traçabilité du consentement saisi par l'agent ne remplace pas sa collecte auprès de la personne. Aucun SMTP ni campagne newsletter n'est configuré ; les messages sont consultables dans la plateforme. Les médias sont des URL HTTPS, sans téléversement.

## Tests

```sh
# Linux :
.venv/bin/python -m pytest -q
# Windows :
.venv/Scripts/python.exe -m pytest -q
```

Base de tests en mémoire isolée : authentification, CSRF, révocation, rôles/projets, CRUD et relations, comptes, filtres et exports, consentement, confidentialité publique et carte privée.

## Mise à jour et sauvegarde

```sh
cd /opt/ceca_backend
sudo git pull --ff-only
cd deploy
sudo docker compose up -d --build
sudo docker compose logs --tail=100 api
```

Sauvegarder PostgreSQL avant mise à jour et planifier des sauvegardes privées hors VM avec restauration testée :

```sh
umask 077
sudo docker compose exec -T db pg_dump -U ceca -d ceca > sauvegarde-ceca.sql
```

Les volumes persistent entre redémarrages. Ne pas utiliser `docker compose down -v` pour une simple mise à jour.

## Administration des pages publiques

Le frontend dispose du dashboard `/impact/site` (« Contenus du site »), réservé à SUPER_ADMIN, DIRECTION et COMMUNICATION. Les huit pages publiques sont éditables : titres, présentations, images, boutons et rubriques ordonnées ; les rubriques Actualités sont des articles. Les projets, vidéos et documents restent gérés par leurs modules.

Routes : `GET /impact/site-pages`, `PUT /impact/site-pages/:slug`, `DELETE /impact/site-pages/:slug` ; seules les versions publiées sont exposées dans `GET /public/catalog`. Les pages sont stockées dans la table de contenus existante : aucune migration supplémentaire nécessaire. Enregistrer sans publication retire la version personnalisée du site ; les éléments de présentation par défaut restent affichés.

`POST /impact/media` accepte le corps binaire d'une image JPG/PNG/WebP (10 Mo, 16 millions de pixels maximum), vérifie l'image, retire ses métadonnées et la convertit en WebP. Les fichiers sont conservés dans `uploads/` et servis publiquement sous `/media/`. Réserver ces images à une diffusion publique ; sauvegarder `uploads/` avec la base. Ce dossier est exclu de Git.

Après `git pull --ff-only`, relancer uniquement `ceca-backend`. Copier aussi la nouvelle configuration `deploy/nginx.conf` vers le site Nginx puis valider et recharger Nginx, afin d'autoriser les chargements d'images jusqu'à 10 Mo. Publier le nouveau build React sur cPanel.
