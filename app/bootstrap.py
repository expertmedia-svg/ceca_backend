"""Créer un compte administrateur sans mot de passe par défaut dans le code."""
import argparse
import getpass
import uuid
from sqlalchemy import select
from pydantic import TypeAdapter, EmailStr
from .db import SessionLocal
from .models import User
from .security import passwords

def create_admin(email: str,name: str,password: str):
    email=str(TypeAdapter(EmailStr).validate_python(email)).lower()
    if len(password)<12:raise ValueError('12 caractères minimum.')
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email==email)):
            return False
        db.add(User(id=str(uuid.uuid4()),email=email,name=name,password_hash=passwords.hash(password),role='SUPER_ADMIN',project_ids=[],active=True));db.commit()
        return True

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--email',required=True);parser.add_argument('--name',default='Administrateur CECA-DR');args=parser.parse_args()
    password=getpass.getpass('Mot de passe (12 caractères minimum) : ')
    if password!=getpass.getpass('Confirmer : '):raise SystemExit('Mots de passe différents.')
    print('Compte créé.' if create_admin(args.email,args.name,password) else 'Compte déjà existant ; mot de passe conservé.')
