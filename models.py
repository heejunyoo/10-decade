from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, LargeBinary
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class Settings(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True) # JSON or simple string
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True) # YYYY-MM-DD format
    title = Column(String, index=True, nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    file_hash = Column(String, index=True, nullable=True)
    phash = Column(String, index=True, nullable=True)
    tags = Column(String, nullable=True)
    summary = Column(Text, nullable=True) # AI Generated Caption
    thumbnail_url = Column(String, nullable=True)
    media_type = Column(String, default="photo")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_name = Column(String, nullable=True)
    weather_info = Column(String, nullable=True)
    capture_time = Column(DateTime, nullable=True) # Full timestamp for stacking
    
    # Photo Stacking
    stack_id = Column(String, index=True, nullable=True) # UUID for the group
    is_stack_representative = Column(Integer, default=0) # 0 or 1 (Boolean)
    blur_score = Column(Float, nullable=True) # Quality metric
    
    mood = Column(String, nullable=True) # AI Detected Atmosphere

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    faces = relationship("Face", back_populates="event")
    interactions = relationship("MemoryInteraction", back_populates="event")

class TimeCapsule(Base):
    __tablename__ = "time_capsules"

    id = Column(Integer, primary_key=True, index=True)
    author = Column(String) # Mom, Dad, etc.
    message = Column(Text)
    open_date = Column(String) # YYYY-MM-DD
    capsule_type = Column(String, default="custom") # next_year, next_decade, legacy, custom
    prompt_question = Column(String, nullable=True)
    is_read = Column(Integer, default=0) # Boolean 0/1 (SQLite)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Person(Base):
    __tablename__ = "people"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Unknown", index=True)
    cover_photo = Column(String, nullable=True) # URL to a representative face crop
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    faces = relationship("Face", back_populates="person")

class Face(Base):
    __tablename__ = "faces"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("timeline_events.id"))
    person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    encoding = Column(LargeBinary) # 128-d vector pickled or raw bytes
    location = Column(String) # JSON "[top, right, bottom, left]"
    thumbnail_url = Column(String, nullable=True) # Crop of the face
    emotion = Column(String, nullable=True) # happy, sad, angry, etc.
    
    event = relationship("TimelineEvent", back_populates="faces")
    person = relationship("Person", back_populates="faces")

class MemoryInteraction(Base):
    __tablename__ = "memory_interactions"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("timeline_events.id"))
    question = Column(String)
    answer = Column(Text, nullable=True) # Null if user hasn't answered yet
    is_answered = Column(Integer, default=0) # 0/1
    author = Column(String, nullable=True) # Profile name (e.g. "Dad")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)

    event = relationship("TimelineEvent", back_populates="interactions")

class SystemLog(Base):
    """
    Structured System Logs for Observability.
    Replaces ephemeral print() statements.
    """
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String, index=True) # INFO, WARNING, ERROR
    module = Column(String, index=True) # Vision, System, Auth...
    message = Column(Text)
    metadata_json = Column(Text, nullable=True) # JSON string for extra context
    created_at = Column(DateTime(timezone=True), server_default=func.now())
