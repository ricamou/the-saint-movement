from datetime import datetime
import uuid
from api.core.config import DEFAULT_COMPANY_ID
from api.repositories import base

async def log(event_type: str, message: str, payload=None):
    item = {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "event_type": event_type,
        "message": message,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    return await base.create("logs", item)