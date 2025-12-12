from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/map", response_class=HTMLResponse)
def read_map(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})

@router.get("/api/map/markers")
@router.get("/api/map-events")
def get_map_markers(db: Session = Depends(get_db)):
    events = db.query(models.TimelineEvent).filter(
        models.TimelineEvent.latitude.isnot(None),
        models.TimelineEvent.longitude.isnot(None)
    ).all()
    
    return [
        {
            "id": event.id,
            "lat": event.latitude,
            "lng": event.longitude,
            "title": event.title or event.date, # Requested 'title'
            "thumbnail": event.thumbnail_url or event.image_url,
            "date": event.date
        }
        for event in events
    ]

from geopy.distance import geodesic

@router.get("/api/map/nearby")
def get_nearby_markers(
    lat: float, 
    lng: float, 
    radius_km: float = 5.0, 
    db: Session = Depends(get_db)
):
    """
    Finds photos within radius_km of (lat, lng).
    Optimized with Bounding Box approximation first.
    """
    # 1. Bounding Box (Approximate)
    # 1 degree latitude ~= 111 km
    # 1 degree longitude ~= 111 km * cos(lat)
    
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * abs(0.00001 + 0.7)) # Rough avg cos(45deg), strict haversine later
    # Just be generous with bounding box
    lat_delta *= 1.5 
    lng_delta *= 1.5
    
    min_lat, max_lat = lat - lat_delta, lat + lat_delta
    min_lng, max_lng = lng - lng_delta, lng + lng_delta
    
    candidates = db.query(models.TimelineEvent).filter(
        models.TimelineEvent.latitude.between(min_lat, max_lat),
        models.TimelineEvent.longitude.between(min_lng, max_lng)
    ).all()
    
    results = []
    center_point = (lat, lng)
    
    for event in candidates:
        event_point = (event.latitude, event.longitude)
        dist = geodesic(center_point, event_point).km
        
        if dist <= radius_km:
            results.append({
                "id": event.id,
                "lat": event.latitude,
                "lng": event.longitude,
                "thumbnail": event.thumbnail_url or event.image_url,
                "date": event.date,
                "distance": round(dist, 2)
            })
            
    # Sort by distance
    results.sort(key=lambda x: x['distance'])
    return results
