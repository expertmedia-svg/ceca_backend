"""Initialisation locale idempotente ; aucune diffusion de secrets dans les logs."""
import secrets
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parent
env=root/'.env'
if not env.exists():env.write_text('ENVIRONMENT=development\nCOOKIE_SECURE=false\nSEED_WORK_DATA=true\nCORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:4173\nSESSION_HOURS=8\n',encoding='utf-8')
subprocess.run([sys.executable,'-m','alembic','-c',str(root/'alembic.ini'),'upgrade','head'],cwd=root,check=True)
from app.bootstrap import create_admin
from app.seed import seed
password=secrets.token_urlsafe(20)
if create_admin('admin@cecadr.org','Administrateur CECA-DR',password):
    (root/'ACCES_LOCAL.txt').write_text(f'Accès au backend local CECA-DR\nURL : http://localhost:5173/impact/login\nE-mail : admin@cecadr.org\nMot de passe : {password}\n\nCompte réel de développement, SUPER_ADMIN. Mot de passe généré aléatoirement.\nConserver ce fichier en lieu sûr ; il est exclu de Git.\nChanger le mot de passe avant toute publication.\n',encoding='utf-8')
seed()
print('Base créée, migrations appliquées, compte local et données de travail disponibles. Identifiants dans backend/ACCES_LOCAL.txt ; aucun secret affiché.')
