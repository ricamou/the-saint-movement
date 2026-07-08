from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime
import json, uuid

from api.core.config import APP_VERSION, DEFAULT_COMPANY_ID
from api.db import supabase
from api.repositories import base
from api.services.product_service import create_product, list_products, seed
from api.services.listing_service import build_mercadolivre_payload
from api.services.mercadolivre_service import build_auth_url, exchange_code, request_ml
from api.ui.templates import shell, btn, money

app = FastAPI(title="CommerceHub Enterprise V3", version=APP_VERSION)

def system_state():
    return {
        "version": APP_VERSION,
        "mode": supabase.mode(),
        "supabase_configured": supabase.configured(),
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "commercehub", **system_state()}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    products = await list_products()
    count = len(products.get("data") or [])
    content = f"""
<div class='grid'>
<div class='metric'><span>Sistema</span><strong>OK</strong></div>
<div class='metric'><span>Banco</span><strong>{supabase.mode().upper()}</strong></div>
<div class='metric'><span>Produtos</span><strong>{count}</strong></div>
<div class='metric'><span>Versão</span><strong>V3</strong></div>
</div>
<div class='card'><h2>CommerceHub Enterprise V3</h2><p>Base limpa e profissional para começar vendas no Mercado Livre.</p>
{btn('/setup','Setup')}{btn('/new-product','Cadastrar Produto')}{btn('/mercado-livre','Mercado Livre')}{btn('/sell-flow','Fluxo de Venda')}</div>
"""
    return HTMLResponse(shell("Dashboard", content))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias():
    return await dashboard()

@app.get("/setup", response_class=HTMLResponse)
def setup_page():
    content = f"""
<div class='card'><h2>Setup</h2><pre>{json.dumps(system_state(), ensure_ascii=False, indent=2)}</pre>
{btn('/api/backend/health','Backend Health')}{btn('/api/foundation/seed','Criar dados iniciais')}{btn('/new-product','Novo produto')}</div>
<div class='card'><h2>Passos</h2><ol><li>Rodar supabase_schema.sql no Supabase.</li><li>Clicar em Criar dados iniciais.</li><li>Conectar Mercado Livre.</li><li>Cadastrar produto e gerar preview.</li></ol></div>
"""
    return HTMLResponse(shell("Setup", content))

@app.get("/api/backend/health")
async def backend_health():
    tables = {}
    for table in ["companies", "suppliers", "products", "inventory", "orders", "listings", "oauth_tokens", "logs", "webhooks"]:
        res = await base.list_rows(table, "select=*&limit=1")
        tables[table] = {"success": res.get("success"), "mode": res.get("mode"), "rows": len(res.get("data", [])), "error": str(res.get("error", ""))[:180]}
    return {"success": True, **system_state(), "tables": tables}

@app.get("/api/foundation/status")
def foundation_status():
    return {"success": True, **system_state(), "tables": list(supabase.MEMORY.keys()), "next": "/api/foundation/seed"}

@app.get("/api/foundation/seed")
@app.post("/api/foundation/seed")
async def foundation_seed():
    company = {"id": DEFAULT_COMPANY_ID, "name": "CommerceHub", "document": "00000000000000", "plan": "enterprise", "status": "active"}
    company_result = await base.save("companies", company)
    product_result = await seed()
    return {"success": True, "company": company_result, "seed": product_result}

@app.get("/new-product", response_class=HTMLResponse)
def new_product_page():
    content = """
<div class='card'><h2>Cadastrar produto</h2>
<form method='post' action='/api/products/create'>
<label>SKU</label><input name='sku' value='PROD-001'>
<label>Nome</label><input name='name' value='Produto Teste CommerceHub'>
<label>Marca</label><input name='brand' value='CommerceHub'>
<label>Categoria</label><input name='category' value='Produto'>
<label>Custo</label><input name='cost_price' value='20'>
<label>Estoque</label><input name='stock' value='5'>
<label>Descrição</label><textarea name='description'>Produto novo, pronto para venda no Mercado Livre.</textarea>
<button type='submit'>Salvar produto</button>
</form></div>
"""
    return HTMLResponse(shell("Novo Produto", content))

@app.post("/api/products/create")
async def create_product_form(request: Request):
    form = await request.form()
    data = {k: form.get(k) for k in ["sku", "name", "brand", "category", "cost_price", "stock", "description"]}
    await create_product(data)
    return RedirectResponse("/products", status_code=303)

@app.get("/products", response_class=HTMLResponse)
async def products_page():
    res = await list_products()
    rows = ""
    for p in res.get("data", []):
        rows += f"<tr><td>{p.get('sku')}</td><td>{p.get('name')}</td><td>{p.get('brand')}</td><td>{p.get('stock')}</td><td>{money(p.get('sale_price'))}</td><td>{btn('/api/listings/preview/'+str(p.get('id')),'Preview')}</td></tr>"
    if not rows:
        rows = "<tr><td colspan='6'>Nenhum produto cadastrado.</td></tr>"
    content = f"<div class='card'><table><tr><th>SKU</th><th>Nome</th><th>Marca</th><th>Estoque</th><th>Preço</th><th>Ação</th></tr>{rows}</table>{btn('/new-product','Novo Produto')}</div>"
    return HTMLResponse(shell("Produtos", content))

