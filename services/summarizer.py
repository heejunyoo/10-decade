from datetime import datetime
from sqlalchemy.orm import Session
from database import get_db
import models
from services.ai_service import ai_service
from services.logger import get_logger

logger = get_logger("summarizer")

def get_events_for_date(db: Session, date_str: str):
    """
    Fetches all photo/video events for a specific date.
    """
    return db.query(models.TimelineEvent).filter(
        models.TimelineEvent.date == date_str,
        models.TimelineEvent.media_type.in_(["photo", "video"])
    ).all()

def generate_daily_summary(date_str: str):
    """
    Generates a daily summary for the given date and saves it as a TimelineEvent.
    """
    logger.info(f"📅 Generating Daily Summary for {date_str}...")
    db = next(get_db())
    try:
        events = get_events_for_date(db, date_str)
        if not events:
            logger.info("No events found for this date. Skipping summary.")
            return None

        # 1. Construct Context
        context_lines = []
        for evt in events:
            line = f"- [{evt.capture_time or 'Time Unknown'}] "
            if evt.location_name:
                line += f"at {evt.location_name}. "
            if evt.summary:
                line += f"Scan: {evt.summary} "
            if evt.description:
                line += f"User Note: {evt.description} "
            
            # People
            names = [f.person.name for f in evt.faces if f.person]
            if names:
                line += f"With: {', '.join(set(names))}."
                
            context_lines.append(line)
            
        full_context = "\n".join(context_lines)
        
        # 2. Call AI
        # We assume ai_service has a method or we use it directly
        # Let's craft a prompt here and use ai_service.generate_response?
        # Ideally we want a specific 'summarize' mode.
        
        prompt = (
            f"Here is a log of events from {date_str}:\n\n"
            f"{full_context}\n\n"
            "Write a cohesive, short diary entry (1 paragraph) summarizing this day. "
            "Focus on the main activities, locations, and people. "
            "Do not use bullet points. Write in the past tense."
        )
        
        # We can use the existing chat interface for simplicity, or add a dedicated method.
        # Let's use `generate_response` but with a system prompt override if possible?
        # `ai_service` is persona-based.
        # Let's rely on the LLM's instruction following capability within the persona context.
        # Or add a method to `ai_service` or `ollama_manager` directly.
        # Updating `ai_service` is cleaner.
        
        # For now, let's use a direct call pattern for robustness if I don't want to modify ai_service again.
        # But wait, I updated `ollama_manager` to support specific model calls? No, just ensuring.
        # I'll update `ai_service` to expose `generate_raw(messages)`?
        # Actually `ai_service` has `generate_response`. I'll just use that with a strong prompt.
        
        summary_text = ai_service.generate_response(
            user_input=prompt,
            context="You are a helpful historian summarizing a day's events.",
            conversation_history=[] # Stateless
        )
        
        # 3. Save Summary Event
        # Check if one exists
        existing = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.date == date_str,
            models.TimelineEvent.media_type == "day_summary"
        ).first()
        
        if existing:
            print(f"Updating existing summary for {date_str}")
            existing.summary = summary_text
            # Update RAG?
            existing_id = existing.id
        else:
            new_event = models.TimelineEvent(
                date=date_str,
                media_type="day_summary",
                title=f"Daily Summary: {date_str}",
                summary=summary_text,
                description="AI-generated summary of the day's events.",
                image_url="/static/img/icon_diary.png" # Placeholder or None
            )
            db.add(new_event)
            db.commit()
            db.refresh(new_event)
            existing_id = new_event.id
            
        logger.info(f"✅ Daily Summary Saved: {summary_text[:50]}...")
        
        # 4. Update RAG
        from services.rag import memory_vector_store
        memory_vector_store.update_photo_index(existing_id)
        
        return summary_text

    except Exception as e:
        logger.error(f"Error generation summary: {e}")
        return None
    finally:
        db.close()
