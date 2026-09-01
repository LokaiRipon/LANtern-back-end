from typing import List
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db
from connection_manager import manager

# Create database tables automatically when starting the backend
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LAN Office Messaging Backend")

# --- REAL-TIME WEBSOCKET ROUTE ---

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Keeps the WebSocket connection active and listening
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)

# --- INTERNAL MAIL ENDPOINTS ---

@app.post("/api/mail", response_model=schemas.MailResponse)
async def send_mail(mail_data: schemas.MailCreate, db: Session = Depends(get_db)):
    db_mail = models.Mail(**mail_data.model_dump())
    db.add(db_mail)
    db.commit()
    db.refresh(db_mail)

    # Push instant notification to recipient if connected to the LAN
    await manager.send_personal_message(
        {
            "type": "new_mail",
            "sender": db_mail.sender,
            "subject": db_mail.subject,
            "id": db_mail.id
        },
        user_id=db_mail.recipient # type: ignore
    )

    return db_mail

@app.get("/api/mail/{user_id}", response_model=List[schemas.MailResponse])
def get_user_inbox(user_id: str, db: Session = Depends(get_db)):
    return db.query(models.Mail).filter(models.Mail.recipient == user_id).all()

# --- PUBLIC ADDRESS (PA) BROADCAST ENDPOINTS ---

@app.post("/api/broadcast", response_model=schemas.BroadcastResponse)
async def create_broadcast(broadcast_data: schemas.BroadcastCreate, db: Session = Depends(get_db)):
    db_broadcast = models.Broadcast(**broadcast_data.model_dump())
    db.add(db_broadcast)
    db.commit()
    db.refresh(db_broadcast)

    # Instantly stream PA message across every connected office machine
    await manager.broadcast({
        "type": "pa_announcement",
        "sender": db_broadcast.sender,
        "title": db_broadcast.title,
        "message": db_broadcast.message,
        "priority": db_broadcast.priority
    })

    return db_broadcast

@app.get("/api/broadcast", response_model=List[schemas.BroadcastResponse])
def get_all_broadcasts(db: Session = Depends(get_db)):
    return db.query(models.Broadcast).order_by(models.Broadcast.timestamp.desc()).all()