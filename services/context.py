import requests
import time
from database import SessionLocal
import models
from datetime import datetime

class ContextService:
    def __init__(self):
        self.headers = {
            "User-Agent": "DecadeJourney/1.0 (context@decadejourney.local)"
        }

    def get_address(self, lat: float, lon: float) -> str:
        """
        Reverse geocoding using OpenStreetMap (Nominatim).
        Returns nicely formatted "City, Country" or "Town".
        """
        if not lat or not lon:
            return None
            
        try:
            # Add delay to respect usage policy
            time.sleep(1.1) 
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                
                # Priority: City > Town > Village
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county")
                country = addr.get("country")
                
                parts = []
                if city: parts.append(city)
                if country: parts.append(country)
                
                return ", ".join(parts)
        except Exception as e:
            print(f"⚠️ Geocoding error: {e}")
            return None
        return None

    def get_weather(self, lat: float, lon: float, date_str: str) -> str:
        """
        Get historical weather from Open-Meteo.
        Open-Meteo Historical Weather API.
        """
        if not lat or not lon or not date_str:
            return None
            
        try:
            # Open-Meteo requires YYYY-MM-DD
            # And it's an archive API usually.
            # Does it support 'today'? Yes, via forecast API, but we usually look at history.
            
            # Check if date is today/future? If so use forecast.
            # But assume historical for now.
            
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&daily=weathercode,temperature_2m_max&timezone=auto"
            
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                
                # Decode Weather Code (WMO)
                code = daily.get("weathercode", [None])[0]
                temp = daily.get("temperature_2m_max", [None])[0]
                
                condition = self._wmo_to_string(code)
                
                if condition and temp is not None:
                    return f"{condition}, {temp}°C"
                elif condition:
                    return condition
                    
        except Exception as e:
            print(f"⚠️ Weather fetch error: {e}")
            return None
        return None
        
    def _wmo_to_string(self, code):
        if code is None: return None
        # Simplified WMO Table
        if code == 0: return "Clear Sky ☀️"
        if code in [1, 2, 3]: return "Partly Cloudy ⛅"
        if code in [45, 48]: return "Foggy 🌫️"
        if code in [51, 53, 55]: return "Drizzle 🌧️"
        if code in [61, 63, 65]: return "Rain 🌧️"
        if code in [71, 73, 75]: return "Snow ❄️"
        if code in [80, 81, 82]: return "Rain Showers 🌦️"
        if code in [95, 96, 99]: return "Thunderstorm ⚡"
        return "Cloudy ☁️"

    def enrich_event(self, event_id: int):
        db = SessionLocal()
        try:
            event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
            if not event or not event.latitude or not event.longitude:
                return
            
            updated = False
            
            # 1. Address
            if not event.location_name:
                address = self.get_address(event.latitude, event.longitude)
                if address:
                    event.location_name = address
                    updated = True
                    print(f"📍 Context: Resolved Address -> {address}")
            
            # 2. Weather
            if not event.weather_info and event.date:
                weather = self.get_weather(event.latitude, event.longitude, event.date)
                if weather:
                    event.weather_info = weather
                    updated = True
                    print(f"☁️ Context: Resolved Weather -> {weather}")
            
            if updated:
                db.commit()
                print(f"✅ Event {event_id} enriched.")
                
        except Exception as e:
            print(f"❌ Context enrichment failed: {e}")
        finally:
            db.close()

context_service = ContextService()
