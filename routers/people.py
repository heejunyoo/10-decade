
from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from services.media import regenerate_captions_for_person

router = APIRouter(prefix="/people", tags=["people"])
templates = Jinja2Templates(directory="templates")

@router.get("/")
def list_people(request: Request, db: Session = Depends(get_db)):
    # Sort by number of faces (descending)
    # Note: SQLite doesn't support easy count sort without join/group by complexity.
    # For now, just fetch all persons.
    # Ideally: db.query(Person).join(Face).group_by(Person.id).order_by(func.count(Face.id).desc()).all()
    
    people = db.query(models.Person).all()
    # Sort in python for now (n < 1000 usually)
    people.sort(key=lambda p: len(p.faces), reverse=True)
    
    return templates.TemplateResponse("people.html", {
        "request": request, 
        "people": people
    })

from services.faces import get_indexing_status

@router.get("/{person_id}")
def person_detail(request: Request, person_id: int, db: Session = Depends(get_db)):
    # Debug Logging
    all_ids = [p.id for p in db.query(models.Person.id).all()]
    print(f"🔎 DEBUG: Requested Person {person_id}. Existing IDs: {all_ids}")

    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    
    # 1. Check for Re-indexing active
    indexing_status = get_indexing_status()
    if indexing_status and indexing_status.get("is_indexing"):
        if not person:
            return templates.TemplateResponse("scanning.html", {
                "request": request, 
                "status": indexing_status
            })

    if not person:
        print(f"⚠️ Person {person_id} not found. Rendering 404.html")
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
        
    events = []
    face_map = {} # event_id -> location_json
    
    # Sort faces by event date? Or simple list
    sorted_faces = sorted(person.faces, key=lambda f: f.event.date if f.event else "0000-00-00", reverse=True)
    
    for face in sorted_faces:
        if face.event:
            events.append(face.event)
            face_map[face.event.id] = face.location

    return templates.TemplateResponse("person_detail.html", {
        "request": request,
        "person": person,
        "events": events,
        "face_map": face_map
    })

@router.post("/{person_id}/update")
def update_person(
    person_id: int, 
    background_tasks: BackgroundTasks,
    name: str = Form(...), 
    db: Session = Depends(get_db)
):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if person:
        old_name = person.name
        person.name = name
        db.commit()
        
        # Trigger AI update if name changed
        if old_name != name:
            print(f"📝 Name changed ({old_name} -> {name}). Queuing caption update...")
            background_tasks.add_task(regenerate_captions_for_person, person_id)
            
    return RedirectResponse(url=f"/people/{person_id}", status_code=303)
            
@router.delete("/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        return RedirectResponse(url="/people", status_code=404)
    
    # Check if this person has faces and delete them
    # Note: If cascade delete is not set up in DB schema, we do it manually safely here.
    # The models.py Relationship doesn't explicitly state cascade="all, delete", so manual is safer.
    faces = db.query(models.Face).filter(models.Face.person_id == person_id).all()
    for face in faces:
        db.delete(face)
        
    db.delete(person)
    db.commit()
    
    return {"status": "success", "message": f"Person {person_id} deleted"}