@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page():
    res = await base.list_rows("suppliers", "select=*")
    rows = "".join([f"<tr><td>{s.get('id')}</td><td>{s.get('name')}</td><td>{s.get('type')}</td><td>{s.get('status')}</td></tr>" for s in res.get("data", [])])
    if not rows:
        rows = "<tr><td colspan='4'>Nenhum fornecedor cadastrado.</td></tr>"
    return HTMLResponse(shell("Fornecedores", f"<div class='card'><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table></div>"))

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page():
    res = await base.list_rows("inventory", "select=*")
    rows = "".join([f"<tr><td>{i.get('sku')}</td><td>{i.get('movement_type')}</td><td>{i.get('quantity')}</td><td>{i.get('new_stock')}</td></tr>" for i in res.get("data", [])])
    if not rows:
        rows = "<tr><td colspan='4'>Nenhum movimento de estoque.</td></tr>"
    return HTMLResponse(shell("Estoque", f"<div class='card'><table><tr><th>SKU</th><th>Movimento</th><th>Qtd</th><th>Novo estoque</th></tr>{rows}</table></div>"))

@app.get("/mercado-livre", response_class=HTMLResponse)
async def mercado_livre_page():
    token = await base.list_rows("oauth_tokens", "select=*&marketplace=eq.mercado_livre&limit=1")
    connected = bool(token.get("data"))
    content = f"<div class='card'><h2>Mercado Livre</h2><p>Conectado: <b>{connected}</b></p>{btn(build_auth_url(),'Conectar Mercado Livre')}{btn('/api/mercadolivre/me','Testar conta')}{btn('/api/ml/items','Anúncios')}{btn('/api/ml/orders','Pedidos')}</div>"
    return HTMLResponse(shell("Mercado Livre", content))

@app.get("/mercadolivre/callback", response_class=HTMLResponse)
async def mercadolivre_callback(code: str = ""):
    result = await exchange_code(code)
    content = f"<div class='card'><h2>OAuth Mercado Livre</h2><pre>{json.dumps(result, ensure_ascii=False, indent=2)}</pre>{btn('/mercado-livre','Voltar')}</div>"
    return HTMLResponse(shell("Callback Mercado Livre", content))

@app.get("/api/mercadolivre/me")
async def ml_me():
    return await request_ml("/users/me")

@app.get("/api/ml/items")
async def ml_items():
    me = await request_ml("/users/me")
    user_id = (me.get("data") or {}).get("id")
    if not user_id:
        return {"success": False, "error": "Não foi possível identificar User ID", "me": me}
    return await request_ml(f"/users/{user_id}/items/search", params={"limit": 20})

@app.get("/api/ml/orders")
async def ml_orders():
    me = await request_ml("/users/me")
    user_id = (me.get("data") or {}).get("id")
    if not user_id:
        return {"success": False, "error": "Não foi possível identificar User ID", "me": me}
    return await request_ml("/orders/search", params={"seller": user_id, "limit": 20})

@app.get("/api/listings/preview/{product_id}")
async def listing_preview(product_id: str, category_id: str = "MLBXXXX"):
    res = await list_products()
    product = next((p for p in res.get("data", []) if str(p.get("id")) == str(product_id)), None)
    if not product:
        return {"success": False, "error": "Produto não encontrado"}
    return {"success": True, "product": product, "payload": build_mercadolivre_payload(product, category_id)}

@app.post("/api/listings/publish/{product_id}")
async def listing_publish(product_id: str, category_id: str = "MLBXXXX"):
    preview = await listing_preview(product_id, category_id)
    if not preview.get("success"):
        return preview
    result = await request_ml("/items", "POST", preview["payload"])
    listing = {
        "id": str(uuid.uuid4()),
        "company_id": DEFAULT_COMPANY_ID,
        "product_id": product_id,
        "marketplace": "mercado_livre",
        "external_id": (result.get("data") or {}).get("id"),
        "status": "published" if result.get("success") else "error",
        "payload": result,
        "created_at": datetime.utcnow().isoformat(),
    }
    await base.create("listings", listing)
    return {"success": result.get("success"), "result": result}

@app.get("/sell-flow", response_class=HTMLResponse)
def sell_flow_page():
    content = f"<div class='card'><h2>Fluxo de venda</h2><ol><li>Setup e banco.</li><li>Conectar Mercado Livre.</li><li>Cadastrar produto.</li><li>Gerar preview.</li><li>Publicar anúncio.</li><li>Acompanhar pedidos.</li></ol>{btn('/setup','Setup')}{btn('/mercado-livre','Mercado Livre')}{btn('/new-product','Novo Produto')}{btn('/products','Produtos')}</div>"
    return HTMLResponse(shell("Fluxo de Venda", content))

@app.get("/api/routes")
def routes():
    return {"success": True, "routes": sorted([getattr(r, "path", "") for r in app.routes if getattr(r, "path", "")])}

@app.get("/favicon.ico")
def favicon():
    return {"ok": True}