from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter()
templates = Jinja2Templates(directory="templates")

from datetime import date

@router.get("/capsule")
def create_capsule_page(request: Request, db: Session = Depends(get_db)):
    today = date.today().isoformat()
    current_year = str(date.today().year)
    
    # Fetch Data
    total_unlocked_count = db.query(models.TimeCapsule)\
        .filter(models.TimeCapsule.open_date <= today)\
        .count()

    unlocked_capsules = db.query(models.TimeCapsule)\
        .filter(models.TimeCapsule.open_date <= today)\
        .order_by(models.TimeCapsule.open_date.desc())\
        .limit(3)\
        .all()
        
    locked_count = db.query(models.TimeCapsule)\
        .filter(models.TimeCapsule.open_date > today)\
        .count()
        
    next_capsule = db.query(models.TimeCapsule).filter(
        models.TimeCapsule.open_date > today
    ).order_by(models.TimeCapsule.open_date.asc()).first()
    
    days_until_open = 0
    next_opening_date = None
    
    if next_capsule:
        y, m, d = map(int, next_capsule.open_date.split('-'))
        next_opening_date = date(y, m, d)
        days_until_open = (next_opening_date - date.today()).days
    else:
        # Fallback Dates logic (same as timeline)
        target_dates = [
            date(int(current_year), 10, 20),
            date(int(current_year), 12, 31),
            date(int(current_year) + 1, 10, 20)
        ]
        future_dates = [d for d in target_dates if d > date.today()]
        next_opening_date = future_dates[0] if future_dates else target_dates[0]
        days_until_open = (next_opening_date - date.today()).days

    # Remove synchronous AI call
    # Logic moved to /api/capsule/smart-prompt via HTMX

    return templates.TemplateResponse("capsule_form.html", {
        "request": request,
        "unlocked_capsules": unlocked_capsules,
        "total_unlocked_count": total_unlocked_count,
        "locked_count": locked_count,
        "next_opening_date": next_opening_date,
        "days_until_open": days_until_open
    })

@router.get("/api/capsule/smart-prompt")
def get_capsule_prompt(request: Request):
    """
    Async HTMX endpoint to generate the prompt.
    """
    user_name = request.cookies.get("decade_journey_profile") or "여행자"
    
    from services.ai_service import ai_service
    smart_prompt = ai_service.generate_time_capsule_question(author_name=user_name)
    
    return templates.TemplateResponse("partials/capsule_prompt.html", {
        "request": request,
        "smart_prompt": smart_prompt
    })

@router.get("/capsule/list")
def get_capsule_list(request: Request, db: Session = Depends(get_db)):
    today = date.today().isoformat()
    capsules = db.query(models.TimeCapsule)\
        .filter(models.TimeCapsule.open_date <= today)\
        .order_by(models.TimeCapsule.open_date.desc())\
        .all()
        
    return templates.TemplateResponse("capsule_list.html", {
        "request": request, 
        "capsules": capsules
    })

@router.post("/capsule")
async def create_capsule(
    request: Request,
    author: str = Form(...),
    open_date: str = Form(...),
    message: str = Form(...),
    capsule_type: str = Form("custom"),
    prompt_question: str = Form(None),
    db: Session = Depends(get_db)
):
    new_capsule = models.TimeCapsule(
        author=author,
        open_date=open_date,
        message=message,
        capsule_type=capsule_type,
        prompt_question=prompt_question
    )
    db.add(new_capsule)
    db.commit()
    
    # Redirect to home with a success query param
    # We'll need to handle this query param in the index route (routers/timeline.py)
    msg = f"타임캡슐이 안전하게 봉인되었습니다! {open_date}에 열립니다."
    return RedirectResponse(url=f"/?msg={msg}", status_code=303)

@router.get("/api/capsule-templates")
def get_capsule_templates():
    return JSONResponse(content=[
        {"id": 1, "question": "내년 이맘때, 우리가 가장 자랑스러워할 성취는 무엇일까요?", "type": "next_year"},
        {"id": 2, "question": "현재 배우자에게 가장 감사한 점을 적고, 내년에도 이 감정이 지속될 수 있도록 우리가 노력할 점은 무엇일까요?", "type": "relationship"},
        {"id": 3, "question": "다음 여행에서 꼭 가보고 싶은 곳과 그곳에서 하고 싶은 활동을 적어주세요.", "type": "bucket_list"},
        {"id": 4, "question": "10년 뒤 우리의 모습은 어떻게 변해있을까요?", "type": "legacy"}
    ])
