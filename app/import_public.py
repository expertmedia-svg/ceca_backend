"""Importer des contenus publics sourcés, sans créer de dossiers individuels fictifs."""
import json
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal
from .models import Content, Project

DATA=Path(__file__).resolve().with_name('public-content.json')

def import_content(db):
    data=json.loads(DATA.read_text(encoding='utf-8'))
    counts={'pages':0,'projects':0,'contents':0}
    for slug,payload in data['pages'].items():
        key='sitepage-'+slug
        if db.get(Content,key):continue
        payload=dict(payload);title=payload.pop('title')
        db.add(Content(id=key,kind='sitepage',title=title,published=True,payload={**payload,'slug':slug}))
        counts['pages']+=1
    for payload in data['projects']:
        if db.scalar(select(Project).where((Project.id==payload['id'])|(Project.slug==payload['slug'])|(Project.name==payload['name']))):continue
        db.add(Project(id=payload['id'],slug=payload['slug'],name=payload['name'],published=True,payload={k:v for k,v in payload.items() if k not in {'id','slug','name'}}))
        counts['projects']+=1
    for item in data['contents']:
        if db.get(Content,item['id']):continue
        db.add(Content(**item));counts['contents']+=1
    db.commit()
    return counts

if __name__=='__main__':
    with SessionLocal() as db:print('Contenus publics ajoutés :',import_content(db),'— contenus existants conservés.')
