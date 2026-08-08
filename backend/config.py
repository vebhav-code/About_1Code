import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


DATABASE_URL = get_required_env("DATABASE_URL")
GEMINI_API_KEY = get_required_env("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ADMIN_KEY = get_required_env("ADMIN_KEY")
print(f"ADMIN_KEY loaded: {bool(ADMIN_KEY)}")

# Optional WebRTC TURN server credentials for cross-network / firewall traversal
TURN_URL = os.getenv("TURN_URL", "")
TURN_USERNAME = os.getenv("TURN_USERNAME", "")
TURN_CREDENTIAL = os.getenv("TURN_CREDENTIAL", "")