from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import urlencode
from datetime import datetime
import os, json, uuid, urllib.request, urllib.error

app = FastAPI(title='CommerceHub V2 ML Pro', version='v2-ml-pro')

def env(name, default=''):
    v = os.getenv(name, default)
    return '' if v is None else str(v).strip().strip('"').strip("'")

APP_URL = env('APP_URL','https://commercehub-vercel-mvp.vercel.app')
SUPABASE_URL = env('SUPABASE_URL') or env('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = env('SUPABASE_SERVICE_ROLE_KEY') or env('SUPABASE_KEY') or env('SUPABASE_ANON_KEY')
ML_CLIENT_ID = env('ML_CLIENT_ID')
ML_CLIENT_SECRET = env('ML_CLIENT_SECRET')
ML_REDIRECT_URI = env('ML_REDIRECT_URI', f'{APP_URL}/mercadolivre/callback')
DB_TIMEOUT = int(env('DB_TIMEOUT_SECONDS','8') or 8)
DEFAULT_COMPANY_ID = '00000000-0000-0000-0000-000000000001'
DEFAULT_SUPPLIER_ID = '00000000-0000-0000-0000-000000000101'
MEMORY = {k: [] for k in ['companies','suppliers','products','inventory','orders','listings','oauth_tokens','logs']}

def db_configured(): return bool(SUPABASE_URL and SUPABASE_KEY)
def db_mode(): return 'supabase' if db_configured() else 'memory'
def parse_json(raw, default):
    try: return json.loads(raw) if raw else default
    except Exception: return default

def http(method, url, headers=None, payload=None, timeout=8):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
            return {'success': 200 <= resp.status < 400, 'status_code': resp.status, 'data': parse_json(raw, {}), 'error': ''}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='ignore')
        return {'success': False, 'status_code': exc.code, 'data': parse_json(raw, {}), 'error': raw or str(exc)}
    except Exception as exc:
        return {'success': False, 'status_code': 0, 'data': {}, 'error': str(exc)}

