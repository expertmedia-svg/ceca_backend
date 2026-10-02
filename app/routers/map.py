from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..security import current_user,check_collection
from .records import scoped_records
from .public import zones

router=APIRouter(prefix='/impact',tags=['Cartographie privée'])

@router.get('/map')
def map_data(layer: str='Projets',project: str='',commune: str='',year: str='',sex: str='',activity: str='',user: User=Depends(current_user),db: Session=Depends(get_db)):
    layers={'Producteurs':'producteurs','Ménages':'menages','Transformateurs':'transformateurs','Parcelles':'parcelles','Organisations':'organisations'}
    if layer=='Projets':
        from ..security import GLOBAL_ROLES
        return [z for z in zones(db) if (user.role in GLOBAL_ROLES or z['project'] in user.project_ids) and (not project or z['project']==project) and (not commune or z['name']==commune) and (not year or z['year']==year)]
    if layer=='Infrastructures':return []
    if layer not in layers:raise HTTPException(422,'Couche inconnue.')
    collection=layers[layer];check_collection(user,collection)
    result=[]
    for r in db.scalars(scoped_records(db,user,collection)):
        p=r.payload;lat=p.get('latitude');lon=p.get('longitude')
        if (project and r.project_id!=project) or (commune and r.village!=commune) or (year and r.year!=year) or (sex and p.get('sex')!=sex) or (activity and p.get('activity')!=activity):continue
        if isinstance(lat,(int,float)) and isinstance(lon,(int,float)) and -90<=lat<=90 and -180<=lon<=180:
            result.append({'id':r.external_id,'name':r.name,'lat':lat,'lon':lon,'beneficiaries':1,'project':r.project_id,'year':r.year,'type':layer,'results':r.status})
    return result
