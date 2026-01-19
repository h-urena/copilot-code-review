"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)

class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[str] = None
    expiration_date: str

class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None

def authenticate_teacher(username: str):
    """Helper function to authenticate teacher"""
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return teacher

@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements() -> List[Dict[str, Any]]:
    """
    Get all active announcements (not expired and started if start_date is set)
    """
    now = datetime.now(timezone.utc)
    
    # Find announcements that are active
    query = {
        "expiration_date": {"$gt": now.isoformat()}
    }
    
    # Also check start_date if present
    announcements = []
    for announcement in announcements_collection.find(query):
        start_date = announcement.get("start_date")
        if start_date and datetime.fromisoformat(start_date.replace('Z', '+00:00')) > now:
            continue
        announcements.append({
            "id": str(announcement["_id"]),
            "message": announcement["message"],
            "start_date": announcement.get("start_date"),
            "expiration_date": announcement["expiration_date"]
        })
    
    return announcements

@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str) -> List[Dict[str, Any]]:
    """
    Get all announcements (requires authentication)
    """
    authenticate_teacher(teacher_username)
    
    announcements = []
    for announcement in announcements_collection.find():
        announcements.append({
            "id": str(announcement["_id"]),
            "message": announcement["message"],
            "start_date": announcement.get("start_date"),
            "expiration_date": announcement["expiration_date"]
        })
    
    return announcements

@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(announcement: AnnouncementCreate, teacher_username: str) -> Dict[str, Any]:
    """
    Create a new announcement (requires authentication)
    """
    authenticate_teacher(teacher_username)
    
    # Validate dates
    try:
        exp_date = datetime.fromisoformat(announcement.expiration_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (e.g., 2026-01-31T23:59:59Z)")

    if exp_date <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Expiration date must be in the future")

    if announcement.start_date:
        try:
            start_date = datetime.fromisoformat(announcement.start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (e.g., 2026-01-31T23:59:59Z)")
        if start_date >= exp_date:
            raise HTTPException(status_code=400, detail="Start date must be before expiration date")
    
    doc = {
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date
    }
    
    result = announcements_collection.insert_one(doc)
    
    return {
        "id": str(result.inserted_id),
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date
    }

@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(announcement_id: str, announcement: AnnouncementUpdate, teacher_username: str) -> Dict[str, Any]:
    """
    Update an announcement (requires authentication)
    """
    authenticate_teacher(teacher_username)
    
    try:
        obj_id = ObjectId(announcement_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Get existing announcement
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Prepare update
    update_doc = {}
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date
    if announcement.expiration_date is not None:
        update_doc["expiration_date"] = announcement.expiration_date
    
    # Validate dates if updating
    if "expiration_date" in update_doc or "start_date" in update_doc:
        exp_date_str = update_doc.get("expiration_date", existing["expiration_date"])
        start_date_str = update_doc.get("start_date", existing.get("start_date"))
        
        try:
            exp_date = datetime.fromisoformat(exp_date_str.replace('Z', '+00:00'))
            if exp_date <= datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Expiration date must be in the future")
            
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                if start_date >= exp_date:
                    raise HTTPException(status_code=400, detail="Start date must be before expiration date")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (e.g., 2026-01-31T23:59:59Z)")
    
    if update_doc:
        announcements_collection.update_one({"_id": obj_id}, {"$set": update_doc})
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": obj_id})
    return {
        "id": str(updated["_id"]),
        "message": updated["message"],
        "start_date": updated.get("start_date"),
        "expiration_date": updated["expiration_date"]
    }

@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str):
    """
    Delete an announcement (requires authentication)
    """
    authenticate_teacher(teacher_username)
    
    try:
        obj_id = ObjectId(announcement_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}