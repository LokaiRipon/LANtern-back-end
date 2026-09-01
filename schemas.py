from datetime import datetime
from pydantic import BaseModel

# --- MAIL SCHEMAS ---

class MailCreate(BaseModel):
    """Data validation schema [rules that ensure incoming request data matches expected types] for sending mail."""
    sender: str
    recipient: str
    subject: str
    body: str

class MailResponse(MailCreate):
    id: int
    timestamp: datetime
    is_read: bool

    class Config:
        from_attributes = True

# --- BROADCAST / PA SCHEMAS ---

class BroadcastCreate(BaseModel):
    sender: str
    title: str
    message: str
    priority: str = "normal"

class BroadcastResponse(BroadcastCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True