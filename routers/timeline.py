from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date
from typing import Optional
from database import get_db
import models
import random
import os

# Import constant from auth router module or define here
# Ideally should be in a shared config
PROFILE_COOKIE_NAME = "decade_journey_profile"

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
def read_root(request: Request, db: Session = Depends(get_db)):
    profile = request.cookies.get(PROFILE_COOKIE_NAME)
    
    # Delegate data fetching to Service
    from services.timeline import timeline_service
    data = timeline_service.get_homepage_data(db, limit=5)
    
    # Specific View Logic (Prompt selection)
    today_md = date.today().strftime('%m-%d')
    current_year = str(date.today().year)
    is_writing_day = False
    writing_prompt = None

    # Dynamic Anniversary Logic
    anniv_env = os.getenv("WEDDING_ANNIVERSARY", "2015-10-20")
    try:
        ay, am, ad = map(int, anniv_env.split('-'))
    except:
        # Fallback
        ay, am, ad = 2015, 10, 20
    
    anniv_md = f"{am:02d}-{ad:02d}"

    if today_md == anniv_md:
        is_writing_day = True
        writing_prompt = "오늘은 결혼기념일입니다. 서로에게, 그리고 미래의 우리에게 편지를 남겨보세요."
    elif today_md == "12-31":
        is_writing_day = True
        writing_prompt = "한 해의 마지막 날입니다. 내년의 우리에게 바라는 점을 적어보세요."

    # Next Opening Date Logic (Keep simple view logic here or move to service if complex)
    # Keeping here for now as it couples with view strictly.
    today = date.today().isoformat()
    next_capsule = db.query(models.TimeCapsule).filter(
        models.TimeCapsule.open_date > today
    ).order_by(models.TimeCapsule.open_date.asc()).first()
    
    if next_capsule:
        y, m, d = map(int, next_capsule.open_date.split('-'))
        next_opening_date = date(y, m, d)
        days_until_open = (next_opening_date - date.today()).days
    else:
        target_dates = [
            date(int(current_year), am, ad),
            date(int(current_year), 12, 31),
            date(int(current_year) + 1, am, ad)
        ]
        future_dates = [d for d in target_dates if d > date.today()]
        next_opening_date = future_dates[0] if future_dates else target_dates[0]
        days_until_open = (next_opening_date - date.today()).days

    # Capsule Message from Query Param
    capsule_msg = request.query_params.get("msg")

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "profile": profile,
        "events": data["events"],
        "unlocked_capsules": data["unlocked_capsules"],
        "locked_count": data["locked_count"],
        "on_this_day_events": data["on_this_day_events"],
        "analytics": data["analytics"],
        "next_skip": data["next_skip"],
        "limit": 5,
        "is_writing_day": is_writing_day,
        "writing_prompt": writing_prompt,
        "days_until_open": days_until_open,
        "next_opening_date": next_opening_date,
        "capsule_msg": capsule_msg
    })

@router.get("/cinema")
def read_cinema(request: Request, db: Session = Depends(get_db)):
    # Fetch only events that have a USER ANSWERED memory
    results = db.query(models.TimelineEvent, models.MemoryInteraction)\
        .join(models.MemoryInteraction, models.TimelineEvent.id == models.MemoryInteraction.event_id)\
        .filter(
            models.TimelineEvent.media_type == "photo",
            models.MemoryInteraction.is_answered == 1
        )\
        .order_by(models.TimelineEvent.date.desc())\
        .all()
        
    events_with_stories = []
    for event, interaction in results:
        event.user_memory = interaction.answer
        event.user_memory_author = interaction.author
        events_with_stories.append(event)
        
    return templates.TemplateResponse("cinema.html", {"request": request, "events": events_with_stories})