def s_headers(prefer='return=representation'):
    return {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json', 'Prefer': prefer}

def s_rest(method, path, payload=None, prefer='return=representation'):
    if not db_configured(): return {'success': False, 'mode': 'memory', 'data': [], 'error': 'Supabase não configurado'}
    res = http(method, f"{SUPABASE_URL.rstrip()}/rest/v1/{path.lstrip('/')}", s_headers(prefer), payload, DB_TIMEOUT)
    res['mode'] = 'supabase'
    return res
async def db_select(table, query='select=*'):
    if not db_configured(): return {'success': True, 'mode': 'memory', 'data': MEMORY.get(table, [])}
    res = s_rest('GET', f'{table}?{query}')
    if not isinstance(res.get('data'), list): res['data'] = []
    return res
async def db_insert(table, payload):
    if not db_configured():
        MEMORY.setdefault(table, []).append(payload)
        return {'success': True, 'mode': 'memory', 'data': payload}
    return s_rest('POST', table, payload)
async def db_upsert(table, payload, conflict='id'):
    if not db_configured():
        items = MEMORY.setdefault(table, [])
        for i, it in enumerate(items):
            if str(it.get(conflict)) == str(payload.get(conflict)):
                items[i] = {**it, **payload}; break
        else: items.append(payload)
        return {'success': True, 'mode': 'memory', 'data': payload}
    return s_rest('POST', f'{table}?on_conflict={conflict}', payload, 'resolution=merge-duplicates,return=representation')

def sale_price(cost):
    cost = float(cost or 0)
    return round((cost + 6 + cost * .35) / .84, 2)

def money(v):
    try: return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X','.')
    except Exception: return 'R$ 0,00'
def btn(url, label): return f"<a class='btn' href='{url}'>{label}</a>"
def shell(title, content):
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>body{{margin:0;font-family:Arial;background:#f4f7fb;color:#111827}}aside{{position:fixed;left:0;top:0;bottom:0;width:250px;background:#0b1220;color:white;padding:20px}}aside a{{display:block;color:white;text-decoration:none;padding:9px;margin:4px 0}}main{{margin-left:270px;padding:28px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:14px}}.card,.metric{{background:white;border:1px solid #d8dee8;border-radius:14px;padding:18px;margin:14px 0}}.metric span{{display:block;color:#64748b}}.metric strong{{font-size:24px}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:10px 14px;border-radius:10px;margin:6px 5px 6px 0}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #e5e7eb;text-align:left;padding:10px}}input,textarea{{width:100%;padding:10px;margin:5px 0 12px}}button{{background:#2563eb;color:white;border:0;padding:10px 14px;border-radius:10px}}pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto}}</style></head><body><aside><h2>CH</h2><p>CommerceHub<br>V2 ML Pro</p><a href='/'>Dashboard</a><a href='/setup'>Setup</a><a href='/products'>Produtos</a><a href='/new-product'>Novo Produto</a><a href='/suppliers'>Fornecedores</a><a href='/inventory'>Estoque</a><a href='/mercado-livre'>Mercado Livre</a><a href='/sell-flow'>Fluxo de Venda</a><a href='/api/health'>API Health</a></aside><main><h1>{title}</h1>{content}</main></body></html>"""

def ml_auth_url():
    if not ML_CLIENT_ID: return ''
    return 'https://auth.mercadolivre.com.br/authorization?' + urlencode({'response_type': 'code', 'client_id': ML_CLIENT_ID, 'redirect_uri': ML_REDIRECT_URI})
async def get_token():
    r = await db_select('oauth_tokens', 'select=*&marketplace=eq.mercado_livre&limit=1')
    data = r.get('data') or []
    return data[0] if data else {}
async def save_token(token):
    return await db_upsert('oauth_tokens', {'id':'mercado_livre_default','company_id':DEFAULT_COMPANY_ID,'marketplace':'mercado_livre','access_token':token.get('access_token'),'refresh_token':token.get('refresh_token'),'user_id':str(token.get('user_id') or ''),'expires_in':int(token.get('expires_in') or 0),'token_type':token.get('token_type') or 'Bearer','scope':token.get('scope') or '','updated_at':datetime.utcnow().isoformat()}, 'id')
async def refresh_token():
    t = await get_token(); rt = t.get('refresh_token')
    if not rt: return {'success': False, 'error': 'Refresh token não encontrado'}
    r = http('POST','https://api.mercadolibre.com/oauth/token', {'Content-Type':'application/json'}, {'grant_type':'refresh_token','client_id':ML_CLIENT_ID,'client_secret':ML_CLIENT_SECRET,'refresh_token':rt}, 12)
    if r.get('success'): await save_token(r.get('data') or {})
    return r
async def ml_request(path, method='GET', payload=None, params=None, retry=True):
    t = await get_token(); access = t.get('access_token')
    if not access: return {'success': False, 'error': 'Mercado Livre não conectado. Clique em Conectar Mercado Livre.'}
    q = '?' + urlencode(params) if params else ''
    r = http(method, 'https://api.mercadolibre.com' + path + q, {'Authorization': f'Bearer {access}', 'Content-Type':'application/json'}, payload, 12)
    if r.get('status_code') == 401 and retry:
        rr = await refresh_token()
        if rr.get('success'): return await ml_request(path, method, payload, params, False)
    return r

@app.get('/api/health')
def health(): return {'status':'ok','service':'commercehub','version':'v2-ml-pro','mode':db_mode()}
@app.get('/', response_class=HTMLResponse)
async def dashboard():
    r = await db_select('products','select=*')
    return HTMLResponse(shell('Dashboard', f"<div class='grid'><div class='metric'><span>Sistema</span><strong>OK</strong></div><div class='metric'><span>Banco</span><strong>{db_mode().upper()}</strong></div><div class='metric'><span>Produtos</span><strong>{len(r.get('data',[]))}</strong></div><div class='metric'><span>Versão</span><strong>V2</strong></div></div><div class='card'><h2>CommerceHub V2 Mercado Livre</h2><p>Versão limpa e focada para começar vendas no Mercado Livre.</p>{btn('/setup','Setup')}{btn('/new-product','Cadastrar Produto')}{btn('/mercado-livre','Mercado Livre')}{btn('/sell-flow','Fluxo de Venda')}</div>"))
@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard_alias(): return await dashboard()
@app.get('/setup', response_class=HTMLResponse)
def setup(): return HTMLResponse(shell('Setup', f"<div class='card'><pre>{json.dumps({'version':'v2-ml-pro','mode':db_mode(),'supabase':db_configured()},indent=2)}</pre>{btn('/api/foundation/seed','Criar dados iniciais')}{btn('/api/backend/health','Backend Health')}</div>"))
@app.get('/api/backend/health')
async def backend_health():
    tables = {}
    for t in ['suppliers','products','inventory','orders','listings','oauth_tokens','logs']:
        r = await db_select(t,'select=*&limit=1'); tables[t] = {'success':r.get('success'),'rows':len(r.get('data',[])),'error':str(r.get('error',''))[:120]}
    return {'success': True, 'mode': db_mode(), 'tables': tables}
@app.get('/api/foundation/seed')
@app.post('/api/foundation/seed')
async def seed():
    supplier={'id':DEFAULT_SUPPLIER_ID,'company_id':DEFAULT_COMPANY_ID,'name':'Fornecedor Manual','type':'manual','status':'active','config':{}}
    product={'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'supplier_id':DEFAULT_SUPPLIER_ID,'sku':'TESTE-ML-001','name':'Produto Teste CommerceHub','brand':'CommerceHub','category':'Produto','description':'Produto novo, pronto para venda no Mercado Livre.','cost_price':20,'sale_price':sale_price(20),'stock':5,'status':'active','raw_data':{}}
    return {'success':True,'supplier':await db_upsert('suppliers',supplier),'product':await db_upsert('products',product),'inventory':await db_insert('inventory',{'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'product_id':product['id'],'sku':product['sku'],'movement_type':'set','quantity':5,'previous_stock':0,'new_stock':5,'source':'seed','created_at':datetime.utcnow().isoformat()})}
@app.get('/new-product', response_class=HTMLResponse)
def new_product():
    return HTMLResponse(shell('Novo Produto', """<div class='card'><form method='post' action='/api/products/create'><label>SKU</label><input name='sku' value='PROD-001'><label>Nome</label><input name='name' value='Produto Teste CommerceHub'><label>Marca</label><input name='brand' value='CommerceHub'><label>Categoria</label><input name='category' value='Produto'><label>Custo</label><input name='cost_price' value='20'><label>Estoque</label><input name='stock' value='5'><label>Descrição</label><textarea name='description'>Produto novo, pronto para venda no Mercado Livre.</textarea><button type='submit'>Salvar produto</button></form></div>"""))
@app.post('/api/products/create')
async def create_product(request:Request):
    f = await request.form()
    product={'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'supplier_id':DEFAULT_SUPPLIER_ID,'sku':str(f.get('sku')),'name':str(f.get('name')),'brand':str(f.get('brand')),'category':str(f.get('category')),'description':str(f.get('description')),'cost_price':float(f.get('cost_price') or 0),'sale_price':sale_price(float(f.get('cost_price') or 0)),'stock':int(float(f.get('stock') or 0)),'status':'active','raw_data':{}}
    await db_upsert('suppliers', {'id':DEFAULT_SUPPLIER_ID,'company_id':DEFAULT_COMPANY_ID,'name':'Fornecedor Manual','type':'manual','status':'active','config':{}})
    await db_upsert('products', product)
    await db_insert('inventory', {'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'product_id':product['id'],'sku':product['sku'],'movement_type':'set','quantity':product['stock'],'previous_stock':0,'new_stock':product['stock'],'source':'manual','created_at':datetime.utcnow().isoformat()})
    return RedirectResponse('/products', status_code=303)
@app.get('/products', response_class=HTMLResponse)
async def products():
    r=await db_select('products','select=*')
    rows=''.join([f"<tr><td>{p.get('sku')}</td><td>{p.get('name')}</td><td>{p.get('brand')}</td><td>{p.get('stock')}</td><td>{money(p.get('sale_price'))}</td><td>{btn('/api/listings/preview/'+str(p.get('id')),'Preview')}</td></tr>" for p in r.get('data',[])]) or "<tr><td colspan='6'>Nenhum produto cadastrado.</td></tr>"
    return HTMLResponse(shell('Produtos', f"<div class='card'><table><tr><th>SKU</th><th>Nome</th><th>Marca</th><th>Estoque</th><th>Preço</th><th>Ação</th></tr>{rows}</table>{btn('/new-product','Novo produto')}</div>"))
@app.get('/suppliers', response_class=HTMLResponse)
async def suppliers():
    r=await db_select('suppliers','select=*')
    rows=''.join([f"<tr><td>{s.get('id')}</td><td>{s.get('name')}</td><td>{s.get('type')}</td><td>{s.get('status')}</td></tr>" for s in r.get('data',[])]) or "<tr><td colspan='4'>Nenhum fornecedor cadastrado.</td></tr>"
    return HTMLResponse(shell('Fornecedores', f"<div class='card'><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table></div>"))
@app.get('/inventory', response_class=HTMLResponse)
async def inventory():
    r=await db_select('inventory','select=*')
    rows=''.join([f"<tr><td>{i.get('sku')}</td><td>{i.get('movement_type')}</td><td>{i.get('quantity')}</td><td>{i.get('new_stock')}</td></tr>" for i in r.get('data',[])]) or "<tr><td colspan='4'>Nenhum movimento.</td></tr>"
    return HTMLResponse(shell('Estoque', f"<div class='card'><table><tr><th>SKU</th><th>Movimento</th><th>Qtd</th><th>Novo estoque</th></tr>{rows}</table></div>"))
@app.get('/mercado-livre', response_class=HTMLResponse)
async def mercado_livre():
    t=await get_token(); connected=bool(t.get('access_token'))
    return HTMLResponse(shell('Mercado Livre', f"<div class='card'><h2>Mercado Livre</h2><p>Conectado: <b>{connected}</b></p>{btn(ml_auth_url(),'Conectar Mercado Livre')}{btn('/api/mercadolivre/me','Testar conta')}{btn('/api/ml/items','Anúncios')}{btn('/api/ml/orders','Pedidos')}</div>"))
@app.get('/mercadolivre/callback', response_class=HTMLResponse)
async def ml_callback(code:str=''):
    res=http('POST','https://api.mercadolibre.com/oauth/token', {'Content-Type':'application/json'}, {'grant_type':'authorization_code','client_id':ML_CLIENT_ID,'client_secret':ML_CLIENT_SECRET,'code':code,'redirect_uri':ML_REDIRECT_URI}, 12)
    if res.get('success'): await save_token(res.get('data') or {})
    return HTMLResponse(shell('Callback Mercado Livre', f"<div class='card'><pre>{json.dumps(res, ensure_ascii=False, indent=2)}</pre>{btn('/mercado-livre','Voltar')}</div>"))
@app.get('/api/mercadolivre/me')
async def me(): return await ml_request('/users/me')
@app.get('/api/ml/items')
async def items():
    me=await ml_request('/users/me'); uid=(me.get('data') or {}).get('id')
    return {'success':False,'error':'Não foi possível identificar User ID','me':me} if not uid else await ml_request(f'/users/{uid}/items/search', params={'limit':20})
@app.get('/api/ml/orders')
async def orders():
    me=await ml_request('/users/me'); uid=(me.get('data') or {}).get('id')
    return {'success':False,'error':'Não foi possível identificar User ID','me':me} if not uid else await ml_request('/orders/search', params={'seller':uid,'limit':20})
@app.get('/api/listings/preview/{product_id}')
async def preview(product_id:str, category_id:str='MLBXXXX'):
    r=await db_select('products','select=*')
    p=next((x for x in r.get('data',[]) if str(x.get('id'))==str(product_id)),None)
    if not p: return {'success':False,'error':'Produto não encontrado'}
    title=f"{p.get('brand','CommerceHub')} {p.get('name','Produto')}"[:60]
    return {'success':True,'payload':{'title':title,'category_id':category_id,'price':float(p.get('sale_price') or sale_price(p.get('cost_price'))),'currency_id':'BRL','available_quantity':int(p.get('stock') or 1),'buying_mode':'buy_it_now','condition':'new','listing_type_id':'gold_special','description':{'plain_text':p.get('description') or title}}}
@app.get('/sell-flow', response_class=HTMLResponse)
def sell_flow():
    return HTMLResponse(shell('Fluxo de Venda', f"<div class='card'><h2>Fluxo para vender no Mercado Livre</h2><ol><li>Conectar Mercado Livre.</li><li>Cadastrar produto.</li><li>Gerar preview.</li><li>Validar categoria.</li><li>Publicar anúncio.</li><li>Acompanhar pedidos.</li></ol>{btn('/mercado-livre','Mercado Livre')}{btn('/new-product','Cadastrar Produto')}{btn('/products','Produtos')}</div>"))
@app.get('/favicon.ico')
def favicon(): return {'ok':True}
