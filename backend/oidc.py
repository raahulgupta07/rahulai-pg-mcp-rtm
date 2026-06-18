"""Multi-provider OIDC / OAuth2 SSO (Keycloak, Google, Microsoft, …).

Protocol only — discovery, authorize URL, code exchange, claim extraction.
User provisioning lives in auth.provision_oidc_user. No new heavy deps:
discovery/token via `requests`, id_token decoded as a trusted back-channel
JWT (obtained server→provider over TLS). Config: data/oidc_config.json.
"""
import os
import json
import base64
from pathlib import Path
from urllib.parse import urlencode

import requests

OIDC_FILE = Path(__file__).parent.parent / "data" / "oidc_config.json"
_DISCOVERY: dict = {}


def default_config() -> dict:
    return {"enabled": False, "merge_by_email": True, "providers": []}


def load_oidc_config() -> dict:
    if OIDC_FILE.exists():
        try:
            return {**default_config(), **json.loads(OIDC_FILE.read_text())}
        except Exception:
            pass
    return default_config()


def save_oidc_config(cfg: dict) -> bool:
    OIDC_FILE.parent.mkdir(parents=True, exist_ok=True)
    OIDC_FILE.write_text(json.dumps(cfg, indent=2))
    return True


def enabled_providers() -> list:
    cfg = load_oidc_config()
    if not cfg.get("enabled"):
        return []
    return [p for p in cfg.get("providers", []) if p.get("enabled") and p.get("issuer") and p.get("client_id")]


def get_provider(pid: str) -> dict | None:
    return next((p for p in enabled_providers() if p.get("id") == pid), None)


def public_providers() -> list:
    """Minimal list for the login page — no secrets."""
    return [{"id": p["id"], "name": p.get("name") or p["id"]} for p in enabled_providers()]


def discover(issuer: str) -> dict:
    issuer = (issuer or "").rstrip("/")
    if issuer in _DISCOVERY:
        return _DISCOVERY[issuer]
    doc = requests.get(issuer + "/.well-known/openid-configuration", timeout=10).json()
    _DISCOVERY[issuer] = doc
    return doc


def authorize_url(provider: dict, redirect_uri: str, state: str) -> str:
    doc = discover(provider["issuer"])
    q = urlencode({
        "client_id": provider["client_id"],
        "response_type": "code",
        "scope": provider.get("scopes") or "openid email profile",
        "redirect_uri": redirect_uri,
        "state": state,
    })
    return doc["authorization_endpoint"] + "?" + q


def exchange_code(provider: dict, code: str, redirect_uri: str) -> dict:
    doc = discover(provider["issuer"])
    r = requests.post(doc["token_endpoint"], data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": provider["client_id"],
        "client_secret": provider.get("client_secret", ""),
    }, timeout=10)
    r.raise_for_status()
    return r.json()


def _decode_jwt_payload(tok: str) -> dict:
    try:
        part = tok.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


def claims_from_token(provider: dict, token: dict) -> dict:
    """id_token (trusted back-channel) merged with userinfo for completeness."""
    claims = _decode_jwt_payload(token.get("id_token", "")) if token.get("id_token") else {}
    if token.get("access_token"):
        try:
            doc = discover(provider["issuer"])
            ep = doc.get("userinfo_endpoint")
            if ep:
                ui = requests.get(ep, headers={"Authorization": "Bearer " + token["access_token"]}, timeout=10).json()
                claims = {**ui, **claims}
        except Exception:
            pass
    return claims


def _nested(claims: dict, path: str):
    cur = claims
    for part in (path or "").split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def user_info_from_claims(provider: dict, claims: dict) -> dict:
    """Normalize provider claims → the dict auth.provision_oidc_user expects."""
    username = claims.get("preferred_username") or claims.get("email") or claims.get("sub")
    mail = claims.get("email", "") or ""
    name = claims.get("name") or claims.get("preferred_username") or username
    roles = _nested(claims, provider.get("roles_claim") or "roles") or []
    if isinstance(roles, str):
        roles = [roles]
    groups = _nested(claims, provider.get("groups_claim") or "groups") or []
    if isinstance(groups, str):
        groups = [groups]
    admin_roles = [str(r).lower() for r in (provider.get("admin_roles") or [])]
    role = provider.get("default_role") or "user"
    if admin_roles and any(str(r).lower() in admin_roles for r in roles):
        role = "admin"
    return {"username": username, "mail": mail, "display_name": name, "role": role,
            "groups": [str(g) for g in groups]}
