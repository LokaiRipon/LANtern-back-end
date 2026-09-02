import sys
import json
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from database import engine, Base, get_db
from models import User, Message, Announcement, Meeting
from schemas import (
    UserCreate, UserOut, UserLogin,
    MessageCreate, MessageOut,
    AnnouncementCreate, AnnouncementOut,
    MeetingCreate, MeetingOut,
    CallOffer, CallAnswer, IceCandidate
)
from connection_manager import manager

# --- CONFIG ---
SECRET_KEY = "your-secret-key-change-in-production"   # TODO: env var
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- FIX: use pbkdf2_sha256 instead of bcrypt to avoid 72-byte limit ---
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# --- CREATE TABLES ---
Base.metadata.create_all(bind=engine)

# --- PATH RESOLVER FOR PYINSTALLER ---
def get_resource_path(relative_path: str) -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path

# --- FASTAPI APP ---
app = FastAPI(title="LANtern Command", version="1.0")

static_dir = get_resource_path("static")
templates_dir = get_resource_path("templates")

if not static_dir.exists():
    static_dir = get_resource_path("../static")
if not templates_dir.exists():
    templates_dir = get_resource_path("../templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# --- AUTH HELPERS ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    # add expiration if needed
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def is_authorized(user: User, required_role: str = None):
    if required_role:
        if user.role not in ["CEO", "Manager"] and user.role != required_role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True

# --- ROUTES ---

@app.get("/")
async def serve_frontend(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Auth
@app.post("/api/auth/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(400, "Username already taken")
    hashed = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed,
        full_name=user.full_name,
        role=user.role,
        department=user.department
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"msg": "User created"}

@app.post("/api/auth/login")
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect username or password")
    token = create_access_token({"sub": str(user.id)})
    # Mark online
    user.is_online = True
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": UserOut.model_validate(user)}

@app.post("/api/auth/logout")
async def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.is_online = False
    db.commit()
    return {"msg": "Logged out"}

# Users
@app.get("/api/users", response_model=List[UserOut])
async def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).all()

# Messages
@app.post("/api/mail", response_model=MessageOut)
async def send_message(
    msg: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check recipient exists
    recipient = db.query(User).filter(User.id == msg.recipient_id).first()
    if not recipient:
        raise HTTPException(404, "Recipient not found")
    db_msg = Message(
        sender_id=current_user.id,
        recipient_id=msg.recipient_id,
        content=msg.content
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    # Notify recipient if online
    await manager.send_personal(msg.recipient_id, {
        "type": "new_message",
        "message": MessageOut.model_validate(db_msg).model_dump()
    })
    return db_msg

@app.get("/api/mail/inbox", response_model=List[MessageOut])
async def get_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msgs = db.query(Message).filter(Message.recipient_id == current_user.id).order_by(Message.timestamp.desc()).all()
    return msgs

@app.get("/api/mail/sent", response_model=List[MessageOut])
async def get_sent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msgs = db.query(Message).filter(Message.sender_id == current_user.id).order_by(Message.timestamp.desc()).all()
    return msgs

# Announcements (PA)
@app.post("/api/public", response_model=AnnouncementOut)
async def post_announcement(
    ann: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only CEO or Manager can broadcast
    if current_user.role not in ["CEO", "Manager"]:
        raise HTTPException(403, "Only CEO/Manager can post public announcements")
    db_ann = Announcement(sender_id=current_user.id, content=ann.content)
    db.add(db_ann)
    db.commit()
    db.refresh(db_ann)
    # Broadcast to all online
    await manager.broadcast({
        "type": "public_announcement",
        "announcement": AnnouncementOut.model_validate(db_ann).model_dump()
    })
    return db_ann

@app.get("/api/public", response_model=List[AnnouncementOut])
async def get_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Announcement).order_by(Announcement.timestamp.desc()).all()

# Meetings
@app.post("/api/meetings", response_model=MeetingOut)
async def create_meeting(
    meeting: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["CEO", "Manager"]:
        raise HTTPException(403, "Only CEO/Manager can schedule meetings")
    import uuid
    room_id = str(uuid.uuid4())
    db_meeting = Meeting(
        title=meeting.title,
        description=meeting.description,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        organizer_id=current_user.id,
        room_id=room_id
    )
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    # Add attendees
    if meeting.attendee_ids:
        attendees = db.query(User).filter(User.id.in_(meeting.attendee_ids)).all()
        db_meeting.attendees = attendees
        db.commit()
    # Notify attendees
    for user in db_meeting.attendees:
        await manager.send_personal(user.id, {
            "type": "meeting_invite",
            "meeting": MeetingOut.model_validate(db_meeting).model_dump()
        })
    return db_meeting

@app.get("/api/meetings", response_model=List[MeetingOut])
async def list_meetings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Return meetings where user is organizer or attendee
    user_meetings = db.query(Meeting).filter(
        (Meeting.organizer_id == current_user.id) |
        (Meeting.attendees.any(User.id == current_user.id))
    ).all()
    return user_meetings

@app.post("/api/meetings/{meeting_id}/join_room")
async def join_meeting_room(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    # Check user is allowed (organizer or attendee)
    if current_user.id not in [u.id for u in meeting.attendees] and current_user.id != meeting.organizer_id:
        raise HTTPException(403, "Not authorized to join this meeting")
    manager.join_room(meeting.room_id, current_user.id)
    return {"room_id": meeting.room_id}

# --- WEBSOCKET ENDPOINT ---
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    # Optionally validate token here (via query param) – for simplicity we trust user_id
    await manager.connect(user_id, websocket)
    # Broadcast presence
    await manager.broadcast({"type": "presence", "user_id": user_id, "status": "online"})
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "call_offer":
                target = data.get("target")
                if target:
                    await manager.send_personal(target, {
                        "type": "call_offer",
                        "from": user_id,
                        "sdp": data.get("sdp")
                    })
            elif msg_type == "call_answer":
                target = data.get("target")
                if target:
                    await manager.send_personal(target, {
                        "type": "call_answer",
                        "from": user_id,
                        "sdp": data.get("sdp")
                    })
            elif msg_type == "ice_candidate":
                target = data.get("target")
                if target:
                    await manager.send_personal(target, {
                        "type": "ice_candidate",
                        "from": user_id,
                        "candidate": data.get("candidate")
                    })
            elif msg_type == "end_call":
                target = data.get("target")
                if target:
                    await manager.send_personal(target, {"type": "end_call", "from": user_id})
            elif msg_type == "meeting_chat":
                room_id = data.get("room_id")
                if room_id:
                    await manager.send_to_room(room_id, {
                        "type": "meeting_chat",
                        "from": user_id,
                        "message": data.get("message")
                    }, exclude_user=user_id)
            elif msg_type == "join_room":
                room_id = data.get("room_id")
                if room_id:
                    manager.join_room(room_id, user_id)
            elif msg_type == "leave_room":
                room_id = data.get("room_id")
                if room_id:
                    manager.leave_room(room_id, user_id)
            # else ignore

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast({"type": "presence", "user_id": user_id, "status": "offline"})
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(user_id)

# --- BROWSER LAUNCHER ---
def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)