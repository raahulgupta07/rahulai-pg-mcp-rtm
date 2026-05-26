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
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    if USERS_FILE.exists():
        users = json.loads(USERS_FILE.read_text())
        # Migration: the configured root account is always super_admin
        changed = False
        for u in users:
            if u["username"] == admin_user and u.get("role") != "super_admin":
                u["role"] = "super_admin"
                changed = True
        if changed:
            _save_users(users)
        return users
    # Create default super-admin from env vars (all other users created via UI)
    admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_name = os.getenv("ADMIN_DISPLAY_NAME", "Administrator")
    default_users = [
        {"id": 1, "username": admin_user, "password": _hash_password(admin_pass), "role": "super_admin", "display_name": admin_name},
    ]
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(default_users, indent=2))
    return default_users

def _save_users(users: list):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))

def authenticate_user(username: str, password: str) -> Optional[dict]:
    # 1. Local users first — keeps super_admin working even if LDAP is down
    users = _load_users()
    hashed = _hash_password(password)
    for u in users:
        if u["username"] == username and u["password"] == hashed:
            if u.get("disabled"):
                return None  # account disabled
            return {"id": u["id"], "username": u["username"], "role": u["role"], "display_name": u["display_name"]}
    # 2. Fall back to LDAP — try the user's home server first, then the rest
    ldap_cfg = load_ldap_config()
    servers = [s for s in ldap_cfg["servers"] if s.get("enabled")]
    if not servers:
        return None
    home_id = next((u.get("ldap_server") for u in users if u["username"] == username), None)
    ordered = sorted(servers, key=lambda s: 0 if s.get("id") == home_id else 1)
    for srv in ordered:
        ldap_user = ldap_authenticate(username, password, srv)
        if ldap_user:
            return _provision_ldap_user(ldap_user, srv["id"], ldap_cfg.get("merge_by_email", True))
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
    return [{
        "id": u["id"], "username": u["username"], "role": u["role"],
        "display_name": u["display_name"],
        "email": u.get("email", ""),
        "source": u.get("source", "local"),
        "ldap_username": u.get("ldap_username", ""),
        "ldap_server": u.get("ldap_server", ""),
        "disabled": u.get("disabled", False),
        "groups": u.get("groups", []),
    } for u in users]


# ════════════════════════════════════════════════════════════
# Groups & permissions (additive — layered on top of the base role)
# ════════════════════════════════════════════════════════════

GROUPS_FILE = Path(__file__).parent.parent / "data" / "groups.json"

# Capabilities a group can grant. Base role access is never reduced — groups
# only ADD. 'settings' / user-management stay super_admin-only (not grantable).
PERMISSION_CATALOG = ["rules", "analytics"]

# Permissions every role has by default (the floor — groups add on top).
ROLE_BASE_PERMISSIONS = {
    "super_admin": {"rules", "analytics"},
    "admin": {"rules"},
    "user": set(),
}


def load_groups() -> list:
    if GROUPS_FILE.exists():
        try:
            return json.loads(GROUPS_FILE.read_text())
        except Exception:
            return []
    return []


def save_groups(groups: list):
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GROUPS_FILE.write_text(json.dumps(groups, indent=2))


def list_groups() -> list:
    return load_groups()


def create_group(name: str, description: str = "", permissions: list = None,
                  ldap_group: str = "") -> dict:
    groups = load_groups()
    import uuid
    g = {
        "id": "grp-" + uuid.uuid4().hex[:8],
        "name": name.strip(),
        "description": description.strip(),
        "permissions": [p for p in (permissions or []) if p in PERMISSION_CATALOG],
        "ldap_group": ldap_group.strip(),
    }
    groups.append(g)
    save_groups(groups)
    return g


def update_group(group_id: str, name=None, description=None,
                 permissions=None, ldap_group=None) -> bool:
    groups = load_groups()
    for g in groups:
        if g["id"] == group_id:
            if name is not None:
                g["name"] = name.strip()
            if description is not None:
                g["description"] = description.strip()
            if permissions is not None:
                g["permissions"] = [p for p in permissions if p in PERMISSION_CATALOG]
            if ldap_group is not None:
                g["ldap_group"] = ldap_group.strip()
            save_groups(groups)
            return True
    return False


