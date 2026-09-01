from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from database import Base

class Mail(Base):
    __tablename__ = "mail"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, index=True)
    recipient = Column(String, index=True)
    subject = Column(String)
    body = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

class Broadcast(Base):
    """Database model for Public Address (PA) network announcements."""
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)
    title = Column(String)
    message = Column(Text)
    priority = Column(String, default="normal")  # Options: normal, urgent, emergency
    timestamp = Column(DateTime, default=datetime.utcnow)