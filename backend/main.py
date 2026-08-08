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
from routes.team import router as team_router
from routes.team_ws import router as team_ws_router
from routes.profile import router as profile_router
from routes.stats import router as stats_router

# Register models to ensure they are loaded into Base metadata
import models.challenge
import models.submission
import models.evaluation
import models.user
import models.session
import models.chat_message
import models.team
import models.team_member
import models.user_activity
import models.site_visit



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

default_origins = [

    "http://localhost:5500",

    "http://127.0.0.1:5500",

    "http://localhost:3000",

    "http://127.0.0.1:3000",

    "null",  # Allows file:// protocol (browser sends Origin: null)

    "https://1code-swart.vercel.app",

    "https://1codeadmin-124as535w-vebhav-sharma-s-projects.vercel.app",

    "https://about-1code.onrender.com",

    "https://1codeadmin.vercel.app",

]

# FRONTEND_ORIGIN can hold a comma-separated list for extra/preview deploy URLs,
# e.g. "https://1code-swart.vercel.app,https://1codeadmin-xxxx.vercel.app"
env_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGIN", "").split(",")
    if origin.strip()
]

frontend_origins = list(set(default_origins + env_origins))

# Vercel gives every preview deployment a unique auto-generated URL
# (e.g. 1code-5fh6hadyn-vebhav-sharma-s-projects.vercel.app) that changes
# on every push. Rather than adding each one by hand, trust any subdomain
# under these two Vercel projects via regex, in addition to the fixed list above.
frontend_origin_regex = r"^https:\/\/(1code|1codeadmin)(-[a-z0-9]+)?-vebhav-sharma-s-projects\.vercel\.app$|^https:\/\/1code-swart\.vercel\.app$"

print(f"CORS allowed origins: {frontend_origins}")
print(f"CORS allowed origin regex: {frontend_origin_regex}")

from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=frontend_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable response compression for JSON/HTML responses >= 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)


# Custom StaticFiles subclass to add Cache-Control headers (max-age=3600)
class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response


studio_dir = Path(__file__).resolve().parent.parent / "studio"
if studio_dir.exists():
    app.mount("/studio", CachedStaticFiles(directory=str(studio_dir), html=True), name="studio")

uploads_dir = Path(__file__).resolve().parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", CachedStaticFiles(directory=str(uploads_dir)), name="uploads")


# Note on Render Free-Tier Cold Starts:
# Free-tier compute instances on Render spin down after 15 minutes of inactivity,
# causing an initial 30-50s cold-start latency on the first request while the container boots.
# Code-level caching cannot prevent cold starts. To keep the instance warm, set up an external
# uptime ping service (e.g., UptimeRobot) targeting this lightweight /health endpoint every ~10 mins.
@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(contest_router)
app.include_router(submission_router)
app.include_router(evaluation_router)
app.include_router(leaderboard_router)
app.include_router(admin_login_router)
app.include_router(admin_router)
app.include_router(session_router)
app.include_router(team_router)
app.include_router(team_ws_router)
app.include_router(profile_router)
app.include_router(stats_router)