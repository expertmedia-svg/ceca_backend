from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .routers import auth, public, records, reports, dashboard, admin, map, site
from fastapi.staticfiles import StaticFiles

app=FastAPI(title='CECA-DR API',version='1.0.0',description='API séparée : comptes, dossiers, projets, rapports et contenus.',docs_url='/docs' if settings.environment!='production' else None,redoc_url=None,openapi_url='/openapi.json' if settings.environment!='production' else None)
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-CSRF-Token'],expose_headers=['Content-Disposition'])

@app.middleware('http')
async def headers_and_limits(request: Request,call_next):
    length=request.headers.get('content-length','0')
    limit=11*1024*1024 if request.url.path=='/impact/media' else 1_000_000
    if not length.isdigit() or int(length)>limit:
        return JSONResponse(status_code=413,content={'detail':'Requête trop volumineuse.'})
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    if request.url.path.startswith(('/impact','/auth','/reports')):response.headers['Cache-Control']='no-store'
    return response

# Les routes spécifiques sont déclarées avant /impact/{collection}.
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(map.router)
app.include_router(site.router)
app.include_router(reports.router)
app.include_router(records.router)
app.mount('/media',StaticFiles(directory=site.UPLOADS),name='site-media')
