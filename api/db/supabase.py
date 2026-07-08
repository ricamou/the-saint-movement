from api.core.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, HTTP_TIMEOUT
from api.core.http_client import request_json

MEMORY = {
    "companies": [],
    "users": [],
    "suppliers": [],
    "products": [],
    "inventory": [],
    "orders": [],
    "listings": [],
    "oauth_tokens": [],
    "logs": [],
    "webhooks": [],
    "sync_jobs": [],
}

def configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)

def mode() -> str:
    return "supabase" if configured() else "memory"

def _headers(prefer="return=representation"):
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }

def rest(method: str, path: str, payload=None, prefer="return=representation"):
    if not configured():
        return {"success": False, "mode": "memory", "status_code": 0, "data": [], "error": "Supabase não configurado"}
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    result = request_json(method, url, _headers(prefer), payload, timeout=HTTP_TIMEOUT)
    result["mode"] = "supabase"
    return result

async def select(table: str, query: str = "select=*"):
    if not configured():
        return {"success": True, "mode": "memory", "data": MEMORY.get(table, [])}
    result = rest("GET", f"{table}?{query}")
    if not isinstance(result.get("data"), list):
        result["data"] = []
    return result

async def insert(table: str, payload):
    if not configured():
        if isinstance(payload, list):
            MEMORY.setdefault(table, []).extend(payload)
        else:
            MEMORY.setdefault(table, []).append(payload)
        return {"success": True, "mode": "memory", "data": payload}
    return rest("POST", table, payload)

async def upsert(table: str, payload, conflict="id"):
    if not configured():
        values = payload if isinstance(payload, list) else [payload]
        items = MEMORY.setdefault(table, [])
        for value in values:
            found = False
            for i, current in enumerate(items):
                if str(current.get(conflict)) == str(value.get(conflict)):
                    items[i] = {**current, **value}
                    found = True
                    break
            if not found:
                items.append(value)
        return {"success": True, "mode": "memory", "data": payload}
    return rest("POST", f"{table}?on_conflict={conflict}", payload, "resolution=merge-duplicates,return=representation")