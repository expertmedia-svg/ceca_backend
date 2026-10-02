import uuid
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Project, Content, Contact, Newsletter, Record, now
from ..schemas import ContactIn, NewsletterIn
from ..config import settings
from ..security import check_origin

router=APIRouter(tags=['Site public'])
CENTROIDS={'Boussé':(12.661,-1.893),'Toéghin':(12.78,-1.79),'Koudougou':(12.252,-2.362)}
PROJECT_FIELDS={'location','status','period','domains','beneficiaries','partners','photo'}
CONTENT_FIELDS={'category','year','size','photo','url','commune','duration','theme','project','beneficiaryConsent'}

def public_project(project: Project):
    return {'id':project.id,'slug':project.slug,'name':project.name,**{k:v for k,v in project.payload.items() if k in PROJECT_FIELDS}}

def public_content(content: Content):
    return {'id':content.id,'title':content.title,**{k:v for k,v in content.payload.items() if k in CONTENT_FIELDS}}

@router.get('/health')
def health(db: Session=Depends(get_db)):
    db.execute(select(1))
    return {'status':'ok','service':'CECA-DR API','environment':settings.environment,'workData':settings.seed_work_data}

@router.get('/projects')
def projects(db: Session=Depends(get_db)):
    return [public_project(p) for p in db.scalars(select(Project).where(Project.published.is_(True)))]

@router.get('/projects/{slug}')
def project(slug: str,db: Session=Depends(get_db)):
    result=db.scalar(select(Project).where(Project.slug==slug,Project.published.is_(True)))
    if not result:raise HTTPException(404,'Projet non publié.')
    return public_project(result)

@router.get('/public/zones')
def zones(db: Session=Depends(get_db)):
    result=[]
    for item in db.scalars(select(Content).where(Content.kind=='zone',Content.published.is_(True))):
        if item.title not in CENTROIDS:continue
        latitude,longitude=CENTROIDS[item.title]
        payload=item.payload
        result.append({'id':item.id,'name':item.title,'lat':latitude,'lon':longitude,'beneficiaries':int(payload.get('beneficiaries',0)),'project':payload.get('project',''),'year':payload.get('year',''),'type':payload.get('type',''),'results':payload.get('results',''),'precision':'commune'})
    return result

@router.get('/public/catalog')
def catalog(db: Session=Depends(get_db)):
    contents=db.scalars(select(Content).where(Content.published.is_(True),Content.kind!='zone')).all()
    public_projects=projects(db);ids=[p['id'] for p in public_projects]
    records=db.scalars(select(Record).where(Record.project_id.in_(ids),Record.status!='Archivé')).all()
    producers=[r for r in records if r.collection=='producteurs'];locations=zones(db)
    women=round(100*sum(r.payload.get('sex')=='Femme' for r in producers)/len(producers),1) if producers else 0
    kpis=[{'value':str(len(producers)),'label':'Producteurs accompagnés'},{'value':str(women)+' %','label':'Femmes'},{'value':str(sum(r.collection=='menages' for r in records)),'label':'Ménages suivis'},{'value':str(round(sum(float(r.payload.get('surface',0)) for r in producers),2))+' ha','label':'Superficie accompagnée'},{'value':str(sum(r.collection=='transformateurs' for r in records)),'label':'Transformateurs'},{'value':str(len(set(z['name'] for z in locations))),'label':'Communes'}]
    return {'projects':public_projects,'zones':locations,'videos':[public_content(c) for c in contents if c.kind=='video'],'documents':[public_content(c) for c in contents if c.kind=='document'],'partners':[c.title for c in contents if c.kind=='partner'],'kpis':kpis,'source':'Données de travail non validées' if settings.seed_work_data else 'Contenus publiés par le CECA-DR'}

@router.post('/contact',status_code=201)
def contact(payload: ContactIn,request: Request,db: Session=Depends(get_db)):
    check_origin(request)
    count=db.scalar(select(func.count()).select_from(Contact).where(Contact.email==str(payload.email).lower(),Contact.created_at>=now()-timedelta(hours=1)))
    if count>=5:raise HTTPException(429,'Trop de demandes pour cette adresse. Réessayez plus tard.')
    record=Contact(id=str(uuid.uuid4()),name=payload.name,email=str(payload.email).lower(),message=payload.message)
    db.add(record);db.commit()
    return {'id':record.id,'message':'Demande enregistrée. L’équipe pourra la consulter dans Impact.'}

@router.post('/newsletter')
def newsletter(payload: NewsletterIn,request: Request,db: Session=Depends(get_db)):
    check_origin(request)
    email=str(payload.email).lower()
    if not db.scalar(select(Newsletter).where(Newsletter.email==email)):
        db.add(Newsletter(id=str(uuid.uuid4()),email=email));db.commit()
    return {'message':'Adresse enregistrée. Aucun message automatique envoyé.'}
