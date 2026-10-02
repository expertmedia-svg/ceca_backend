import json
import uuid
from sqlalchemy import select
from .config import ROOT,settings
from .db import SessionLocal
from .models import Project,Record,Content

def seed():
    if settings.environment=='production' or not settings.seed_work_data:
        raise RuntimeError('Les données de travail nécessitent SEED_WORK_DATA=true hors production.')
    data=json.loads((ROOT/'work-data.json').read_text(encoding='utf-8'))
    with SessionLocal() as db:
        for p in data['projects']:
            if not db.get(Project,p['id']):db.add(Project(id=p['id'],slug=p['slug'],name=p['name'],published=True,payload={k:v for k,v in p.items() if k not in ['id','slug','name']}))
        db.flush()
        for collection,rows in data['records'].items():
            if collection=='utilisateurs':continue
            for row in rows:
                if db.scalar(select(Record).where(Record.collection==collection,Record.external_id==row['id'])):continue
                project=db.scalar(select(Project).where(Project.name==row['project']))
                db.add(Record(id=str(uuid.uuid4()),external_id=row['id'],collection=collection,project_id=project.id,name=row['name'],year=row['year'],village=row['village'],status=row['status'],payload=row))
        for kind,items in [('zone',data['zones']),('video',data['videos']),('document',data['documents']),('partner',[{'title':p} for p in data['partners']])]:
            for i,item in enumerate(items):
                key=f'work-{kind}-{i}'
                if not db.get(Content,key):db.add(Content(id=key,kind=kind,title=item.get('title',item.get('name','')),published=kind in {'zone','partner'},payload=item))
        db.commit()

if __name__=='__main__':seed();print('Données de travail importées. Aucun compte fictif créé.')
