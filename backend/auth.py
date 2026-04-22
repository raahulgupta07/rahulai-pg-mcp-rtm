import os, hashlib, json
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "rtm-command-center-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# Simple user store in a JSON file
USERS_FILE = Path(__file__).parent.parent / "data" / "users.json"

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _load_users() -> list:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    # Create default admin user
    default_users = [
        {"id": 1, "username": "admin", "password": _hash_password("admin123"), "role": "admin", "display_name": "Administrator"},
        {"id": 2, "username": "user", "password": _hash_password("user123"), "role": "user", "display_name": "Analyst"},
    ]
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(default_users, indent=2))
    return default_users

def _save_users(users: list):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))

def authenticate_user(username: str, password: str) -> Optional[dict]:
    users = _load_users()
    hashed = _hash_password(password)
    for u in users:
        if u["username"] == username and u["password"] == hashed:
            return {"id": u["id"], "username": u["username"], "role": u["role"], "display_name": u["display_name"]}
    return None

def create_token(user: dict) -> str:
    import jwt as pyjwt
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    import jwt as pyjwt
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"user_id": payload["user_id"], "username": payload["username"], "role": payload["role"]}
    except:
        return None

def get_current_user(authorization: str = None) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    return verify_token(token)

def list_users() -> list:
    users = _load_users()
    return [{"id": u["id"], "username": u["username"], "role": u["role"], "display_name": u["display_name"]} for u in users]

def create_user(username: str, password: str, role: str = "user", display_name: str = "") -> dict:
    users = _load_users()
    if any(u["username"] == username for u in users):
        raise ValueError(f"Username '{username}' already exists")
    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {"id": new_id, "username": username, "password": _hash_password(password), "role": role, "display_name": display_name or username}
    users.append(new_user)
    _save_users(users)
    return {"id": new_id, "username": username, "role": role, "display_name": new_user["display_name"]}

def delete_user(user_id: int) -> bool:
    users = _load_users()
    users = [u for u in users if u["id"] != user_id]
    _save_users(users)
    return True

def update_user_password(user_id: int, new_password: str) -> bool:
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            u["password"] = _hash_password(new_password)
            _save_users(users)
            return True
    return False