@router.get("/search")
def search_events(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    return templates.TemplateResponse("chat_search.html", {
        "request": request,
        "query": q or ""
    })

@router.get("/api/timeline")
def get_timeline_events(request: Request, skip: int = 0, limit: int = 5, tag: str = None, db: Session = Depends(get_db)):
    query = db.query(models.TimelineEvent).filter(
        models.TimelineEvent.media_type != 'video',
        or_(
            models.TimelineEvent.stack_id == None,
            models.TimelineEvent.is_stack_representative == 1
        )
    ).order_by(models.TimelineEvent.date.desc())
    
    if tag:
        query = query.filter(models.TimelineEvent.tags.like(f"%{tag}%"))
    events = query.offset(skip).limit(limit).all()
    
    # Calculate Stack Counts
    stack_ids = [e.stack_id for e in events if e.stack_id]
    stack_counts = {}
    if stack_ids:
        rows = db.query(models.TimelineEvent.stack_id, func.count(models.TimelineEvent.id))\
            .filter(models.TimelineEvent.stack_id.in_(stack_ids))\
            .group_by(models.TimelineEvent.stack_id).all()
        for sid, count in rows:
            stack_counts[sid] = count
    
    for e in events:
        if e.stack_id:
            e.stack_count = stack_counts.get(e.stack_id, 1)
    
    context = {
        "request": request, 
        "events": events,
        "next_skip": skip + limit if len(events) == limit else None,
        "limit": limit
    }
    return templates.TemplateResponse("timeline_response.html", context)

@router.get("/api/tags")
def get_all_tags(db: Session = Depends(get_db)):
    # Fetch only tags column
    results = db.query(models.TimelineEvent.tags).filter(models.TimelineEvent.tags != None).all()
    tag_counts = {}
    for (tags_str,) in results:
        if tags_str:
            tags_list = [t.strip() for t in tags_str.split(',')]
            for tag in tags_list:
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return JSONResponse(content=tag_counts)

@router.get("/api/archive-dates")
def get_archive_dates(db: Session = Depends(get_db)):
    results = db.query(models.TimelineEvent.date).distinct().all()
    dates = [r[0] for r in results if r[0]]
    return JSONResponse(content=dates)

@router.get("/api/archive-items")
def get_archive_items(
    request: Request,
    skip: int = 0,
    limit: int = 20,
    media_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.TimelineEvent)
    
    if media_type == "photo":
        query = query.filter(models.TimelineEvent.media_type != "video")
    elif media_type == "video":
        query = query.filter(models.TimelineEvent.media_type == "video")
        
    query = query.order_by(models.TimelineEvent.date.desc())
    events = query.offset(skip).limit(limit).all()
    
    return templates.TemplateResponse("archive_item.html", {
        "request": request,
        "events": events
    })

@router.get("/archive")
def read_archive(
    request: Request, 
    media_type: str = Query(None), 
    limit: int = 20, 
    db: Session = Depends(get_db)
):
    profile = request.cookies.get(PROFILE_COOKIE_NAME)
    
    if media_type == "people":
        people = db.query(models.Person).filter(models.Person.name != "Unknown").all()
        people.sort(key=lambda p: len(p.faces), reverse=True)
        
        return templates.TemplateResponse("archive.html", {
            "request": request,
            "profile": profile,
            "current_filter": "people",
            "people": people,
            "events": [], 
            "limit": limit,
            "total_count": len(people)
        })

    query = db.query(models.TimelineEvent)
    if media_type == "photo":
        query = query.filter(models.TimelineEvent.media_type != "video")
    elif media_type == "video":
        query = query.filter(models.TimelineEvent.media_type == "video")
        
    query = query.order_by(models.TimelineEvent.date.desc())
    total_count = query.count()
    events = query.limit(limit).all()
    
    return templates.TemplateResponse("archive.html", {
        "request": request,
        "profile": profile,
        "current_filter": media_type,
        "events": events, 
        "total_count": total_count,
        "limit": limit,
        "people": [] 
    })

@router.get("/highlights")
def read_highlights(request: Request, db: Session = Depends(get_db)):
    try:
        # Delegate to Service
        from services.timeline import timeline_service
        data = timeline_service.get_highlights(db)
        
        return templates.TemplateResponse("highlights.html", {
            "request": request, 
            "highlights": data.get("highlights", []),
            "total_events": data.get("total_events", 0),
            "hero_event": data.get("hero_event", None),
            "year_stats": data.get("year_stats", []),
            "days_together": data.get("days_together", 0)
        })
    except Exception as e:
        # Fallback for 500
        print(f"❌ Highlights Error: {e}")
        return templates.TemplateResponse("highlights.html", {
            "request": request, 
            "highlights": [],
            "total_events": 0,
            "hero_event": None,
            "year_stats": [],
            "days_together": 0,
            "error_msg": "데이터를 불러오는 중 문제가 발생했습니다."
        })

@router.get("/api/events/{event_id}")
def get_event_detail(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
    if not event:
        return JSONResponse(status_code=404, content={"message": "Event not found"})
    
    # Get User Story (Interaction)
    # Prefer one with an answer
    interaction = db.query(models.MemoryInteraction).filter(
        models.MemoryInteraction.event_id == event.id,
        models.MemoryInteraction.is_answered == 1
    ).order_by(models.MemoryInteraction.created_at.desc()).first()
    
    # Get People Names with Emotion
    people_data = []
    for face in event.faces:
        if face.person:
            people_data.append({
                "name": face.person.name,
                "emotion": face.emotion
            })
    # Remove duplicates based on name (if needed, but simple list is fine for now)
    # Actually, we might have multiple faces of same person?
    # Let's just return all detected faces or unique people. 
    # Uniqueness by name is better for the UI badge list.
    unique_people = {}
    for p in people_data:
        if p["name"] not in unique_people:
            unique_people[p["name"]] = p["emotion"]
    
    final_people = [{"name": k, "emotion": v} for k, v in unique_people.items()]

    
    data = {
        "id": event.id,
        "date": event.date,
        "image_url": event.image_url,
        "media_type": event.media_type,
        "title": event.title,
        "summary": event.summary, # AI Caption
        "user_memory": interaction.answer if interaction else None,
        "user_memory_author": interaction.author if interaction else None,
        "user_memory_question": interaction.question if interaction else None,
        "location": event.location_name,
        "weather": event.weather_info,
        "tags": event.tags,
        "people": final_people,
        "lat": event.latitude,
        "lng": event.longitude
    }
    return JSONResponse(content=data)

@router.get("/api/events/stack/{stack_id}")
def get_stack_members(request: Request, stack_id: str, db: Session = Depends(get_db)):
    events = db.query(models.TimelineEvent)\
        .filter(models.TimelineEvent.stack_id == stack_id)\
        .order_by(models.TimelineEvent.is_stack_representative.desc(), models.TimelineEvent.capture_time.asc())\
        .all()
    
    return templates.TemplateResponse("partials/stack_gallery.html", {
        "request": request,
        "events": events
    })
