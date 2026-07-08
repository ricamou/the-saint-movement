from datetime import datetime
import uuid
from api.core.config import DEFAULT_COMPANY_ID, DEFAULT_SUPPLIER_ID
from api.repositories import base
from api.services.pricing_service import calculate_sale_price
from api.services.log_service import log

async def list_products():
    return await base.list_rows("products", "select=*")

async def create_product(data: dict):
    cost = float(data.get("cost_price") or 0)
    stock = int(float(data.get("stock") or 0))
    pricing = calculate_sale_price(cost)
    supplier = {
        "id": DEFAULT_SUPPLIER_ID,
        "company_id": DEFAULT_COMPANY_ID,
        "name": "Fornecedor Manual",
        "type": "manual",
        "status": "active",
        "config": {},
    }
    product = {
        "id": data.get("id") or str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "supplier_id": DEFAULT_SUPPLIER_ID,
        "sku": data.get("sku") or f"SKU-{int(datetime.utcnow().timestamp())}",
        "name": data.get("name") or "Produto",
        "brand": data.get("brand") or "CommerceHub",
        "category": data.get("category") or "Produto",
        "description": data.get("description") or "",
        "cost_price": cost,
        "sale_price": pricing["sale_price"],
        "stock": stock,
        "status": "active",
        "raw_data": {},
    }
    inventory = {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product["id"],
        "sku": product["sku"],
        "movement_type": "set",
        "quantity": stock,
        "previous_stock": 0,
        "new_stock": stock,
        "source": "manual",
        "created_at": datetime.utcnow().isoformat(),
    }

    supplier_result = await base.save("suppliers", supplier)
    product_result = await base.save("products", product)
    inventory_result = await base.create("inventory", inventory)
    await log("product_created", "Produto criado", {"sku": product["sku"]})

    return {
        "success": True,
        "supplier": supplier_result,
        "product": product_result,
        "inventory": inventory_result,
        "product_payload": product,
    }

async def seed():
    return await create_product({
        "sku": "TESTE-ML-001",
        "name": "Produto Teste CommerceHub",
        "brand": "CommerceHub",
        "category": "Produto",
        "description": "Produto novo, pronto para venda no Mercado Livre.",
        "cost_price": 20,
        "stock": 5,
    })