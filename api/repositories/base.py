from api.db import supabase

async def list_rows(table: str, query: str = "select=*"):
    return await supabase.select(table, query)

async def save(table: str, payload, conflict: str = "id"):
    return await supabase.upsert(table, payload, conflict)

async def create(table: str, payload):
    return await supabase.insert(table, payload)