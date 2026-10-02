from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete, func, or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, AuthSession, LoginAttempt, now
from ..schemas import LoginIn, PasswordIn
from ..security import current_user, check_origin, passwords, DUMMY_HASH, digest, new_session, view_user, audit, COOKIE_NAME
from ..config import settings

router=APIRouter(prefix='/auth',tags=['Authentification'])

@router.post('/login')
def login(payload: LoginIn, request: Request, response: Response, db: Session=Depends(get_db)):
    check_origin(request)
    email=str(payload.email).lower()
    ip_key=digest(request.client.host if request.client else 'unknown')
    account_key=digest(email)
    cutoff=now()-timedelta(minutes=15)
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at<cutoff))
    attempts=db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.created_at>=cutoff,or_(LoginAttempt.account_key==account_key,LoginAttempt.ip_key==ip_key)))
    if attempts>=10:
        db.commit()
        raise HTTPException(429,'Trop de tentatives. Réessayez dans 15 minutes.')
    user=db.scalar(select(User).where(User.email==email))
    valid=passwords.verify(payload.password,user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active:
        db.add(LoginAttempt(account_key=account_key,ip_key=ip_key))
        audit(db,None,'login_failed',account_key)
        db.commit()
        raise HTTPException(401,'Adresse e-mail ou mot de passe incorrect.')
    db.execute(delete(AuthSession).where(AuthSession.expires_at<=now()))
    token,session=new_session(db,user)
    audit(db,user,'login',user.id)
    db.commit()
    response.set_cookie(COOKIE_NAME,token,httponly=True,secure=settings.cookie_secure,samesite=settings.cookie_samesite,max_age=settings.session_hours*3600,path='/')
    response.headers['Cache-Control']='no-store'
    return {'user':view_user(user),'csrfToken':session.csrf_token}

@router.get('/me')
def me(request: Request,response: Response,user: User=Depends(current_user)):
    response.headers['Cache-Control']='no-store'
    return {'user':view_user(user),'csrfToken':request.state.auth_session.csrf_token}

@router.post('/logout')
def logout(request: Request,response: Response,user: User=Depends(current_user),db: Session=Depends(get_db)):
    db.delete(request.state.auth_session)
    audit(db,user,'logout',user.id)
    db.commit()
    response.delete_cookie(COOKIE_NAME,path='/',secure=settings.cookie_secure,httponly=True,samesite=settings.cookie_samesite)
    return {'message':'Session fermée.'}

@router.post('/change-password')
def change_password(payload: PasswordIn,response: Response,user: User=Depends(current_user),db: Session=Depends(get_db)):
    if not passwords.verify(payload.current_password,user.password_hash):
        raise HTTPException(400,'Mot de passe actuel incorrect.')
    user.password_hash=passwords.hash(payload.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
    audit(db,user,'password_changed',user.id)
    db.commit()
    response.delete_cookie(COOKIE_NAME,path='/',secure=settings.cookie_secure,httponly=True,samesite=settings.cookie_samesite)
    return {'message':'Mot de passe changé. Reconnectez-vous.'}
