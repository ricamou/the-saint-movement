from api.services.ai_service import optimize_listing
from api.services.pricing_service import calculate_sale_price

def build_mercadolivre_payload(product: dict, category_id: str = "MLBXXXX"):
    ai = optimize_listing(product)
    sale_price = product.get("sale_price") or calculate_sale_price(product.get("cost_price", 0))["sale_price"]
    return {
        "title": ai["title"],
        "category_id": category_id,
        "price": float(sale_price),
        "currency_id": "BRL",
        "available_quantity": int(product.get("stock") or 1),
        "buying_mode": "buy_it_now",
        "condition": "new",
        "listing_type_id": "gold_special",
        "description": {"plain_text": ai["description"]},
        "attributes": [
            {"id": "BRAND", "value_name": product.get("brand") or "CommerceHub"},
            {"id": "MODEL", "value_name": product.get("sku") or "CH-001"},
        ],
    }