def delete_group(group_id: str) -> bool:
    groups = [g for g in load_groups() if g["id"] != group_id]
    save_groups(groups)
    # Drop the group from every user's membership
    users = _load_users()
    changed = False
    for u in users:
        if group_id in u.get("groups", []):
            u["groups"] = [gid for gid in u["groups"] if gid != group_id]
            changed = True
    if changed:
        _save_users(users)
    return True


def get_user_record(user_id: int) -> Optional[dict]:
    for u in _load_users():
        if u["id"] == user_id:
            return u
    return None


def set_user_groups(user_id: int, group_ids: list) -> bool:
    valid = {g["id"] for g in load_groups()}
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            u["groups"] = [gid for gid in group_ids if gid in valid]
            _save_users(users)
            return True
    return False


def effective_permissions(user_id: int) -> list:
    """Role-base permissions UNION the permissions of every group the user is in."""
    u = get_user_record(user_id)
    if not u:
        return []
    perms = set(ROLE_BASE_PERMISSIONS.get(u.get("role", "user"), set()))
    groups = {g["id"]: g for g in load_groups()}
    for gid in u.get("groups", []):
        g = groups.get(gid)
        if g:
            perms |= set(g.get("permissions", []))
    return sorted(perms)


def set_user_disabled(user_id: int, disabled: bool) -> bool:
    """Block / unblock a user from logging in (super_admin cannot be disabled)."""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            if u.get("role") == "super_admin":
                return False
            u["disabled"] = bool(disabled)
            _save_users(users)
            return True
    return False


def update_user_identity(user_id: int, email: str = None, ldap_username: str = None) -> bool:
    """Update a user's email and/or LDAP-username alias (admin merge controls)."""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            if email is not None:
                u["email"] = email.strip()
            if ldap_username is not None:
                if ldap_username.strip():
                    u["ldap_username"] = ldap_username.strip()
                else:
                    u.pop("ldap_username", None)
            _save_users(users)
            return True
    return False

def create_user(username: str, password: str, role: str = "user", display_name: str = "",
                email: str = "", groups: list = None) -> dict:
    users = _load_users()
    if any(u["username"] == username for u in users):
        raise ValueError(f"Username '{username}' already exists")
    new_id = max((u["id"] for u in users), default=0) + 1
    valid_groups = {g["id"] for g in load_groups()}
    new_user = {"id": new_id, "username": username, "password": _hash_password(password),
                "role": role, "display_name": display_name or username, "email": email.strip(),
                "groups": [g for g in (groups or []) if g in valid_groups]}
    users.append(new_user)
    _save_users(users)
    return {"id": new_id, "username": username, "role": role, "display_name": new_user["display_name"]}

def delete_user(user_id: int) -> bool:
    users = _load_users()
    users = [u for u in users if u["id"] != user_id]
    _save_users(users)
    return True

def update_user_password(user_id: int, new_password: str) -> bool:
    """Reset a user's password (admin action — no old password needed)."""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            u["password"] = _hash_password(new_password)
            _save_users(users)
            return True
    return False


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """Change a user's own password — verifies the current password first.
    LDAP accounts manage their password in the directory, not here."""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            if u.get("source") == "ldap":
                raise ValueError("LDAP accounts change their password in the directory")
            if u["password"] != _hash_password(old_password):
                raise ValueError("Current password is incorrect")
            u["password"] = _hash_password(new_password)
            _save_users(users)
            return True
    raise ValueError("User not found")

# ════════════════════════════════════════════════════════════
# LDAP / Active Directory authentication
# ════════════════════════════════════════════════════════════

LDAP_CONFIG_FILE = Path(__file__).parent.parent / "data" / "ldap_config.json"

# Per-server config template
DEFAULT_LDAP = {
    "id": "",
    "enabled": False,
    "label": "Company Directory",
    "host": "",
    "port": 389,
    "use_tls": False,
    "validate_cert": True,
    "app_dn": "",
    "app_password": "",
    "search_base": "",
    "attr_username": "uid",
    "attr_mail": "mail",
    "search_filter": "",
    "default_role": "user",
    "admin_group": "",
}

MAX_LDAP_SERVERS = 5


