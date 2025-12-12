
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
import models
from services.faces import get_unknown_clusters, batch_label_face_cluster, reindex_faces
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/faces", tags=["faces"])

class MergeRequest(BaseModel):
    target_name: str
    source_person_ids: List[int]

class ClusterVal(BaseModel):
    threshold: float = 0.45

@router.get("/clusters")
def get_clusters(threshold: float = 0.45):
    """
    Get clusters of similar 'Unknown' faces to help manage fragmentation.
    Strict threshold default: 0.45
    """
    return get_unknown_clusters(threshold)

@router.post("/merge")
def merge_faces(payload: MergeRequest):
    """
    Merge multiple 'Unknown' person entries into a single Identity (Target Name).
    This effectively appends their embeddings to the Target Person's 'Vector Gallery'.
    """
    success = batch_label_face_cluster(payload.source_person_ids, payload.target_name)
    if not success:
        raise HTTPException(status_code=500, detail="Merge failed")
    
    return {"status": "success", "message": f"Merged {len(payload.source_person_ids)} identities into '{payload.target_name}'"}

@router.post("/reindex")
def trigger_reindex(background_tasks: BackgroundTasks):
    """
    Trigger full face re-indexing (Admin only).
    """
    background_tasks.add_task(reindex_faces)
    return {"status": "started", "message": "Face re-indexing started in background."}
