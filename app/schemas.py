import math
from datetime import date
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator, field_validator

class Role(str, Enum):
    SUPER_ADMIN='SUPER_ADMIN'
    DIRECTION='DIRECTION'
    CHEF_PROJET='CHEF_PROJET'
    AGENT_TERRAIN='AGENT_TERRAIN'
    SUIVI_EVALUATION='SUIVI_EVALUATION'
    COMMUNICATION='COMMUNICATION'
    PARTENAIRE='PARTENAIRE'

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

class UserIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    role: Role
    password: str | None = Field(default=None, min_length=12, max_length=128)
    projectIds: list[str] = Field(default_factory=list, max_length=100)
    status: str = 'Actif'
    project: str = ''
    village: str = ''
    year: str = '2026'

class RecordIn(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    name: str = Field(min_length=1, max_length=200)
    project: str = Field(min_length=1, max_length=200)
    village: str = Field(min_length=1, max_length=150)
    year: str = Field(pattern=r'^20\d{2}$')
    status: str = Field(pattern=r'^(Actif|À vérifier|Archivé)$')

    @model_validator(mode='after')
    def validate_extras(self):
        for key, value in (self.__pydantic_extra__ or {}).items():
            if not isinstance(value, (str, int, float, bool)) or len(key)>80:
                raise ValueError('Les champs supplémentaires doivent être des valeurs simples.')
            if isinstance(value, str) and len(value)>4000:
                raise ValueError('Champ trop long.')
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError('Nombre invalide.')
            if key in ['surface','production','quantity','members','income','expenses','sales','financingNeed'] and (not isinstance(value,(int,float)) or isinstance(value,bool) or value<0):
                raise ValueError(f'{key} doit être un nombre positif ou nul.')
            if key in ['visit','date'] and value:
                date.fromisoformat(str(value))
            if key=='latitude' and (not isinstance(value,(int,float)) or not -90<=value<=90):
                raise ValueError('Latitude invalide.')
            if key=='longitude' and (not isinstance(value,(int,float)) or not -180<=value<=180):
                raise ValueError('Longitude invalide.')
        return self

class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    message: str = Field(min_length=1, max_length=10000)

class NewsletterIn(BaseModel):
    email: EmailStr

class ReportIn(BaseModel):
    project: str = Field(min_length=1, max_length=200)
    period: str = Field(pattern=r'^20\d{2}$')
    zone: str = Field(default='Toutes les zones', max_length=150)
    indicators: list[str] = Field(min_length=1, max_length=6)

    @field_validator('indicators')
    @classmethod
    def indicators_valid(cls, values):
        allowed={'Producteurs','Ménages','Superficie','Femmes','Production','Transformateurs'}
        if not set(values)<=allowed or len(values)!=len(set(values)):
            raise ValueError('Indicateurs invalides ou dupliqués.')
        return values

class ConsentIn(BaseModel):
    accepted: bool
    purpose: str = Field(min_length=3, max_length=200)

class ContentIn(BaseModel):
    id: str | None = None
    kind: str = Field(pattern=r'^(video|document|zone|partner|testimonial)$')
    title: str = Field(min_length=1, max_length=200)
    published: bool = False
    payload: dict = Field(default_factory=dict)
