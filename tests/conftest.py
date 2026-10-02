import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.db import Base,get_db
from app.main import app
from app.models import User,Project,Record
from app.security import passwords

@pytest.fixture
def database():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as db:
        for pid in ['p1','p2']:db.add(Project(id=pid,name='Projet '+pid,slug='projet-'+pid,published=True,payload={'location':'Boussé','status':'En cours'}))
        for role in ['SUPER_ADMIN','DIRECTION','CHEF_PROJET','AGENT_TERRAIN','SUIVI_EVALUATION','COMMUNICATION','PARTENAIRE']:
            db.add(User(id=role,email=role.lower()+'@example.org',name=role,password_hash=passwords.hash('MotDePasse-Test-2026'),role=role,project_ids=['p1'],active=True))
        db.flush()
        for i in range(3):
            pid='p1' if i<2 else 'p2'
            payload={'id':f'PR-{i}','name':f'Producteur {i}','project':'Projet '+pid,'village':'Boussé' if i%2==0 else 'Toéghin','year':'2026','status':'Actif','sex':'Femme' if i==0 else 'Homme','activity':'Maraîchage','surface':i+1,'production':100*(i+1),'visit':'2026-09-18','latitude':12.123456,'longitude':-1.123456}
            db.add(Record(id=f'internal-{i}',external_id=payload['id'],collection='producteurs',project_id=pid,name=payload['name'],village=payload['village'],year='2026',status='Actif',payload=payload))
        db.commit()
    def override():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=override
    yield factory
    app.dependency_overrides.clear();engine.dispose()

@pytest.fixture
def client(database):
    with TestClient(app) as client:yield client

def login(client,role='SUPER_ADMIN'):
    response=client.post('/auth/login',json={'email':role.lower()+'@example.org','password':'MotDePasse-Test-2026','role':'SUPER_ADMIN'})
    assert response.status_code==200,response.text
    client.headers['X-CSRF-Token']=response.json()['csrfToken']
    return response
