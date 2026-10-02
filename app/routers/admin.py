import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict
from ..db import get_db
from ..models import Project, Content, User, Contact, Newsletter, AuditLog
from ..schemas import ContentIn
from ..security import current_user, audit, GLOBAL_ROLES, check_project
from .public import public_project

router=APIRouter(prefix='/impact',tags=['Administration et contenus'])

class ProjectIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: str = Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    name: str = Field(min_length=1,max_length=200)
    slug: str = Field(min_length=1,max_length=120,pattern=r'^[a-z0-9-]+$')
    published: bool=False
    location: str=Field(default='',max_length=200)
    status: str=Field(default='En cours',pattern=r'^(En cours|Terminé)$')
    period: str=Field(default='',max_length=100)
    domains: list[str]=Field(default_factory=list,max_length=20)
    beneficiaries: int=Field(default=0,ge=0)
    partners: str=Field(default='',max_length=500)
    photo: str=Field(default='',max_length=2000)

def editor(user: User):
    if user.role not in {'SUPER_ADMIN','DIRECTION','COMMUNICATION'}:
        raise HTTPException(403,'Gestion éditoriale non autorisée.')

@router.get('/projects')
def projects(user: User=Depends(current_user),db: Session=Depends(get_db)):
    statement=select(Project)
    if user.role not in GLOBAL_ROLES and user.role!='COMMUNICATION':statement=statement.where(Project.id.in_(user.project_ids))
    return [{**public_project(p),'published':p.published} for p in db.scalars(statement)]

@router.post('/projects',status_code=201)
def create_project(payload: ProjectIn,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    if db.get(Project,payload.id) or db.scalar(select(Project).where((Project.slug==payload.slug)|(Project.name==payload.name))):
        raise HTTPException(409,'Projet, nom ou slug déjà utilisé.')
    project=Project(id=payload.id,name=payload.name,slug=payload.slug,published=payload.published,payload=payload.model_dump(exclude={'id','name','slug','published'}))
    db.add(project);audit(db,user,'project_created',project.id);db.commit()
    return {**public_project(project),'published':project.published}

@router.patch('/projects/{project_id}')
def update_project(project_id: str,payload: ProjectIn,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    project=db.get(Project,project_id)
    if not project:raise HTTPException(404,'Projet introuvable.')
    if payload.id!=project_id:raise HTTPException(422,'Identifiant non modifiable.')
    if db.scalar(select(Project).where(Project.id!=project_id,(Project.name==payload.name)|(Project.slug==payload.slug))):raise HTTPException(409,'Nom ou slug déjà utilisé.')
    project.name=payload.name;project.slug=payload.slug;project.published=payload.published;project.payload=payload.model_dump(exclude={'id','name','slug','published'})
    # Les noms dénormalisés destinés à React suivent le projet relationnel.
    from ..models import Record
    for record in db.scalars(select(Record).where(Record.project_id==project_id)):
        record.payload={**record.payload,'project':project.name}
    audit(db,user,'project_updated',project_id);db.commit()
    return {**public_project(project),'published':project.published}

@router.get('/content')
def content(user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    return [{'id':r.id,'kind':r.kind,'title':r.title,'published':r.published,'payload':r.payload} for r in db.scalars(select(Content))]

@router.post('/content',status_code=201)
def save_content(payload: ContentIn,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    url=payload.payload.get('url')
    if url and (not isinstance(url,str) or not url.startswith('https://')):
        raise HTTPException(422,'Une URL HTTPS est requise.')
    if payload.kind=='zone' and payload.title not in {'Boussé','Toéghin','Koudougou'}:
        raise HTTPException(422,'Commune non configurée : ajouter son centroïde dans le registre public.')
    if len(str(payload.payload))>20000:raise HTTPException(422,'Contenu trop volumineux.')
    if payload.kind=='video' and payload.published and not url:raise HTTPException(422,'URL du film requise pour publication.')
    if payload.kind=='document' and payload.published and not url:raise HTTPException(422,'URL du document original requise pour publication.')
    existing=db.get(Content,payload.id) if payload.id else None
    content=existing or Content(id=payload.id or str(uuid.uuid4()))
    content.kind=payload.kind;content.title=payload.title;content.published=payload.published;content.payload=payload.payload
    db.add(content);audit(db,user,'content_saved',content.id);db.commit()
    return {'id':content.id,'message':'Contenu enregistré.'}

@router.delete('/content/{content_id}')
def delete_content(content_id: str,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user);content=db.get(Content,content_id)
    if not content:raise HTTPException(404,'Contenu introuvable.')
    db.delete(content);audit(db,user,'content_deleted',content_id);db.commit();return {'message':'Contenu supprimé.'}

def management(user: User):
    if user.role not in {'SUPER_ADMIN','DIRECTION'}:raise HTTPException(403,'Accès réservé à la direction.')

@router.get('/messages')
def messages(user: User=Depends(current_user),db: Session=Depends(get_db)):
    management(user)
    return [{'id':r.id,'name':r.name,'email':r.email,'message':r.message,'status':r.status,'date':r.created_at.isoformat()} for r in db.scalars(select(Contact).order_by(Contact.created_at.desc()))]

class ContactStatus(BaseModel):
    status: str=Field(pattern=r'^(Reçu|En traitement|Traité)$')

@router.patch('/messages/{contact_id}')
def update_message(contact_id: str,payload: ContactStatus,user: User=Depends(current_user),db: Session=Depends(get_db)):
    management(user);contact=db.get(Contact,contact_id)
    if not contact:raise HTTPException(404,'Message introuvable.')
    contact.status=payload.status;audit(db,user,'message_updated',contact_id);db.commit();return {'status':contact.status}

@router.get('/newsletter')
def subscribers(user: User=Depends(current_user),db: Session=Depends(get_db)):
    management(user)
    return [{'id':r.id,'email':r.email,'date':r.created_at.isoformat()} for r in db.scalars(select(Newsletter))]

@router.get('/audit')
def logs(user: User=Depends(current_user),db: Session=Depends(get_db)):
    management(user)
    return [{'actorId':r.actor_id,'action':r.action,'resource':r.resource,'date':r.created_at.isoformat()} for r in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))]
