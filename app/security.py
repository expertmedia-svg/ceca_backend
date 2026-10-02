import hashlib
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import AuthSession, User, AuditLog, now

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(24))
COOKIE_NAME = 'ceca_session'
GLOBAL_ROLES = {'SUPER_ADMIN','DIRECTION','SUIVI_EVALUATION'}
WRITE_ROLES = GLOBAL_ROLES | {'CHEF_PROJET','AGENT_TERRAIN'}
PERSONAL = {'producteurs','menages','transformateurs','parcelles','productions'}

def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()

def check_origin(request: Request):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') not in settings.origins:
        raise HTTPException(403, 'Origine non autorisée.')

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token=request.cookies.get(COOKIE_NAME)
    session=db.get(AuthSession, digest(token)) if token else None
    if not session or session.expires_at<=now():
        raise HTTPException(401, 'Session absente ou expirée.')
    user=db.get(User,session.user_id)
    if not user or not user.active:
        raise HTTPException(401,'Compte désactivé.')
    if request.method not in {'GET','HEAD','OPTIONS'}:
        check_origin(request)
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.csrf_token):
            raise HTTPException(403,'Jeton CSRF invalide.')
    request.state.auth_session=session
    return user

def view_user(user: User):
    return {'id':user.id,'name':user.name,'email':user.email,'role':user.role,'projectIds':user.project_ids,'status':'Actif' if user.active else 'Archivé'}

def require_admin(user: User = Depends(current_user)):
    if user.role!='SUPER_ADMIN':
        raise HTTPException(403,'Réservé au super administrateur.')
    return user

def check_collection(user: User, collection: str, write=False):
    if collection=='utilisateurs':
        if user.role!='SUPER_ADMIN':
            raise HTTPException(403,'Gestion des utilisateurs non autorisée.')
    elif user.role=='COMMUNICATION' or (collection in PERSONAL and user.role=='PARTENAIRE'):
        raise HTTPException(403,'Accès aux données individuelles non autorisé.')
    if write and user.role not in WRITE_ROLES:
        raise HTTPException(403,'Modification non autorisée.')

def check_project(user: User, project_id: str):
    if user.role not in GLOBAL_ROLES and project_id not in user.project_ids:
        raise HTTPException(403,'Projet non autorisé.')

def audit(db: Session, user: User | None, action: str, resource: str):
    db.add(AuditLog(actor_id=user.id if user else None, action=action,resource=resource))

def new_session(db: Session, user: User):
    token=secrets.token_urlsafe(48)
    session=AuthSession(token_hash=digest(token),user_id=user.id,csrf_token=secrets.token_urlsafe(32),expires_at=now()+timedelta(hours=settings.session_hours))
    db.add(session)
    return token,session
