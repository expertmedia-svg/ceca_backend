from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Record, Project
from ..security import current_user, GLOBAL_ROLES, check_project
from ..config import settings
from .public import zones,public_project

router=APIRouter(prefix='/impact',tags=['Tableau de bord'])

@router.get('/dashboard')
def dashboard(project: str='Tous les projets',period: str='2026',user: User=Depends(current_user),db: Session=Depends(get_db)):
    if user.role=='COMMUNICATION':return {'kpis':[],'chart':[],'activities':[],'visits':[],'alerts':0,'projects':[],'zones':[],'source':'Accès communication : consulter la capitalisation et les contenus publics.'}
    statement=select(Record).where(Record.year==period,Record.status!='Archivé')
    if user.role not in GLOBAL_ROLES:statement=statement.where(Record.project_id.in_(user.project_ids))
    if project!='Tous les projets':
        target=db.scalar(select(Project).where(Project.name==project))
        if not target:raise HTTPException(404,'Projet inconnu.')
        check_project(user,target.id);statement=statement.where(Record.project_id==target.id)
    records=db.scalars(statement).all();producers=[r for r in records if r.collection=='producteurs']
    women=round(100*len([r for r in producers if r.payload.get('sex')=='Femme'])/len(producers),1) if producers else 0
    kpis=[{'label':'Producteurs','value':len(producers)},{'label':'Ménages','value':sum(r.collection=='menages' for r in records)},{'label':'Transformateurs','value':sum(r.collection=='transformateurs' for r in records)},{'label':'Parcelles','value':sum(r.collection=='parcelles' for r in records)},{'label':'Superficie (ha)','value':round(sum(float(r.payload.get('surface',0)) for r in producers),2)},{'label':'Production (kg)','value':sum(float(r.payload.get('production',0)) for r in producers)},{'label':'Femmes (%)','value':women}]
    activities={};chart=[];running=0
    for record in producers:
        activity=record.payload.get('activity','Non renseignée');activities[activity]=activities.get(activity,0)+1
    for month,label in enumerate(['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Août','Sep','Oct','Nov','Déc'],1):
        matching=[r for r in producers if str(r.payload.get('visit',''))[5:7]==f'{month:02}'];running+=len(matching)
        chart.append({'month':label,'beneficiaires':running,'production':sum(float(r.payload.get('production',0)) for r in matching)})
    project_rows=db.scalars(select(Project)).all()
    accessible=[p for p in project_rows if (user.role in GLOBAL_ROLES or p.id in user.project_ids) and (project=='Tous les projets' or p.name==project)]
    ids={p.id for p in accessible}
    return {'kpis':kpis,'chart':chart,'women':women,'activities':[{'name':name,'percentage':round(100*n/len(producers),1)} for name,n in activities.items()],'visits':[] if user.role=='PARTENAIRE' else [r.payload for r in sorted(producers,key=lambda r:r.payload.get('visit',''),reverse=True)[:3]],'alerts':sum(r.status=='À vérifier' for r in records),'projects':[public_project(p) for p in accessible],'zones':[z for z in zones(db) if z['project'] in ids and z['year']==period],'source':'Données de travail non validées' if settings.seed_work_data else 'Données enregistrées en base'}
