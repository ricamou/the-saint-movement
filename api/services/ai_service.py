def optimize_listing(product: dict):
    brand = product.get("brand") or "CommerceHub"
    name = product.get("name") or "Produto"
    category = product.get("category") or ""
    title = " ".join(f"{brand} {name} {category}".split())[:60]
    description = product.get("description") or f"{name} novo, com envio rápido e pronto para venda."
    return {
        "title": title,
        "description": description,
        "seo_score": 100 if len(title) >= 20 else 80,
    }