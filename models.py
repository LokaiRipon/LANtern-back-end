from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from database import Base

# Association table for meeting attendees (many-to-many)
meeting_attendees = Table(
    "meeting_attendees",
    Base.metadata,
    Column("meeting_id", Integer, ForeignKey("meetings.id")),
    Column("user_id", Integer, ForeignKey("users.id")),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String, default="Employee")   # CEO, Manager, Employee
    department = Column(String, default="General")
    is_online = Column(Boolean, default=False)

    # Relationships
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.recipient_id", back_populates="recipient")
    announcements = relationship("Announcement", back_populates="author")
    meetings_organized = relationship("Meeting", foreign_keys="Meeting.organizer_id", back_populates="organizer")
    meetings_attending = relationship("Meeting", secondary=meeting_attendees, back_populates="attendees")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    recipient_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")

class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    author = relationship("User", back_populates="announcements")

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    organizer_id = Column(Integer, ForeignKey("users.id"))
    room_id = Column(String, unique=True)   # used for chat room

    organizer = relationship("User", foreign_keys=[organizer_id], back_populates="meetings_organized")
    attendees = relationship("User", secondary=meeting_attendees, back_populates="meetings_attending")