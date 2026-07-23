import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database.connection import engine, Base, SessionLocal
from database.migrate import run_migrations
from routes.auth import router as auth_router
from routes.contest import router as contest_router
from routes.submission import router as submission_router
from routes.evaluation import router as evaluation_router
from routes.leaderboard import router as leaderboard_router
from routes.admin import router as admin_router, login_router as admin_login_router
from routes.session import router as session_router

# Register models to ensure they are loaded into Base metadata
import models.challenge
import models.submission
import models.evaluation
import models.user
import models.session
import models.chat_message


def seed_admin():
    db: Session = SessionLocal()
    try:
        from models.user import User
        from routes.auth import hash_password

        admin_exists = db.query(User).filter(User.email == "admin@1code.com").first()
        if not admin_exists:
            db.add(
                User(
                    name="Admin User",
                    email="admin@1code.com",
                    password_hash=hash_password("adminpassword"),
                    is_admin=True,
                )
            )
            db.commit()
    finally:
        db.close()


# Create tables in PostgreSQL and apply column migrations
Base.metadata.create_all(bind=engine)
run_migrations()
seed_admin()

app = FastAPI(title="1Code API", version="1.0.0")

frontend_origins = [
    os.getenv("FRONTEND_ORIGIN", "http://localhost:5500"),
    "http://localhost:5500",
    "http://127.0.0.1:5500"
]
# Remove duplicates
frontend_origins = list(set(frontend_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

studio_dir = Path(__file__).resolve().parent.parent / "studio"
if studio_dir.exists():
    app.mount("/studio", StaticFiles(directory=str(studio_dir), html=True), name="studio")

app.include_router(auth_router)
app.include_router(contest_router)
app.include_router(submission_router)
app.include_router(evaluation_router)
app.include_router(leaderboard_router)
app.include_router(admin_login_router)
app.include_router(admin_router)
app.include_router(session_router)