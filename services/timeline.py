
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date
from collections import defaultdict
import random
import models

class TimelineService:
    def get_season(self, date_str):
        try:
            month = int(date_str[5:7])
            if 3 <= month <= 5: return "Spring"
            elif 6 <= month <= 8: return "Summer"
            elif 9 <= month <= 11: return "Autumn"
            else: return "Winter"
        except:
            return "Unknown"

    def get_memories_on_this_day(self, db: Session, month: int, day: int, limit: int = 10):
        """
        Refined 'On This Day' logic with Ranking.
        """
        today_md = f"{month:02d}-{day:02d}"
        current_year = str(date.today().year)

        # Base Query
        query = db.query(models.TimelineEvent).filter(
            func.strftime('%m-%d', models.TimelineEvent.date) == today_md,
            func.strftime('%Y', models.TimelineEvent.date) != current_year,
            models.TimelineEvent.media_type != 'video' # Focus on photos for widget
        )
        
        candidates = query.all()
        
        if not candidates:
            return []

        # Ranking Logic (Scoring)
        # 1. Favorite (Simulated by 'fav' tag or just explicit tags) -> +3
        # 2. Has People -> +2
        # 3. Has Caption -> +1
        
        scored = []
        for ev in candidates:
            score = 0
            # Check faces
            if ev.faces:
                score += 2
            
            # Check tags (simulating favorite)
            if ev.tags:
                 score += 1
                 if "favorite" in ev.tags or "heart" in ev.tags:
                     score += 3
            
            if ev.summary:
                score += 1

            scored.append((score, ev))
        
        # Sort by score desc, then shuffle for randomness among ties
        random.shuffle(scored) # Shuffle first to randomize ties
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N
        return [item[1] for item in scored[:limit]]

    def get_homepage_data(self, db: Session, limit: int = 5):
        """
        Fetches data for the homepage (index).
        """
        # Recent Events (Photos only) - Stacking Filter
        # Show if (stack_id IS NULL) OR (is_stack_representative == 1)
        events = db.query(models.TimelineEvent)\
            .filter(
                models.TimelineEvent.media_type != 'video',
                or_(
                    models.TimelineEvent.stack_id == None,
                    models.TimelineEvent.is_stack_representative == 1
                )
            )\
            .order_by(models.TimelineEvent.date.desc())\
            .limit(limit).all()
        
        # Calculate Stack Counts
        stack_ids = [e.stack_id for e in events if e.stack_id]
        stack_counts = {}
        if stack_ids:
            # Query db for counts
            rows = db.query(models.TimelineEvent.stack_id, func.count(models.TimelineEvent.id))\
                .filter(models.TimelineEvent.stack_id.in_(stack_ids))\
                .group_by(models.TimelineEvent.stack_id).all()
            for sid, count in rows:
                stack_counts[sid] = count
        
        # Attach counts
        for e in events:
            if e.stack_id:
                e.stack_count = stack_counts.get(e.stack_id, 1)

        next_skip = limit if len(events) == limit else None
        today = date.today()
        
        # Capsules
        unlocked_capsules = db.query(models.TimeCapsule).filter(models.TimeCapsule.open_date <= today.isoformat()).order_by(models.TimeCapsule.open_date.desc()).all()
        locked_count = db.query(models.TimeCapsule).filter(models.TimeCapsule.open_date > today.isoformat()).count()
        
        # On This Day (Use new logic)
        on_this_day_events = self.get_memories_on_this_day(db, today.month, today.day, limit=10)
        
        # Analytics
        analytics = {
            "total_memories": db.query(models.TimelineEvent).count(),
            "total_photos": db.query(models.TimelineEvent).filter(models.TimelineEvent.media_type != 'video').count(),
            "total_videos": db.query(models.TimelineEvent).filter(models.TimelineEvent.media_type == 'video').count(),
            "busiest_year": db.query(func.substr(models.TimelineEvent.date, 1, 4), func.count(models.TimelineEvent.id))\
                             .group_by(func.substr(models.TimelineEvent.date, 1, 4))\
                             .order_by(func.count(models.TimelineEvent.id).desc()).first(),
            "top_tags": db.query(models.TimelineEvent.tags).filter(models.TimelineEvent.tags != None).all()
        }
        
        return {
            "events": events,
            "next_skip": next_skip,
            "unlocked_capsules": unlocked_capsules,
            "locked_count": locked_count,
            "on_this_day_events": on_this_day_events,
            "analytics": analytics
        }

    def get_highlights(self, db: Session):
        """
        Generates seasonal highlights logic.
        """
        # 1. Fetch metadata
        query = db.query(models.TimelineEvent.id, models.TimelineEvent.date, models.TimelineEvent.summary)\
            .filter(models.TimelineEvent.image_url != None)\
            .order_by(models.TimelineEvent.date.asc())
        
        events_meta = query.all()
        total_events = len(events_meta)

        # 2. Hero Event
        hero_event = None
        if events_meta:
            captioned_ids = [e.id for e in events_meta if e.summary]
            hero_id = random.choice(captioned_ids) if captioned_ids else random.choice(events_meta).id
            hero_event = db.query(models.TimelineEvent).get(hero_id)
            
        # 0. Get Wedding Anniversary
        from services.config import config
        import os
        # Priority: DB Setting > Env Var > Default
        default_date = os.getenv("WEDDING_ANNIVERSARY", "2015-10-20")
        wedding_date_str = config.get("wedding_anniversary", default_date)
        try:
            w_y, w_m, w_d = map(int, wedding_date_str.split('-'))
            wedding_date = date(w_y, w_m, w_d)
        except:
            wedding_date = date(2015, 10, 20) # Ultimate Fallback

        # Days Together
        days_together = (date.today() - wedding_date).days
        years_label = f"{days_together:,} Days"

        # 3. Seasonal Logic (Relative to Anniversary)
        # We still group by Calendar Year for display familiarity OR Anniversary Year?
        # User requested: "Calculate from that date". 
        # Let's group by "Anniversary Year" (e.g. 1st Year, 2nd Year...)
        
        temp_storage = defaultdict(lambda: defaultdict(list))
        
        # Sort logic
        for e in events_meta:
            try:
                e_y, e_m, e_d = map(int, e.date.split('-'))
                e_date = date(e_y, e_m, e_d)
                
                # Calculate Anniversary Year (1-based)
                # If event is before wedding, it's "Pre-Wedding" or Year 0
                if e_date < wedding_date:
                    anniv_year_num = 0
                    label = "Pre-Wedding"
                else:
                    diff_days = (e_date - wedding_date).days
                    anniv_year_num = (diff_days // 365) + 1
                    label = f"Year {anniv_year_num}"

                season = self.get_season(e.date)
                
                # Use a composite key for sorting: (YearNum, Label)
                temp_storage[(anniv_year_num, label)][season].append(e.id)
            except:
                continue
            
        # Year Stats
        year_stats = {}
        # Key in temp_storage is tuple (num, label)
        for (num, label), seasons in temp_storage.items():
            year_stats[label] = sum(len(ids) for ids in seasons.values())
            
        # Select representative IDs
        selected_ids = []
        # Sort by year number
        sorted_years = sorted(temp_storage.items(), key=lambda x: x[0][0])
        
        for (num, label), seasons in sorted_years:
            for season_name in ["Spring", "Summer", "Autumn", "Winter"]:
                if seasons[season_name]:
                    selected_ids.append(random.choice(seasons[season_name]))
                    
        # Fetch full objects
        highlights = defaultdict(list)
        if selected_ids:
            results = db.query(models.TimelineEvent, models.MemoryInteraction)\
                .outerjoin(models.MemoryInteraction, (models.TimelineEvent.id == models.MemoryInteraction.event_id) & (models.MemoryInteraction.is_answered == 1))\
                .filter(models.TimelineEvent.id.in_(selected_ids))\
                .all()
            
            results.sort(key=lambda x: x[0].date)
            
            for event, interaction in results:
                # Re-calculate label for grouping
                e_y, e_m, e_d = map(int, event.date.split('-'))
                e_date = date(e_y, e_m, e_d)
                if e_date < wedding_date:
                    label = "Pre-Wedding"
                else:
                    diff = (e_date - wedding_date).days
                    anniv_num = (diff // 365) + 1
                    # Logic to determine Calendar span for subtitle?
                    # Start Date of this anniv year
                    # Just use "Year X" for now
                    label = f"Year {anniv_num}"

                season = self.get_season(event.date)
                
                user_text = None
                if interaction and interaction.answer:
                    user_text = interaction.answer
                elif event.description:
                     user_text = event.description
                
                event.user_memory = user_text
                highlights[label].append({"event": event, "season": season})
                
        return {
            "highlights": highlights,
            "total_events": total_events,
            "hero_event": hero_event,
            "year_stats": year_stats,
            "days_together": days_together # Pass this for Hero
        }

timeline_service = TimelineService()
