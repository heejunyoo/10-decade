import os

# 🚨 macOS Mutex Crash Prevention (Disable HuggingFace Tokenizers Parallelism)
# Must be set BEFORE any other imports load transformers/tokenizers
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Services & Database
from services import tasks
import preload_models
import models
from database import engine
from services import logger
from services import config as config_service 

# Initialize Logging
logger.setup_logging()

# Routers
from routers import timeline, auth, admin, map, capsule, people, memories, chat, faces

# Config Service (Inject into Templates)
from services.config import config

# Patch all routers' template environments to include 'get_config'
# This avoids modifying every router file to import a shared templates instance.
for router_module in [timeline, auth, admin, map, capsule, people, memories, chat]:
    if hasattr(router_module, "templates"):
        router_module.templates.env.globals["get_config"] = config.get

# HEIC support pre-registration
import pillow_heif
pillow_heif.register_heif_opener()

# Application Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Launch AI Worker (Queue Processor)
    tasks.start_worker()
    
    # Startup: Preload AI Models (Blocking Main Thread) -> Safer for macOS
    if config.get("ai_provider") == "local":
        print("⏳ Preloading AI Models (Main Thread)...")
        preload_models.preload()
    
    yield
    # Shutdown logic if needed

# Create Database Tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="The Decade Journey", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Middleware: Global Auth Check
PROFILE_COOKIE_NAME = "decade_journey_profile"

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Public routes that don't pass auth (static files, favicon)
    # Note: /select-profile and /set-profile must be accessible
    public_routes = ["/static", "/favicon.ico", "/set-profile", "/select-profile"]
    
    # Check if path starts with any public route
    is_public = any(request.url.path.startswith(route) for route in public_routes)
    
    if is_public:
        return await call_next(request)
    
    # Check Profile Cookie (Who is this?)
    # API calls: Return 401 if missing profile
    # Page navigation: Redirect to /select-profile
    profile = request.cookies.get(PROFILE_COOKIE_NAME)
    is_api_call = request.url.path.startswith(("/api", "/delete", "/add", "/update"))
    
    if not profile:
        if is_api_call:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return RedirectResponse("/select-profile", status_code=303)
        
    response = await call_next(request)
    return response

# Include Routers
# Ordering matters: specific routes first
app.include_router(timeline.router)
app.include_router(memories.router)
app.include_router(chat.router)
app.include_router(faces.router)
app.include_router(people.router)
app.include_router(map.router)
# Admin/Manage Routes
app.include_router(admin.router)
app.include_router(capsule.router)
app.include_router(auth.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
