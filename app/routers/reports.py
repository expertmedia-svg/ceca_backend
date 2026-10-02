import uuid
import base64
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Consent, now
from ..schemas import ReportIn, ConsentIn
from ..security import current_user, audit
from ..reporting import calculate, pdf_bytes, excel_bytes
from .records import find_record
from sqlalchemy import select

router=APIRouter(tags=['Rapports et consentements'])

@router.post('/reports')
def report(payload: ReportIn,user: User=Depends(current_user),db: Session=Depends(get_db)):
    result=calculate(db,user,payload);audit(db,user,'report_generated',payload.project);db.commit();return result

@router.post('/reports/export/{format}')
def export(format: str,payload: ReportIn,transport: Literal['binary','json']='binary',user: User=Depends(current_user),db: Session=Depends(get_db)):
    result=calculate(db,user,payload)
    if format=='pdf':body=pdf_bytes(result);mime='application/pdf'
    elif format=='xlsx':body=excel_bytes(result);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:raise HTTPException(404,'Format inconnu.')
    audit(db,user,'report_exported',payload.project+'/'+format);db.commit()
    if transport=='json':return {'content':base64.b64encode(body).decode('ascii'),'mediaType':mime}
    return Response(content=body,media_type=mime,headers={'Content-Disposition':f'attachment; filename="ceca-impact-{payload.period}.{format}"','Cache-Control':'no-store'})

@router.post('/impact/producteurs/{record_id}/consent')
def consent(record_id: str,payload: ConsentIn,user: User=Depends(current_user),db: Session=Depends(get_db)):
    record=find_record(db,user,'producteurs',record_id)
    db.add(Consent(id=str(uuid.uuid4()),record_id=record.id,user_id=user.id,purpose=payload.purpose,accepted=payload.accepted))
    audit(db,user,'consent_recorded',record_id);db.commit()
    return {'accepted':payload.accepted,'message':'Consentement enregistré en base.'}

@router.get('/impact/producteurs/{record_id}/economic.pdf')
def economic_export(record_id: str,transport: Literal['binary','json']='binary',user: User=Depends(current_user),db: Session=Depends(get_db)):
    record=find_record(db,user,'producteurs',record_id)
    consent=db.scalar(select(Consent).where(Consent.record_id==record.id,Consent.user_id==user.id).order_by(Consent.created_at.desc()))
    if not consent or not consent.accepted:raise HTTPException(403,'Consentement enregistré requis pour exporter ce dossier.')
    values=record.payload
    report={'title':'Dossier économique','project':record.name,'period':record.year,'zone':record.village,'source':'Données déclarées. Consentement tracé en base. Aucune décision de crédit. Aucun partage externe.','generatedAt':now().isoformat(),'rows':[{'indicator':label,'value':values[key],'unit':unit} for label,key,unit in [('Superficie','surface','ha'),('Production','production','kg'),('Revenus déclarés','income','FCFA'),('Charges','expenses','FCFA'),('Ventes','sales','FCFA'),('Besoin financier','financingNeed','FCFA')] if key in values]}
    audit(db,user,'economic_exported',record_id);db.commit()
    body=pdf_bytes(report)
    if transport=='json':return {'content':base64.b64encode(body).decode('ascii'),'mediaType':'application/pdf'}
    return Response(body,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="dossier-economique.pdf"','Cache-Control':'no-store'})
