from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from services import interviewer
from fastapi.templating import Jinja2Templates

router = APIRouter(
    prefix="/memories",
    tags=["memories"]
)

templates = Jinja2Templates(directory="templates")

from services.logger import get_logger

logger = get_logger("memories")

@router.post("/{interaction_id}/answer")
def answer_question(
    interaction_id: int,
    answer: str = Form(...),
    db: Session = Depends(get_db)
):
    print(f"👉 RECEIVED ANSWER SUBMISSION: ID={interaction_id}, Answer='{answer}'") # Console force
    logger.info(f"Processing Answer for Interaction {interaction_id}: {answer[:20]}...")

    success = interviewer.submit_answer(db, interaction_id, answer)
    
    if success:
        print(f"✅ Submission Successful for ID {interaction_id}")
    else:
        print(f"❌ Submission Failed (Not Found) for ID {interaction_id}")

    # Redirect back to home, maybe with a flash message?
    # For MVP, just redirect
    return RedirectResponse(url="/", status_code=303)

@router.get("/daily", response_class=HTMLResponse)
def get_daily_widget(request: Request, db: Session = Depends(get_db)):
    """
    HTMX endpoint to load the Daily Memory widget.
    """
    # Get Profile
    user_profile = request.cookies.get("decade_journey_profile")
    
    interaction = interviewer.get_daily_interview_question(db, user_profile=user_profile)
    
    if not interaction:
        return "" # No photos?
        
    return templates.TemplateResponse("partials/daily_memory.html", {
        "request": request,
        "interaction": interaction,
        "event": interaction.event
    })
    return templates.TemplateResponse("partials/daily_memory.html", {
        "request": request,
        "interaction": interaction,
        "event": interaction.event
    })

@router.post("/daily/refresh", response_class=HTMLResponse)
def refresh_daily_widget(request: Request, db: Session = Depends(get_db)):
    """
    Deletes the current daily question and generates a new one.
    """
    user_profile = request.cookies.get("decade_journey_profile")
    
    # 1. Delete existing
    interviewer.skip_daily_question(db, user_profile=user_profile)
    
    # 2. Generate New
    interaction = interviewer.get_daily_interview_question(db, user_profile=user_profile)
    
    if not interaction:
        return ""
        
    return templates.TemplateResponse("partials/daily_memory.html", {
        "request": request,
        "interaction": interaction,
        "event": interaction.event
    })
