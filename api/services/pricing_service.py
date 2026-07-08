def calculate_sale_price(cost_price, margin_percent=35, fixed_cost=6, commission_percent=16):
    cost = float(cost_price or 0)
    margin = float(margin_percent or 0) / 100
    commission = float(commission_percent or 0) / 100
    price = round((cost + fixed_cost + (cost * margin)) / max(0.01, 1 - commission), 2)
    profit = round(price - cost - fixed_cost - (price * commission), 2)
    return {
        "cost_price": cost,
        "sale_price": price,
        "profit": profit,
        "margin_percent": round((profit / price) * 100, 2) if price else 0,
    }