def _merge_server(s: dict) -> dict:
    """Merge one server dict over the per-server defaults; ensure it has an id."""
    import uuid
    m = dict(DEFAULT_LDAP)
    for k in DEFAULT_LDAP:
        if k in s:
            m[k] = s[k]
    m["port"] = int(m["port"] or 389)
    if not m.get("id"):
        m["id"] = "srv-" + uuid.uuid4().hex[:8]
    return m


def load_ldap_config() -> dict:
    """Load the multi-server LDAP config. Migrates the old single-server shape."""
    raw = {}
    if LDAP_CONFIG_FILE.exists():
        try:
            raw = json.loads(LDAP_CONFIG_FILE.read_text())
        except Exception:
            raw = {}
    if isinstance(raw.get("servers"), list):
        servers = [_merge_server(s) for s in raw["servers"]]
    elif raw.get("host") or "enabled" in raw:
        # Old single-server file → migrate into a one-element list
        servers = [_merge_server({**raw, "id": raw.get("id") or "srv-1"})]
    else:
        servers = []
    return {
        "merge_by_email": bool(raw.get("merge_by_email", True)),
        "servers": servers[:MAX_LDAP_SERVERS],
    }


def save_ldap_config(cfg: dict) -> dict:
    """Persist the multi-server LDAP config."""
    servers = [_merge_server(s) for s in (cfg.get("servers") or [])][:MAX_LDAP_SERVERS]
    out = {"merge_by_email": bool(cfg.get("merge_by_email", True)), "servers": servers}
    LDAP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LDAP_CONFIG_FILE.write_text(json.dumps(out, indent=2))
    return out


def _ldap_server(cfg: dict):
    """Build an ldap3 Server from config. get_info=NONE so we never validate
    requested attributes against the directory schema (e.g. memberOf)."""
    import ssl
    from ldap3 import Server, Tls, NONE
    port = int(cfg.get("port") or 389)
    use_ssl = port == 636
    tls = None
    if use_ssl or cfg.get("use_tls"):
        validate = ssl.CERT_REQUIRED if cfg.get("validate_cert", True) else ssl.CERT_NONE
        tls = Tls(validate=validate)
    return Server(cfg["host"], port=port, use_ssl=use_ssl, tls=tls, get_info=NONE)


def _ldap_connect(server, dn, password, cfg):
    """Open a connection, applying StartTLS when use_tls is set on a non-SSL port.
    check_names=False so requesting an attribute absent from the schema
    (e.g. memberOf on a minimal directory) does not raise."""
    from ldap3 import Connection
    conn = Connection(server, dn, password, auto_bind=False, check_names=False)
    if cfg.get("use_tls") and int(cfg.get("port") or 389) != 636:
        conn.open()
        conn.start_tls()
    return conn


def ldap_authenticate(username: str, password: str, cfg: dict) -> Optional[dict]:
    """Bind / search / rebind against the directory. Returns user info or None."""
    if not username or not password:
        return None
    try:
        from ldap3.utils.conv import escape_filter_chars
        server = _ldap_server(cfg)

        # 1. Service bind
        svc = _ldap_connect(server, cfg["app_dn"], cfg["app_password"], cfg)
        if not svc.bind():
            return None

        # 2. Search for the user
        safe = escape_filter_chars(username)
        base = f"({cfg['attr_username']}={safe})"
        extra = (cfg.get("search_filter") or "").strip()
        flt = f"(&{base}{extra})" if extra else base
        attrs = [cfg["attr_username"], cfg.get("attr_mail", "mail"), "memberOf", "cn"]
        svc.search(cfg["search_base"], flt, attributes=attrs)
        if not svc.entries:
            svc.unbind()
            return None
        entry = svc.entries[0]
        user_dn = entry.entry_dn

        def _val(attr):
            try:
                return entry[attr].value
            except Exception:
                return None

        mail = _val(cfg.get("attr_mail", "mail")) or ""
        cn = _val("cn") or username
        groups = _val("memberOf") or []
        if not isinstance(groups, list):
            groups = [groups]
        svc.unbind()

        # 3. Rebind as the user (verifies the password)
        user_conn = _ldap_connect(server, user_dn, password, cfg)
        if not user_conn.bind():
            return None
        user_conn.unbind()

        # Role: admin if in the admin group, else the default
        role = cfg.get("default_role", "user")
        admin_grp = (cfg.get("admin_group") or "").strip().lower()
        if admin_grp:
            for g in groups:
                if admin_grp in str(g).lower():
                    role = "admin"
                    break

        return {
            "username": username,
            "display_name": str(cn) if not isinstance(cn, list) else str(cn[0]),
            "mail": str(mail) if not isinstance(mail, list) else (str(mail[0]) if mail else ""),
            "role": role,
            "ldap_groups": [str(g) for g in groups],   # memberOf — for group sync
        }
    except Exception:
        return None


