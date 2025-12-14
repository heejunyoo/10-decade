from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import models
import random

def get_daily_interview_question(db: Session, user_profile: str = None):
    """
    Selects a photo for today's 'AI Interview'.
    Logic Priority:
    1. Unanswered question from today (persistence) for THIS USER.
    2. 'On This Day' photo from previous years.
    3. Random photo with People (prioritize named people).
    4. Random photo.
    """
    
    # 0. Check Persistence (Did we ask this user today?)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = db.query(models.MemoryInteraction).filter(
        models.MemoryInteraction.created_at >= today_start,
        models.MemoryInteraction.is_answered == 0
    )
    
    if user_profile:
        query = query.filter(models.MemoryInteraction.author == user_profile)
    else:
        # Fallback/Legacy: Find one with no author or just any?
        # Let's say if no profile, we look for global (null author)
        query = query.filter(models.MemoryInteraction.author == None)
        
    existing = query.first()
    if existing:
        return existing
    
    # 1. Selection Logic (Fresh every time)
    # Priority: 
    #   1. On This Day (Same MM-DD)
    #   2. Same Month (Seasonality)
    #   3. Random with People
    #   4. Random Fallback
    
    today_md = datetime.now().strftime("%m-%d")
    today_m = datetime.now().strftime("%m-")
    
    # Try Exact Date Match
    candidates_date = db.query(models.TimelineEvent).filter(
        models.TimelineEvent.date.like(f"%{today_md}"),
        models.TimelineEvent.media_type == "photo"
    ).all()
    
    if candidates_date:
        target_event = random.choice(candidates_date)
        reason = "on_this_day"
    else:
        # Try Same Month Match (Seasonality)
        candidates_month = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.date.like(f"%{today_m}%"),
            models.TimelineEvent.media_type == "photo"
        ).order_by(func.random()).limit(50).all() # Limit to avoid huge query
        
        if candidates_month:
            target_event = random.choice(candidates_month)
            reason = "seasonal"
        else:
            # Fallback: Random with People
             # This is a bit complex query for MVP, let's just pick random photo and check if it has faces later
            count = db.query(models.TimelineEvent).filter(models.TimelineEvent.media_type == "photo").count()
            if count > 0:
                offset = random.randint(0, count - 1)
                target_event = db.query(models.TimelineEvent).filter(models.TimelineEvent.media_type == "photo").offset(offset).first()
                reason = "random"
            else:
                return None
    
    # 3. Generate Question (Generative AI Upgrade)
    # names = [] # Disabled by User Request
    
    # Context Construction
    context = {
        "date": target_event.date,
        "location": target_event.location_name or "알 수 없는 장소",
        # "people": names,
        "caption": target_event.summary or target_event.description or ""
    }
    
    # Try AI Generation first
    from services.ai_service import ai_service
    question = ai_service.generate_interview_question(context)
    
    # Fallback to Templates if AI fails
    if not question:
        templates = [
            "이 사진을 찍었던 날의 분위기가 기억나시나요?",
            "이 순간으로 다시 돌아간다면 무엇을 하고 싶으신가요?",
            "이 날의 날씨나 주변 풍경은 어땠나요?",
            "이 사진에 담긴 숨겨진 이야기가 있나요?",
            "함께한 분들과 어떤 이야기를 나누셨나요?",
            "이 사진을 보면 가장 먼저 떠오르는 감정은 무엇인가요?"
        ]
        question = random.choice(templates)
            
        # Add Context Prefix only for fallback (AI generates its own context)
        if reason == "on_this_day":
            question = f"[📅 오늘과 같은 날] " + question
        elif reason == "seasonal":
            question = f"[🍂 {datetime.now().month}월의 추억] " + question
        
    # 4. Create Interaction Record
    interaction = models.MemoryInteraction(
        event_id=target_event.id,
        question=question,
        is_answered=0,
        author=user_profile  # Save the user profile
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    
    return interaction

def submit_answer(db: Session, interaction_id: int, answer: str):
    """
    Save the user's answer.
    Also appends the answer to the Event's description or logs it.
    """
    interaction = db.query(models.MemoryInteraction).filter(models.MemoryInteraction.id == interaction_id).first()
    if not interaction:
        return False
        
    interaction.answer = answer
    interaction.is_answered = 1
    interaction.answered_at = datetime.now()
    
    # Optional: Append to Event Description or Comments?
    # For now, let's keep it in interaction table. 
    # But maybe we want to see it on the photo?
    # "Memory Note: ..."
    
    db.commit()
    db.commit()
    return True

def skip_daily_question(db: Session, user_profile: str = None):
    """
    Deletes the current unanswered question for today so a new one can be generated.
    """
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = db.query(models.MemoryInteraction).filter(
        models.MemoryInteraction.created_at >= today_start,
        models.MemoryInteraction.is_answered == 0
    )
    
    if user_profile:
        query = query.filter(models.MemoryInteraction.author == user_profile)
    else:
        query = query.filter(models.MemoryInteraction.author == None)
        
    existing = query.first()
    if existing:
        db.delete(existing)
        db.commit()
        return True
    return False
