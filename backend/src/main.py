from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.src.core.config import settings
from backend.src.core.exceptions import rfc7807_exception_handler
from backend.src.core.otel import setup_otel
from backend.src.contexts.auth.router import router as auth_router
from backend.src.contexts.inventory.router import router as inventory_router
from backend.src.contexts.asset.router import router as asset_router
from backend.src.contexts.dashboard.router import router as dashboard_router
from backend.src.contexts.license.router import router as license_router
from backend.src.contexts.itsm.router import router as itsm_router
from backend.src.contexts.remote.router import router as remote_router
from backend.src.contexts.remote.webhooks import router as webhook_router
from backend.src.contexts.procurement.router import router as procurement_router
from backend.src.contexts.workflow.router import router as workflow_router
from backend.src.contexts.notification.router import router as notification_router
from backend.src.contexts.reports.router import router as reports_router
from backend.src.contexts.reconciliation.router import router as reconciliation_router
import uuid
import time
from backend.src.core.i18n import set_language

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="3.6",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# OpenTelemetry
setup_otel(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(HTTPException, rfc7807_exception_handler)

# Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(inventory_router, prefix=settings.API_V1_STR)
app.include_router(asset_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(license_router, prefix=settings.API_V1_STR)
app.include_router(itsm_router, prefix=settings.API_V1_STR)
app.include_router(remote_router, prefix=settings.API_V1_STR)
app.include_router(webhook_router, prefix=settings.API_V1_STR)
app.include_router(procurement_router, prefix=settings.API_V1_STR)
app.include_router(workflow_router, prefix=settings.API_V1_STR)
app.include_router(notification_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(reconciliation_router, prefix=settings.API_V1_STR)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data: https:;"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.middleware("http")
async def add_process_time_and_trace_id(request: Request, call_next):
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return response

@app.middleware("http")
async def detect_language(request: Request, call_next):
    # 1. Check query param
    lang = request.query_params.get("lang")
    
    # 2. Check header
    if not lang:
        accept_lang = request.headers.get("accept-language", "")
        if accept_lang:
            # Simple parse for now: first locale
            lang = accept_lang.split(",")[0].split(";")[0].split("-")[0]
            
    # 3. Default fallback
    if not lang or lang not in ["vi", "en", "ko", "ar"]:
        lang = "vi"
        
    # Set to ContextVar
    set_language(lang)
    
    response = await call_next(request)
    response.headers["Content-Language"] = lang
    return response

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} v3.6 API"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}
