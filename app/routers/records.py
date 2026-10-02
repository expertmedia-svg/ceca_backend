import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..db import get_db
from ..models import User, Record, Project, AuthSession
from ..schemas import RecordIn, UserIn
from ..security import current_user, check_collection, check_project, GLOBAL_ROLES, passwords, view_user, audit

router=APIRouter(prefix='/impact',tags=['Dossiers terrain'])
COLLECTIONS={'producteurs','menages','transformateurs','parcelles','productions','organisations','indicateurs'}
REQUIRED={'producteurs':{'sex','activity','surface','production','visit'},'menages':{'members'},'transformateurs':{'activity','production'},'parcelles':{'producerId','surface','crop'},'productions':{'producerId','quantity','date'},'organisations':{'members'},'indicateurs':{'value','unit'}}

def scoped_records(db: Session,user: User,collection: str):
    statement=select(Record).where(Record.collection==collection)
    if user.role not in GLOBAL_ROLES:
        statement=statement.where(Record.project_id.in_(user.project_ids))
    return statement

def serialize(record: Record):
    return record.payload

def find_record(db: Session,user: User,collection: str,record_id: str):
    if collection not in COLLECTIONS:
        raise HTTPException(404,'Collection inconnue.')
    check_collection(user,collection)
    record=db.scalar(scoped_records(db,user,collection).where(Record.external_id==record_id))
    if not record:
        raise HTTPException(404,'Dossier introuvable.')
    return record

def validate_record(db: Session,user: User,collection: str,payload: RecordIn):
    if collection not in COLLECTIONS:
        raise HTTPException(404,'Collection inconnue.')
    check_collection(user,collection,write=True)
    data=payload.model_dump()
    if not REQUIRED[collection]<=data.keys():
        raise HTTPException(422,'Champs métier obligatoires manquants.')
    if collection=='producteurs' and data['sex'] not in {'Femme','Homme'}:
        raise HTTPException(422,'Sexe invalide.')
    project=db.scalar(select(Project).where(Project.name==payload.project))
    if not project:
        raise HTTPException(422,'Projet inconnu.')
    check_project(user,project.id)
    if collection in {'parcelles','productions'}:
        producer=db.scalar(scoped_records(db,user,'producteurs').where(Record.external_id==data['producerId'],Record.project_id==project.id))
        if not producer:
            raise HTTPException(422,'Producteur lié introuvable dans ce projet.')
    return project,data

def user_record(db: Session,user: User):
    project=db.get(Project,user.project_ids[0]) if user.project_ids else None
    return {**view_user(user),'project':project.name if project else '', 'village':'','year':'2026'}

def save_user(db: Session,actor: User,payload: UserIn,existing: User|None=None):
    check_collection(actor,'utilisateurs',write=True)
    project_ids=payload.projectIds
    if not project_ids and payload.project:
        project=db.scalar(select(Project).where(Project.name==payload.project))
        if not project:raise HTTPException(422,'Projet inconnu.')
        project_ids=[project.id]
    if any(db.get(Project,pid) is None for pid in project_ids):
        raise HTTPException(422,'Projet assigné inconnu.')
    if not existing and not payload.password:
        raise HTTPException(422,'Un mot de passe de 12 caractères minimum est requis.')
    if existing and existing.role=='SUPER_ADMIN' and (payload.role.value!='SUPER_ADMIN' or payload.status!='Actif'):
        admins=db.scalar(select(func.count()).select_from(User).where(User.role=='SUPER_ADMIN',User.active.is_(True)))
        if admins<=1:raise HTTPException(409,'Le dernier super administrateur actif doit être conservé.')
    user=existing or User(id=payload.id or str(uuid.uuid4()))
    user.name=payload.name
    user.email=str(payload.email).lower()
    user.role=payload.role.value
    user.project_ids=project_ids
    user.active=payload.status=='Actif'
    if payload.password:user.password_hash=passwords.hash(payload.password)
    db.add(user)
    if existing:db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
    audit(db,actor,'user_updated' if existing else 'user_created',user.id)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Adresse e-mail ou identifiant déjà utilisé.')
    return user_record(db,user)