def ldap_test(cfg: dict) -> dict:
    """Test the service-account bind. Returns {ok, message, latency_ms}."""
    import time
    if not cfg.get("host"):
        return {"ok": False, "message": "No LDAP host configured"}
    if not cfg.get("app_dn"):
        return {"ok": False, "message": "No service-account DN configured"}
    t0 = time.time()
    try:
        server = _ldap_server(cfg)
        conn = _ldap_connect(server, cfg["app_dn"], cfg["app_password"], cfg)
        ok = conn.bind()
        latency = int((time.time() - t0) * 1000)
        if ok:
            conn.unbind()
            return {"ok": True, "message": "Service bind successful", "latency_ms": latency}
        return {"ok": False, "message": "Service bind failed — check DN / password", "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "message": str(e)[:200]}


def _sync_ldap_groups(rec: dict, ldap_groups: list):
    """Sync a user's RTM group membership from their LDAP memberOf list.
    Directory is the source of truth — only runs if RTM groups have an
    ldap_group mapping configured (otherwise membership is left untouched)."""
    rtm_groups = load_groups()
    if not any((g.get("ldap_group") or "").strip() for g in rtm_groups):
        return
    member = [str(m).lower() for m in (ldap_groups or [])]
    matched = []
    for g in rtm_groups:
        lg = (g.get("ldap_group") or "").strip().lower()
        if lg and any(lg in m for m in member):
            matched.append(g["id"])
    rec["groups"] = matched


def _provision_ldap_user(ldap_user: dict, server_id: str = "", merge_by_email: bool = True) -> dict:
    """Find or create a local record for an LDAP-authenticated user, sync the
    user's groups from LDAP, and remember the home server.
    Merge order: (1) username / admin-set alias, (2) email match (super_admin
    accounts are never auto-merged). LDAP passwords are never stored."""
    users = _load_users()
    target = ldap_user["username"]
    mail = (ldap_user.get("mail") or "").strip().lower()
    rec = None

    # 1. Match on local username OR an admin-set LDAP-username alias
    for u in users:
        if u["username"] == target or u.get("ldap_username") == target:
            rec = u
            break

    # 2. Auto-merge by email — never into a super_admin account
    if rec is None and merge_by_email and mail:
        for u in users:
            if u.get("role") == "super_admin":
                continue
            if (u.get("email") or "").strip().lower() == mail:
                rec = u
                rec["ldap_username"] = target  # stamp for a direct match next time
                break

    # 3. No match → create a new account
    if rec is None:
        import uuid
        new_id = max((u["id"] for u in users), default=0) + 1
        rec = {
            "id": new_id,
            "username": ldap_user["username"],
            "password": _hash_password(uuid.uuid4().hex),  # unusable placeholder
            "role": ldap_user.get("role", "user"),
            "display_name": ldap_user.get("display_name") or ldap_user["username"],
            "email": ldap_user.get("mail", ""),
            "source": "ldap",
            "groups": [],
        }
        users.append(rec)

    if server_id:
        rec["ldap_server"] = server_id
    _sync_ldap_groups(rec, ldap_user.get("ldap_groups"))
    _save_users(users)

    if rec.get("disabled"):
        return None  # account disabled — block login
    return {"id": rec["id"], "username": rec["username"], "role": rec["role"], "display_name": rec["display_name"]}


def get_user_prefs(user_id: int) -> dict:
    """Return per-user UI preferences (theme/appearance)."""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            return u.get("prefs", {})
    return {}

def set_user_prefs(user_id: int, prefs: dict) -> bool:
    """Persist per-user UI preferences."""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            u["prefs"] = prefs
            _save_users(users)
            return True
    return False
