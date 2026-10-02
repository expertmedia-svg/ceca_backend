import uuid
from io import BytesIO
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from PIL import Image, ImageOps, UnidentifiedImageError
from ..config import ROOT
from ..db import get_db
from ..models import Content, User
from ..security import current_user, audit
from .admin import editor

router=APIRouter(tags=['Administration du site'])
PageSlug=Literal['accueil','qui-sommes-nous','actions','projets','notre-impact','capitalisation','ressources','actualites']
UPLOADS=ROOT/'uploads'
UPLOADS.mkdir(exist_ok=True)

class Block(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str=Field(default='',max_length=200)
    text: str=Field(default='',max_length=12000)
    photo: str=Field(default='',max_length=2000)
    link: str=Field(default='',max_length=2000)
    linkLabel: str=Field(default='',max_length=100)

    @field_validator('photo','link')
    @classmethod
    def safe_url(cls,value):
        if value and not (value.startswith('https://') or (value.startswith('/') and not value.startswith('//'))):
            raise ValueError('Lien HTTPS ou chemin interne requis.')
        return value

class SitePage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str=Field(min_length=1,max_length=200)
    subtitle: str=Field(default='',max_length=1000)
    text: str=Field(default='',max_length=20000)
    photo: str=Field(default='',max_length=2000)
    eyebrow: str=Field(default='',max_length=150)
    buttonLabel: str=Field(default='',max_length=100)
    buttonLink: str=Field(default='',max_length=2000)
    experience: str=Field(default='',max_length=40)
    blocks: list[Block]=Field(default_factory=list,max_length=30)
    published: bool=False

    @field_validator('photo','buttonLink')
    @classmethod
    def safe_url(cls,value):return Block.safe_url(value)

def public_pages(db: Session):
    return {r.payload['slug']:{**r.payload,'title':r.title} for r in db.scalars(select(Content).where(Content.kind=='sitepage',Content.published.is_(True)))}

@router.get('/impact/site-pages')
def pages(user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    return {r.payload['slug']:{**{k:v for k,v in r.payload.items() if k!='slug'},'title':r.title,'published':r.published} for r in db.scalars(select(Content).where(Content.kind=='sitepage'))}

@router.put('/impact/site-pages/{slug}')
def save_page(slug: PageSlug,payload: SitePage,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    content=db.get(Content,'sitepage-'+slug) or Content(id='sitepage-'+slug,kind='sitepage')
    content.title=payload.title;content.published=payload.published
    content.payload={**payload.model_dump(exclude={'title','published'}),'slug':slug}
    db.add(content);audit(db,user,'site_page_saved',slug);db.commit()
    return payload.model_dump()

@router.post('/impact/media',status_code=201)
async def upload(request: Request,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>10*1024*1024:raise HTTPException(413,'Image limitée à 10 Mo.')
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {'JPEG','PNG','WEBP'}:raise ValueError('Format non autorisé')
            if image.width*image.height>16_000_000:raise ValueError('Image trop grande')
            image.load();converted=ImageOps.exif_transpose(image).convert('RGB')
            converted.thumbnail((2400,2400))
            filename=str(uuid.uuid4())+'.webp'
            converted.save(UPLOADS/filename,'WEBP',quality=88)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        raise HTTPException(422,'Image JPG, PNG ou WebP valide requise (16 millions de pixels maximum).')
    audit(db,user,'site_media_uploaded',filename);db.commit()
    return {'url':'/media/'+filename}

@router.delete('/impact/site-pages/{slug}')
def reset_page(slug: PageSlug,user: User=Depends(current_user),db: Session=Depends(get_db)):
    editor(user)
    content=db.get(Content,'sitepage-'+slug)
    if content:db.delete(content)
    audit(db,user,'site_page_reset',slug);db.commit()
    return {'message':'Version personnalisée retirée.'}
