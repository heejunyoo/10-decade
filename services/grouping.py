
import cv2
import numpy as np
import os
import uuid
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
import models
from database import SessionLocal
from services.rag import memory_vector_store
from sklearn.metrics.pairwise import cosine_similarity

class GroupingService:
    def calculate_blur_score(self, image_path: str) -> float:
        """
        Calculates the variance of the Laplacian (clarity score).
        Higher is better (sharper).
        """
        try:
            # Handle absolute/relative paths
            if image_path.startswith("/"):
                 # Assuming it's already absolute or relative to project root?
                 # DB stores "/static/uploads/..." which is relative to root if running from root.
                 # Python defines relative to CWD.
                 # If path starts with /, it's absolute. But /static is usually web root.
                 real_path = "." + image_path if image_path.startswith("/static") else image_path
            else:
                real_path = image_path

            if not os.path.exists(real_path):
                print(f"⚠️ Image not found for blur score: {real_path}")
                return 0.0

            image = cv2.imread(real_path)
            if image is None:
                return 0.0
                
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            score = cv2.Laplacian(gray, cv2.CV_64F).var()
            return float(score)
        except Exception as e:
            print(f"❌ Blur check failed: {e}")
            return 0.0

    def process_event(self, event_id: int):
        """
        Main entry point. 
        1. Calculate blur score.
        2. Find temporal neighbors.
        3. Check vector similarity.
        4. Group if needed.
        """
        print(f"🧩 Start Grouping Check for Event {event_id}...")
        db = SessionLocal()
        try:
            target = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
            if not target or target.media_type != "photo":
                return

            # 1. Blur Score
            if target.blur_score is None:
                score = self.calculate_blur_score(target.image_url)
                target.blur_score = score
                db.commit() # Commit blur score first
            
            if not target.capture_time:
                print("⚠️ No capture time, skipping stacking.")
                return

            # 2. Temporal Neighbors ( +/- 60 seconds )
            window = timedelta(seconds=60)
            start_time = target.capture_time - window
            end_time = target.capture_time + window
            
            neighbors = db.query(models.TimelineEvent).filter(
                models.TimelineEvent.media_type == "photo",
                models.TimelineEvent.capture_time.between(start_time, end_time),
                models.TimelineEvent.id != target.id
            ).all()
            
            if not neighbors:
                return # No one close

            # 3. Vector Similarity
            # Fetch embeddings for Target + Neighbors
            all_ids = [str(target.id)] + [str(n.id) for n in neighbors]
            embeddings_map = memory_vector_store.get_embeddings(all_ids)
            
            target_vec = embeddings_map.get(str(target.id))
            if target_vec is None:
                print("⚠️ No embedding for target, skipping vector check.")
                return

            sim_threshold = 0.92
            stack_candidates = []

            for n in neighbors:
                n_vec = embeddings_map.get(str(n.id))
                if n_vec is None:
                    continue
                
                # Cosine Similarity
                sim = cosine_similarity([target_vec], [n_vec])[0][0]
                if sim >= sim_threshold:
                    stack_candidates.append(n)

            if not stack_candidates:
                return # No similar photos

            # 4. Create or Join Stack
            # Check if any candidate already has a stack_id
            existing_stack_id = None
            for cand in stack_candidates:
                if cand.stack_id:
                    existing_stack_id = cand.stack_id
                    break
            
            final_stack_id = existing_stack_id if existing_stack_id else str(uuid.uuid4())
            
            # Apply stack_id to target
            target.stack_id = final_stack_id
            
            # If creating new stack, apply to candidates too (if they don't have one? Logic: if they are similar to target, they join target's stack)
            # Warning: Chaining. If A~B and B~C, should A,B,C be one stack?
            # Ideally yes.
            # Convert all candidates to this stack
            stack_members = [target] + stack_candidates
            
            for member in stack_members:
                member.stack_id = final_stack_id
            
            db.commit() # Save grouping
            
            # 5. Elect Representative
            # Recalculate representative for this stack
            # Fetch ALL members of this stack (in case we missed some in the candidate list but they belong to the stack)
            all_stack_members = db.query(models.TimelineEvent).filter(models.TimelineEvent.stack_id == final_stack_id).all()
            
            best_member = None
            max_score = -1.0
            
            # Reset all is_stack_representative
            for m in all_stack_members:
                m.is_stack_representative = 0
                # Ensure blur score computed?
                if m.blur_score is None:
                    m.blur_score = self.calculate_blur_score(m.image_url)
                
                # Selection Logic: Blur Score is primary proxy for quality/focus
                # User mentioned "Face size" too but that's complex to fetch now (need Face table join).
                # Let's stick to blur_score as primary for now.
                if m.blur_score > max_score:
                    max_score = m.blur_score
                    best_member = m
            
            if best_member:
                best_member.is_stack_representative = 1
                print(f"🏆 Stack {final_stack_id}: Selected Event {best_member.id} as Rep (Score: {max_score:.2f})")
            
            db.commit()

        except Exception as e:
            print(f"❌ Grouping Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

grouping_service = GroupingService()
