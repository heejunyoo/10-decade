from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, BackgroundTasks, Query, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import os
import shutil
import uuid 
from datetime import date as date_cls

from database import get_db
import models
from services.media import process_upload_task
from services.logger import get_logger
from services.faces import reindex_faces, STATUS_FILE
import threading

logger = get_logger("admin")

router = APIRouter()

@router.post("/api/admin/reset-faces")
def reset_faces(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Triggers a FULL Hard Reset of Face Data.
    Wipes 'faces' and 'people' tables and re-indexes everything using InsightFace.
    """
    # Check if already running
    if os.path.exists(STATUS_FILE):
        return JSONResponse({"status": "error", "message": "Indexing already in progress"}, status_code=400)

    # Run in background to avoid timeout
    background_tasks.add_task(reindex_faces)
    
    return {"status": "success", "message": "Face data wipe and re-indexing started."}

templates = Jinja2Templates(directory="templates")

@router.get("/manage/people")
def manage_people_page(request: Request, db: Session = Depends(get_db)):
    people = db.query(models.Person).all()
    people.sort(key=lambda p: len(p.faces), reverse=True)
    return templates.TemplateResponse("manage_people.html", {
        "request": request, 
        "people": people
    })

@router.get("/manage/people/unknown")
def manage_unknown_faces_page(request: Request, db: Session = Depends(get_db)):
    """
    Page to manage/merge unknown face clusters.
    """
    # Fetch all people for the "Merge Target" dropdown
    people = db.query(models.Person).order_by(models.Person.name).all()
    
    return templates.TemplateResponse("manage_people_unknown.html", {
        "request": request,
        "people": people
    })

@router.get("/add")
def add_event_form(request: Request):
    return templates.TemplateResponse("add_event.html", {"request": request})

@router.post("/add")
async def create_event(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(None),
    title: str = Form(None),
    date_form: str = Form(None, alias="date"),
    description: str = Form(None),
    tags: str = Form(None),
    db: Session = Depends(get_db)
):
    print(f"DEBUG: /add called. Files: {len(files) if files else 0}")
    
    try:
        temp_dir = "static/temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Metadata to pass to background task
        metadata = {
            "title": title,
            "date": date_form,
            "description": description,
            "tags": tags
        }
        
        count = 0
        if files:
            for file in files:
                if file.filename:
                    # Save to temp location with unique name to prevent collisions
                    ext = os.path.splitext(file.filename)[1]
                    temp_filename = f"{uuid.uuid4()}{ext}"
                    temp_path = os.path.join(temp_dir, temp_filename)
                    
                    with open(temp_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    
                    # Queue the task
                    # We pass original filename to preserve user's naming if needed (though we rename usually)
                    background_tasks.add_task(
                        process_upload_task, 
                        temp_path, 
                        file.filename, 
                        metadata
                    )
                    count += 1
        
        # Handle Text-Only Events (Synchronous)
        if count == 0 and (title or description):
            event_date = date_form or date_cls.today().isoformat()
            new_event = models.TimelineEvent(
                title=title,
                date=event_date,
                description=description,
                image_url=None,
                tags=tags,
                media_type="text"
            )
            db.add(new_event)
            db.commit()
            print("📝 Created text-only event")

        msg = "업로드가 시작되었습니다. 잠시 후 갤러리에 표시됩니다." if count > 0 else "기록이 저장되었습니다."
        return templates.TemplateResponse("add_event.html", {"request": request, "msg": msg})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"detail": f"Internal Server Error: {str(e)}"}, status_code=500)

@router.get("/manage")
def manage_page(
    request: Request, 
    page: int = Query(1, ge=1), 
    q: str = Query(None),
    db: Session = Depends(get_db)
):
    limit = 20
    offset = (page - 1) * limit
    
    query = db.query(models.TimelineEvent).order_by(models.TimelineEvent.date.desc())
    
    if q:
        search_term = f"%{q}%"
        # Use bitwise OR | for SQLAlchemy OR condition which is cleaner than importing or_
        query = query.filter(
            (models.TimelineEvent.title.like(search_term)) | 
            (models.TimelineEvent.description.like(search_term)) |
            (models.TimelineEvent.tags.like(search_term))
        )
    
    total_count = query.count()
    # Simple ceiling division
    total_pages = (total_count + limit - 1) // limit
    
    events = query.offset(offset).limit(limit).all()
        
    return templates.TemplateResponse("manage.html", {
        "request": request, 
        "events": events,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "q": q or ""
    })

@router.get("/api/manage-events")
def get_manage_events(
    request: Request, 
    page: int = Query(1, ge=1), 
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit
    events = db.query(models.TimelineEvent)\
        .order_by(models.TimelineEvent.date.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()
        
    context = {
        "request": request, 
        "events": events,
        "next_page": page + 1 if len(events) == limit else None,
        "limit": limit
    }
    return templates.TemplateResponse("manage_row.html", context)

@router.get("/edit/{event_id}")
def edit_event_form(request: Request, event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
    if not event:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("edit_event.html", {"request": request, "event": event})

@router.get("/manage/logs")
def view_system_logs(request: Request, db: Session = Depends(get_db)):
    """
    Dashboard for viewing system logs.
    """
    logs = db.query(models.SystemLog).order_by(models.SystemLog.created_at.desc()).limit(100).all()
    
    total_count = db.query(models.SystemLog).count()
    error_count = db.query(models.SystemLog).filter(models.SystemLog.level == "ERROR").count()
    
    return templates.TemplateResponse("admin_logs.html", {
        "request": request,
        "logs": logs,
        "total_count": total_count,
        "error_count": error_count
    })

@router.post("/update/{event_id}")
async def update_event(
    request: Request,
    event_id: int,
    title: str = Form(None),
    date: str = Form(None),
    description: str = Form(None),
    tags: str = Form(None),
    summary: str = Form(None),
    db: Session = Depends(get_db)
):
    event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
    if not event:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    
    # Track if RAG update is needed
    rag_update_needed = False
    
    if title is not None: event.title = title
    if date: event.date = date
    if description is not None: event.description = description
    if tags is not None: event.tags = tags
    
    # Update AI Summary
    if summary is not None and summary != event.summary:
        event.summary = summary
        rag_update_needed = True
    
    db.commit()
    
    # Re-index if summary changed
    if rag_update_needed:
        try:
            from services.rag import memory_vector_store
            print(f"🔄 Re-indexing Event {event_id} due to summary update...")
            memory_vector_store.add_events([event])
        except Exception as e:
            print(f"❌ Failed to re-index event {event_id}: {e}")
            
    return RedirectResponse(url="/manage", status_code=303)

@router.post("/delete-all")
def delete_all_events(request: Request, db: Session = Depends(get_db)):
    try:
        db.query(models.TimelineEvent).delete()
        db.execute(text("DELETE FROM sqlite_sequence WHERE name='timeline_events'"))
        db.commit()
    except Exception as e:
        print(f"Error deleting from DB: {e}")
        db.rollback()

    upload_dir = "static/uploads"
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

    return RedirectResponse(url="/manage", status_code=303)

@router.post("/delete/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    print(f"🗑️ DELETE request received for ID: {event_id}")
    event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
    if not event:
        print(f"❌ Event {event_id} not found")
        return JSONResponse(content={"success": False, "error": "Event not found"}, status_code=404)
    
    if event.image_url:
        filename = event.image_url.split("/")[-1]
        file_path = os.path.join("static/uploads", filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
    
    if event.thumbnail_url:
        thumbnail_filename = event.thumbnail_url.split("/")[-1]
        thumbnail_path = os.path.join("static/uploads", thumbnail_filename)
        if os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                print(f"Error deleting thumbnail {thumbnail_path}: {e}")
    
    try:
        db.delete(event)
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    
    return JSONResponse(content={"success": True})

@router.post("/admin/retry-analysis")
async def admin_retry_analysis(db: Session = Depends(get_db)):
    """
    Trigger retry of failed AI analysis for incomplete events.
    """
    try:
        from services.tasks import enqueue_event
        from sqlalchemy import or_
        
        # Find photos missing summary
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            or_(models.TimelineEvent.summary == None, models.TimelineEvent.summary == ""),
            models.TimelineEvent.image_url != None
        ).all()
        
        count = 0
        for event in events:
            # Check file existence to avoid useless queueing
            if event.image_url:
                filename = event.image_url.split('/')[-1]
                if os.path.exists(os.path.join("static/uploads", filename)):
                     enqueue_event(event.id)
                     count += 1
        
        return JSONResponse({"success": True, "count": count, "message": f"Queued {count} items for retry."})
    except Exception as e:
        print(f"Error in admin retry: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# Settings API
from services.config import config as AppConfig
from pydantic import BaseModel

class SettingUpdate(BaseModel):
    key: str
    value: str

@router.get("/api/settings")
def get_settings():
    return AppConfig._cache

@router.post("/api/settings/update")
def update_setting(setting: SettingUpdate, db: Session = Depends(get_db)):
    # VALIDATION: Gemini Key Check
    if setting.key == "ai_provider" and setting.value == "gemini":
        gemini_key = AppConfig.get("gemini_api_key")
        
        # DEBUG: Print what we see
        print(f"🔍 Debug Validation: Provider Switch Requested. Current Key in Config: '{gemini_key}'")

        if not gemini_key or gemini_key == "unknown" or len(gemini_key) < 10 or "your_gemini_key" in gemini_key:
             return JSONResponse(
                 {"status": "error", "message": "🚨 Gemini API Key가 유효하지 않습니다. 먼저 Key를 저장해주세요."}, 
                 status_code=400
             )

    success = AppConfig.set(setting.key, setting.value)
    if success:
        # If API key is updated, force a model refresh immediately
        if setting.key == "gemini_api_key":
            try:
                from services.gemini import gemini_service
                gemini_service.refresh_best_model()
            except Exception as e:
                logger.error(f"⚠️ Failed to refresh models after key update: {e}")

        # LOGGING: Record the change
        logger.info(
            f"Admin Setting Updated: {setting.key} = {setting.value}",
            extra={"key": setting.key, "value": setting.value, "user_action": "update_setting"}
        )

        return {"status": "success", "message": "✅ 설정이 변경되었습니다.", "key": setting.key, "value": setting.value}
    return JSONResponse({"status": "error", "message": "Failed to update setting"}, status_code=500)
@router.get("/api/settings/warmup")
def warmup_local_models():
    """
    Triggers loading of local AI models to verify dependencies and warm up.
    """
    logger.info("🔥 Warming up Local AI Models...")
    try:
        # 1. Vision Model (Heaviest)
        from services.analyzer import analyzer
        analyzer.load_model()
        
        # 2. Embedding Model (Sentence Transformers)
        # We can trigger it by getting the model
        from services.rag import Embedder
        Embedder.get_model()
        
        return {"status": "success", "message": "Local Models Ready"}
        
    except ImportError as e:
        logger.error(f"❌ Local AI Warmup Failed (Missing Dependencies): {e}")
        return JSONResponse(
            {"status": "error", "message": "Required libraries missing. Please run 'pip install -r requirements-local.txt' to enable Local Mode."},
            status_code=500
        )
    except Exception as e:
        logger.error(f"❌ Local AI Warmup Failed: {e}")
        return JSONResponse(
            {"status": "error", "message": f"Initialization Failed: {str(e)}"},
            status_code=500
        )
