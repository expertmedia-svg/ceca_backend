from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    environment: str = 'development'
    database_url: str = f'sqlite:///{(ROOT / "ceca.db").as_posix()}'
    cors_origins: str = 'http://localhost:5173,http://localhost:5174,http://localhost:4173'
    cookie_secure: bool = False
    cookie_samesite: Literal['lax','strict','none'] = 'lax'
    session_hours: int = 8
    seed_work_data: bool = False

    @property
    def origins(self) -> list[str]:
        return [s.strip().rstrip('/') for s in self.cors_origins.split(',') if s.strip()]

settings = Settings()
if settings.cookie_samesite == 'none' and not settings.cookie_secure:
    raise RuntimeError('SameSite=None nécessite COOKIE_SECURE=true.')
if settings.environment == 'production' and not settings.cookie_secure:
    raise RuntimeError('COOKIE_SECURE=true obligatoire en production.')
if settings.environment == 'production' and (settings.seed_work_data or '*' in settings.origins):
    raise RuntimeError('Données de travail et CORS * interdits en production.')