@router.get('/{collection}')
def list_records(collection: str,user: User=Depends(current_user),db: Session=Depends(get_db),q: str=Query('',max_length=200),project: str|None=None,year: str|None=None,village: str|None=None):
    check_collection(user,collection)
    if collection=='utilisateurs':
        return [user_record(db,u) for u in db.scalars(select(User).order_by(User.name))]
    if collection not in COLLECTIONS:raise HTTPException(404,'Collection inconnue.')
    statement=scoped_records(db,user,collection)
    if q:statement=statement.where(Record.name.ilike('%'+q+'%'))
    if year:statement=statement.where(Record.year==year)
    if village:statement=statement.where(Record.village==village)
    if project:statement=statement.join(Project).where(Project.name==project)
    return [serialize(r) for r in db.scalars(statement.order_by(Record.name))]

@router.post('/{collection}',status_code=201)
def create_record(collection: str,payload: dict,user: User=Depends(current_user),db: Session=Depends(get_db)):
    if collection=='utilisateurs':return save_user(db,user,parse(UserIn,payload))
    data_in=parse(RecordIn,payload)
    project,data=validate_record(db,user,collection,data_in)
    record=Record(id=str(uuid.uuid4()),external_id=data_in.id,collection=collection,project_id=project.id,name=data_in.name,village=data_in.village,year=data_in.year,status=data_in.status,payload=data,created_by=user.id)
    db.add(record)
    audit(db,user,'record_created',f'{collection}/{record.external_id}')
    try:db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Identifiant déjà utilisé.')
    return serialize(record)

def parse(schema,payload):
    from pydantic import ValidationError
    try:return schema.model_validate(payload)
    except ValidationError as error:
        raise HTTPException(422, str(error))

@router.get('/{collection}/{record_id}')
def get_record(collection: str,record_id: str,user: User=Depends(current_user),db: Session=Depends(get_db)):
    return serialize(find_record(db,user,collection,record_id))

@router.patch('/{collection}/{record_id}')
def update_record(collection: str,record_id: str,payload: dict,user: User=Depends(current_user),db: Session=Depends(get_db)):
    if collection=='utilisateurs':
        check_collection(user,collection,write=True)
        existing=db.get(User,record_id)
        if not existing:raise HTTPException(404,'Utilisateur introuvable.')
        return save_user(db,user,parse(UserIn,payload),existing)
    check_collection(user,collection,write=True)
    record=find_record(db,user,collection,record_id)
    data_in=parse(RecordIn,{**record.payload,**payload})
    if data_in.id!=record_id:raise HTTPException(422,'L’identifiant ne peut pas être modifié.')
    project,data=validate_record(db,user,collection,data_in)
    record.project_id=project.id
    record.name=data_in.name
    record.village=data_in.village
    record.year=data_in.year
    record.status=data_in.status
    record.payload=data
    audit(db,user,'record_updated',f'{collection}/{record_id}')
    db.commit()
    return serialize(record)

@router.delete('/{collection}/{record_id}')
def delete_record(collection: str,record_id: str,user: User=Depends(current_user),db: Session=Depends(get_db)):
    check_collection(user,collection,write=True)
    if collection=='utilisateurs':
        target=db.get(User,record_id)
        if not target:raise HTTPException(404,'Utilisateur introuvable.')
        if target.id==user.id:raise HTTPException(409,'Votre propre compte ne peut pas être supprimé.')
        if target.role=='SUPER_ADMIN' and target.active:
            count=db.scalar(select(func.count()).select_from(User).where(User.role=='SUPER_ADMIN',User.active.is_(True)))
            if count<=1:raise HTTPException(409,'Dernier administrateur actif.')
        # Désactivation conserve la traçabilité des visites et consentements.
        target.active=False
        db.execute(delete(AuthSession).where(AuthSession.user_id==target.id))
    else:
        record=find_record(db,user,collection,record_id)
        if collection=='producteurs':
            linked=db.scalars(select(Record).where(Record.collection.in_(['parcelles','productions']))).all()
            if any(r.payload.get('producerId')==record_id for r in linked):
                raise HTTPException(409,'Ce producteur possède des parcelles ou productions liées. Archivez son dossier.')
        db.delete(record)
    audit(db,user,'record_deleted',f'{collection}/{record_id}')
    db.commit()
    return {'message':'Dossier supprimé.' if collection!='utilisateurs' else 'Compte désactivé.'}
