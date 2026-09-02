from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List

# Auth
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "Employee"
    department: str = "General"

class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    department: str
    is_online: bool

    class Config:
        from_attributes = True

# Messages
class MessageCreate(BaseModel):
    recipient_id: int
    content: str

class MessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    timestamp: datetime
    is_read: bool

    class Config:
        from_attributes = True

# Announcements
class AnnouncementCreate(BaseModel):
    content: str

class AnnouncementOut(BaseModel):
    id: int
    sender_id: int
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True

# Meetings
class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    attendee_ids: List[int] = []

class MeetingOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    organizer_id: int
    room_id: str
    attendees: List[UserOut]

    class Config:
        from_attributes = True

# WebRTC signaling payloads (not stored)
class CallOffer(BaseModel):
    target_id: int
    sdp: str

class CallAnswer(BaseModel):
    target_id: int
    sdp: str

class IceCandidate(BaseModel):
    target_id: int
    candidate: dict