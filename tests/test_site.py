from io import BytesIO
from pathlib import Path
from PIL import Image
from conftest import login

def page(**changes):
    return {'title':'Titre institutionnel','subtitle':'Sous-titre','text':'Texte réel','blocks':[{'title':'Nos engagements','text':'Avec les communautés','photo':'','link':'/actions','linkLabel':'Découvrir'}],**changes}

def test_site_page_publication_persistence_and_validation(client):
    assert client.get('/impact/site-pages').status_code==401
    login(client)
    assert client.put('/impact/site-pages/accueil',json=page()).status_code==200
    assert 'accueil' not in client.get('/public/catalog').json()['pages']
    assert client.get('/impact/site-pages').json()['accueil']['title']=='Titre institutionnel'
    saved=client.get('/impact/site-pages').json()['accueil']
    assert client.put('/impact/site-pages/accueil',json={**saved,'title':'Titre modifié'}).status_code==200
    assert client.put('/impact/site-pages/accueil',json=page(published=True)).status_code==200
    assert client.get('/public/catalog').json()['pages']['accueil']['blocks'][0]['text']=='Avec les communautés'
    assert client.put('/impact/site-pages/accueil',json=page(photo='javascript:alert(1)')).status_code==422
    assert client.put('/impact/site-pages/accueil',json=page(blocks=[{'link':'//hostile.example'}])).status_code==422
    assert client.put('/impact/site-pages/inconnue',json=page()).status_code==422
    assert client.put('/impact/site-pages/accueil',json=page()).status_code==200
    assert 'accueil' not in client.get('/public/catalog').json()['pages']

def test_site_editor_roles_and_csrf(client):
    for role in ['AGENT_TERRAIN','PARTENAIRE','CHEF_PROJET','SUIVI_EVALUATION']:
        login(client,role)
        assert client.get('/impact/site-pages').status_code==403
        assert client.put('/impact/site-pages/actions',json=page()).status_code==403
    login(client,'COMMUNICATION')
    assert client.put('/impact/site-pages/actions',json=page()).status_code==200
    client.headers.pop('X-CSRF-Token')
    assert client.put('/impact/site-pages/actions',json=page()).status_code==403

def test_site_images_uploaded_and_served_without_source_metadata(client,monkeypatch,tmp_path):
    from app.routers import site
    monkeypatch.setattr(site,'UPLOADS',tmp_path)
    login(client)
    assert client.post('/impact/media',content=b'not an image').status_code==422
    image=BytesIO();Image.new('RGB',(20,20),'green').save(image,'PNG')
    response=client.post('/impact/media',content=image.getvalue(),headers={'Content-Type':'image/png'})
    assert response.status_code==201,response.text
    filename=Path(response.json()['url']).name
    with Image.open(tmp_path/filename) as saved:
        assert saved.format=='WEBP' and saved.size==(20,20) and not saved.getexif()
    assert client.put('/impact/site-pages/accueil',json=page(photo=response.json()['url'],published=True)).status_code==200
    login(client,'PARTENAIRE')
    assert client.post('/impact/media',content=image.getvalue()).status_code==403
