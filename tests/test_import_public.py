import json
from sqlalchemy import select,func,delete
from app.import_public import import_content,DATA
from app.models import Content,Project,Record
from app.routers.site import SitePage

def test_public_import_valid_idempotent_preserves_editor_changes(database):
    data=json.loads(DATA.read_text(encoding='utf-8'))
    assert len(data['pages'])==8
    for payload in data['pages'].values():SitePage.model_validate(payload)
    with database() as db:
        before=db.scalar(select(func.count()).select_from(Record))
        counts=import_content(db)
        assert counts['pages']==8 and counts['projects']==3
        assert db.scalar(select(func.count()).select_from(Record))==before
        content=db.get(Content,'sitepage-accueil');content.title='Titre personnalisé';db.commit()
        assert import_content(db)=={'pages':0,'projects':0,'contents':0}
        assert db.get(Content,'sitepage-accueil').title=='Titre personnalisé'

def test_reference_metrics_not_mixed_with_current_records(client,database):
    with database() as db:import_content(db)
    assert client.get('/public/catalog').json()['kpis'][0]['label']=='Producteurs accompagnés'
    with database() as db:db.execute(delete(Record));db.commit()
    catalog=client.get('/public/catalog').json()
    assert catalog['kpis'][0]=={'value':'30','label':'Femmes · Boussé 2022'}
    assert 'historiques' in catalog['source']
    assert any(p['status']=='Documenté' for p in catalog['projects'])
