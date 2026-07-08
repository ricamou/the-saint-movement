from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from urllib.parse import urlencode
from datetime import datetime
import os, json, uuid, time, urllib.request, urllib.error

app = FastAPI(title='CommerceHub Mercado Livre Sales Ready', version='ml-sales-ready-v1')

def env(name, default=''):
    v = os.getenv(name, default)
    if v is None: return ''
    v = str(v).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v

APP_URL = env('APP_URL','https://commercehub-vercel-mvp.vercel.app')
SUPABASE_URL = env('SUPABASE_URL') or env('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = env('SUPABASE_SERVICE_ROLE_KEY') or env('SUPABASE_KEY') or env('SUPABASE_ANON_KEY')
ML_CLIENT_ID = env('ML_CLIENT_ID')
ML_CLIENT_SECRET = env('ML_CLIENT_SECRET')
ML_REDIRECT_URI = env('ML_REDIRECT_URI', f'{APP_URL}/mercadolivre/callback')
ML_ACCESS_TOKEN = env('ML_ACCESS_TOKEN')
ML_REFRESH_TOKEN = env('ML_REFRESH_TOKEN')
ML_USER_ID = env('ML_USER_ID')
DB_TIMEOUT = int(env('DB_TIMEOUT_SECONDS','6') or 6)
DB_RETRY = int(env('DB_RETRY_ATTEMPTS','1') or 1)
DEFAULT_COMPANY_ID='00000000-0000-0000-0000-000000000001'
DEFAULT_SUPPLIER_ID='00000000-0000-0000-0000-000000000101'
DEFAULT_PRODUCT_ID='00000000-0000-0000-0000-000000001001'
MEMORY={t:[] for t in ['companies','suppliers','products','inventory','orders','listings','oauth_tokens','logs','webhooks']}

def db_configured(): return bool(SUPABASE_URL and SUPABASE_KEY)
def db_mode(): return 'supabase' if db_configured() else 'memory'
def parse_json(raw, default):
    try: return json.loads(raw) if raw else default
    except Exception: return default

def supabase_request(method, path, payload=None, prefer='return=representation'):
    if not db_configured():
        return {'success':False,'mode':'memory','data':[] if method=='GET' else None,'error':'Supabase não configurado'}
    url=f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    body=None if payload is None else json.dumps(payload).encode('utf-8')
    req=urllib.request.Request(url,data=body,method=method.upper(),headers={'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':prefer})
    last=''
    for attempt in range(DB_RETRY+1):
        try:
            with urllib.request.urlopen(req, timeout=DB_TIMEOUT) as resp:
                text=resp.read().decode('utf-8',errors='ignore')
                return {'success':200<=resp.status<400,'mode':'supabase','status_code':resp.status,'data':parse_json(text, [] if method.upper()=='GET' else None),'error':'','attempt':attempt+1}
        except urllib.error.HTTPError as exc:
            text=exc.read().decode('utf-8',errors='ignore')
            return {'success':False,'mode':'supabase','status_code':exc.code,'data':[] if method.upper()=='GET' else None,'error':text,'attempt':attempt+1}
        except Exception as exc:
            last=str(exc)
            if attempt>=DB_RETRY:
                return {'success':False,'mode':'supabase_error','status_code':0,'data':[] if method.upper()=='GET' else None,'error':last,'attempt':attempt+1}
    return {'success':False,'mode':'supabase_error','data':[],'error':last}

async def db_select(table, query='select=*'):
    if not db_configured(): return {'success':True,'mode':'memory','data':MEMORY.get(table,[])}
    return {**supabase_request('GET', f'{table}?{query}'),'table':table}
async def db_upsert(table, payload, conflict='id'):
    if not db_configured():
        values=payload if isinstance(payload,list) else [payload]; items=MEMORY.setdefault(table,[])
        for value in values:
            for i,item in enumerate(items):
                if str(item.get(conflict))==str(value.get(conflict)):
                    items[i]={**item,**value}; break
            else: items.append(value)
        return {'success':True,'mode':'memory','data':payload}
    return {**supabase_request('POST', f'{table}?on_conflict={conflict}', payload=payload, prefer='resolution=merge-duplicates,return=representation'),'table':table}
async def db_insert(table,payload):
    if not db_configured():
        if isinstance(payload,list): MEMORY.setdefault(table,[]).extend(payload)
        else: MEMORY.setdefault(table,[]).append(payload)
        return {'success':True,'mode':'memory','data':payload}
    return {**supabase_request('POST', table, payload=payload),'table':table}
async def log_event(event_type,message,payload=None):
    return await db_insert('logs',{'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'event_type':event_type,'message':message,'payload':payload or {},'created_at':datetime.utcnow().isoformat()})

def system_state():
    return {'version':'ml-sales-ready-v1','mode':db_mode(),'supabase_configured':db_configured(),'mercado_livre_configured':bool(ML_CLIENT_ID and ML_CLIENT_SECRET and ML_REDIRECT_URI),'mercado_livre_connected':bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN),'user_id':ML_USER_ID or ''}
def money(v):
    try: return f"R$ {float(v):,.2f}".replace(',','X').replace('.',',').replace('X','.')
    except Exception: return 'R$ 0,00'
def price_engine(cost_price, margin_percent=35, fixed_cost=6, commission_percent=16):
    cost=float(cost_price or 0); margin=float(margin_percent or 35)/100; fixed=float(fixed_cost or 0); commission=float(commission_percent or 16)/100
    sale=round((cost+fixed+cost*margin)/max(0.01,1-commission),2); profit=round(sale-cost-fixed-sale*commission,2)
    return {'cost_price':cost,'sale_price':sale,'profit':profit,'margin_percent':round((profit/sale)*100,2) if sale else 0}
def ai_optimize(product):
    title=f"{product.get('brand') or 'CommerceHub'} {product.get('name') or 'Produto'} {product.get('category') or ''}".strip()[:60]
    return {'title':title,'description':product.get('description') or f"{product.get('name','Produto')} novo, pronto para venda.",'seo_score':100 if len(title)>=20 else 80}
def build_ml_payload(product, category_id='MLBXXXX'):
    pricing=price_engine(product.get('cost_price',0)); ai=ai_optimize(product)
    return {'title':ai['title'],'category_id':category_id,'price':float(product.get('sale_price') or pricing['sale_price']),'currency_id':'BRL','available_quantity':int(product.get('stock') or 1),'buying_mode':'buy_it_now','condition':'new','listing_type_id':'gold_special','description':{'plain_text':ai['description']},'attributes':[{'id':'BRAND','value_name':product.get('brand') or 'CommerceHub'},{'id':'MODEL','value_name':product.get('sku') or 'CH-001'}]}
def btn(url,label): return f"<a class='btn' href='{url}'>{label}</a>"
def shell(title,content):
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{title}</title><style>body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f7fb;color:#111827}}aside{{position:fixed;left:0;top:0;bottom:0;width:250px;background:#0b1220;color:white;padding:20px;overflow:auto}}aside a{{display:block;color:white;text-decoration:none;padding:9px;border-radius:8px;margin:4px 0}}aside a:hover{{background:#172033}}main{{margin-left:270px;padding:28px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:14px}}.card,.metric{{background:white;border:1px solid #d8dee8;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 8px 24px rgba(15,23,42,.05)}}.metric span{{display:block;color:#64748b}}.metric strong{{font-size:24px}}.btn{{display:inline-block;background:#2563eb;color:white;text-decoration:none;padding:10px 14px;border-radius:10px;margin:6px 5px 6px 0}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{border-bottom:1px solid #e5e7eb;text-align:left;padding:10px}}th{{background:#f8fafc}}input,textarea{{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;margin:5px 0 12px 0}}button{{background:#2563eb;color:white;border:0;padding:10px 14px;border-radius:10px}}pre{{background:#0b1220;color:white;padding:14px;border-radius:10px;overflow:auto;white-space:pre-wrap}}</style></head><body><aside><h2>CH</h2><p>CommerceHub<br>ML Sales Ready</p><a href='/'>Dashboard</a><a href='/setup'>Setup</a><a href='/supabase'>Supabase</a><a href='/products'>Produtos</a><a href='/new-product'>Novo Produto</a><a href='/suppliers'>Fornecedores</a><a href='/inventory'>Estoque</a><a href='/mercado-livre'>Mercado Livre</a><a href='/sell-flow'>Fluxo de Venda</a><a href='/api/health'>API Health</a></aside><main><h1>{title}</h1>{content}</main></body></html>"""

@app.get('/api/health')
def health(): return {'status':'ok','service':'commercehub','version':'ml-sales-ready-v1'}
@app.get('/', response_class=HTMLResponse)
async def dashboard():
    state=system_state(); products=await db_select('products','select=*')
    content=f"<div class='grid'><div class='metric'><span>Sistema</span><strong>OK</strong></div><div class='metric'><span>Banco</span><strong>{state['mode'].upper()}</strong></div><div class='metric'><span>Produtos</span><strong>{len(products.get('data',[]))}</strong></div><div class='metric'><span>ML</span><strong>{'ON' if state['mercado_livre_connected'] else 'OFF'}</strong></div></div><div class='card'><h2>Pronto para começar vendas no Mercado Livre</h2><p>Fluxo comercial: produto → estoque → preview → Mercado Livre → pedido.</p>{btn('/setup','Preparar sistema')}{btn('/new-product','Cadastrar produto')}{btn('/sell-flow','Fluxo de venda')}{btn('/mercado-livre','Mercado Livre')}</div>"
    return HTMLResponse(shell('Dashboard Enterprise',content))
@app.get('/dashboard',response_class=HTMLResponse)
async def dashboard_alias(): return await dashboard()
@app.get('/setup',response_class=HTMLResponse)
def setup_page():
    return HTMLResponse(shell('Setup',f"<div class='card'><h2>Status de produção</h2><pre>{json.dumps(system_state(),ensure_ascii=False,indent=2)}</pre>{btn('/api/foundation/seed','Criar dados iniciais')}{btn('/api/commercial-test/create-product','Criar produto de teste')}{btn('/api/backend/health','Backend Health')}</div>"))
@app.get('/supabase',response_class=HTMLResponse)
def supabase_page():
    test=supabase_request('GET','products?select=*&limit=1') if db_configured() else {'success':False,'error':'Supabase não configurado','data':[]}
    return HTMLResponse(shell('Supabase',f"<div class='card'><h2>Diagnóstico Supabase</h2><pre>{json.dumps({'state':system_state(),'test':test},ensure_ascii=False,indent=2)}</pre></div>"))
@app.get('/new-product',response_class=HTMLResponse)
def new_product_page():
    return HTMLResponse(shell('Novo Produto',"""<div class='card'><h2>Cadastrar produto rápido</h2><form method='post' action='/api/products/create'><label>SKU</label><input name='sku' value='PROD-001'><label>Nome</label><input name='name' value='Produto Teste CommerceHub'><label>Marca</label><input name='brand' value='CommerceHub'><label>Categoria</label><input name='category' value='Produto'><label>Custo</label><input name='cost_price' value='20'><label>Estoque</label><input name='stock' value='5'><label>Descrição</label><textarea name='description'>Produto novo, pronto para venda no Mercado Livre.</textarea><button type='submit'>Salvar produto</button></form></div>"""))
@app.post('/api/products/create')
async def create_product_form(request:Request):
    form=await request.form(); cost=float(form.get('cost_price') or 0); pricing=price_engine(cost); sku=str(form.get('sku') or f'PROD-{int(time.time())}')
    product={'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'supplier_id':DEFAULT_SUPPLIER_ID,'sku':sku,'name':str(form.get('name') or 'Produto'),'brand':str(form.get('brand') or 'CommerceHub'),'category':str(form.get('category') or 'Produto'),'description':str(form.get('description') or ''),'cost_price':cost,'sale_price':pricing['sale_price'],'stock':int(float(form.get('stock') or 0)),'status':'active','raw_data':{}}
    await db_upsert('suppliers',{'id':DEFAULT_SUPPLIER_ID,'company_id':DEFAULT_COMPANY_ID,'name':'Fornecedor Manual','type':'manual','status':'active','config':{}}); await db_upsert('products',product); await db_insert('inventory',{'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'product_id':product['id'],'sku':sku,'movement_type':'set','quantity':product['stock'],'previous_stock':0,'new_stock':product['stock'],'source':'manual','created_at':datetime.utcnow().isoformat()}); await log_event('product_created','Produto criado',product)
    return RedirectResponse(url='/products',status_code=303)
@app.get('/products',response_class=HTMLResponse)
async def products_page():
    res=await db_select('products','select=*'); data=res.get('data') if isinstance(res.get('data'),list) else []
    rows=''.join([f"<tr><td>{p.get('sku','')}</td><td>{p.get('name','')}</td><td>{p.get('brand','')}</td><td>{p.get('stock','')}</td><td>{money(p.get('sale_price',0))}</td><td>{btn('/api/listings/preview/'+str(p.get('id')),'Preview')}</td></tr>" for p in data]) or "<tr><td colspan='6'>Nenhum produto cadastrado.</td></tr>"
    return HTMLResponse(shell('Produtos',f"<div class='card'><h2>Produtos para venda</h2><table><tr><th>SKU</th><th>Nome</th><th>Marca</th><th>Estoque</th><th>Preço</th><th>Ação</th></tr>{rows}</table>{btn('/new-product','Novo produto')}{btn('/api/commercial-test/create-product','Criar teste')}</div>"))
@app.get('/suppliers',response_class=HTMLResponse)
async def suppliers_page():
    res=await db_select('suppliers','select=*'); data=res.get('data') if isinstance(res.get('data'),list) else []; rows=''.join([f"<tr><td>{s.get('id','')}</td><td>{s.get('name','')}</td><td>{s.get('type','')}</td><td>{s.get('status','')}</td></tr>" for s in data]) or "<tr><td colspan='4'>Nenhum fornecedor cadastrado.</td></tr>"
    return HTMLResponse(shell('Fornecedores',f"<div class='card'><table><tr><th>ID</th><th>Nome</th><th>Tipo</th><th>Status</th></tr>{rows}</table></div>"))
@app.get('/inventory',response_class=HTMLResponse)
async def inventory_page():
    res=await db_select('inventory','select=*'); data=res.get('data') if isinstance(res.get('data'),list) else []; rows=''.join([f"<tr><td>{i.get('sku','')}</td><td>{i.get('movement_type','')}</td><td>{i.get('quantity','')}</td><td>{i.get('new_stock','')}</td><td>{i.get('source','')}</td></tr>" for i in data]) or "<tr><td colspan='5'>Nenhum movimento de estoque.</td></tr>"
    return HTMLResponse(shell('Estoque',f"<div class='card'><table><tr><th>SKU</th><th>Movimento</th><th>Qtd</th><th>Novo estoque</th><th>Origem</th></tr>{rows}</table></div>"))

def ml_request(path,method='GET',payload=None,params=None):
    if not ML_ACCESS_TOKEN: return {'success':False,'message':'ML_ACCESS_TOKEN ausente'}
    query='?'+urlencode(params) if params else ''; data=None if payload is None else json.dumps(payload).encode('utf-8')
    req=urllib.request.Request('https://api.mercadolibre.com'+path+query,data=data,method=method,headers={'Authorization':f'Bearer {ML_ACCESS_TOKEN}','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as resp: return {'success':True,'status_code':resp.status,'data':parse_json(resp.read().decode('utf-8',errors='ignore'),{})}
    except urllib.error.HTTPError as exc: return {'success':False,'status_code':exc.code,'error':exc.read().decode('utf-8',errors='ignore')}
    except Exception as exc: return {'success':False,'error':str(exc)}
@app.get('/mercado-livre',response_class=HTMLResponse)
def mercado_livre_page():
    connected=bool(ML_ACCESS_TOKEN and ML_REFRESH_TOKEN); auth='https://auth.mercadolivre.com.br/authorization?'+urlencode({'response_type':'code','client_id':ML_CLIENT_ID,'redirect_uri':ML_REDIRECT_URI}) if ML_CLIENT_ID else ''
    return HTMLResponse(shell('Mercado Livre',f"<div class='card'><h2>Mercado Livre</h2><p>Conectado: <b>{connected}</b></p><p>User ID: {ML_USER_ID}</p>{btn(auth,'Conectar Mercado Livre') if auth else ''}{btn('/api/mercadolivre/me','Testar Conta')}{btn('/api/ml/items','Anúncios')}{btn('/api/ml/orders','Pedidos')}</div>"))
@app.get('/sell-flow',response_class=HTMLResponse)
def sell_flow(): return HTMLResponse(shell('Fluxo de Venda',f"<div class='card'><h2>Fluxo para vender</h2><ol><li>Cadastrar produto.</li><li>Gerar preview.</li><li>Validar categoria ML.</li><li>Publicar anúncio.</li><li>Acompanhar pedidos.</li></ol>{btn('/new-product','Cadastrar produto')}{btn('/products','Produtos')}{btn('/mercado-livre','Mercado Livre')}</div>"))
@app.get('/api/mercadolivre/me')
def ml_me(): return ml_request('/users/me')
@app.get('/api/ml/items')
def ml_items():
    me=ml_request('/users/me'); user_id=(me.get('data') or {}).get('id') or ML_USER_ID
    return ml_request(f'/users/{user_id}/items/search',params={'limit':20}) if user_id else {'success':False,'message':'ML_USER_ID ausente'}
@app.get('/api/ml/orders')
def ml_orders():
    me=ml_request('/users/me'); user_id=(me.get('data') or {}).get('id') or ML_USER_ID
    return ml_request('/orders/search',params={'seller':user_id,'limit':20}) if user_id else {'success':False,'message':'ML_USER_ID ausente'}
@app.get('/api/listings/preview/{product_id}')
async def listing_preview(product_id:str,category_id:str='MLBXXXX'):
    products=await db_select('products','select=*'); product=next((p for p in products.get('data',[]) if str(p.get('id'))==str(product_id)), None) or {'id':product_id,'sku':'TESTE-ML-001','name':'Produto Teste CommerceHub','brand':'CommerceHub','description':'Produto de teste','cost_price':20,'sale_price':41.67,'stock':5}
    return {'success':True,'product':product,'payload':build_ml_payload(product,category_id),'next':'Validar category_id antes de publicar.'}
@app.post('/api/listings/publish/{product_id}')
async def publish_listing(product_id:str,category_id:str='MLBXXXX'):
    preview=await listing_preview(product_id,category_id); result=ml_request('/items',method='POST',payload=preview['payload']); await db_insert('listings',{'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'product_id':product_id,'marketplace':'mercado_livre','external_id':(result.get('data') or {}).get('id'),'status':'published' if result.get('success') else 'error','payload':result,'created_at':datetime.utcnow().isoformat()}); return {'success':result.get('success'), 'ml_result':result, 'payload_sent':preview['payload']}
@app.get('/api/foundation/seed')
@app.post('/api/foundation/seed')
async def seed():
    company={'id':DEFAULT_COMPANY_ID,'name':'CommerceHub','document':'00000000000000','plan':'enterprise','status':'active'}; supplier={'id':DEFAULT_SUPPLIER_ID,'company_id':DEFAULT_COMPANY_ID,'name':'Fornecedor Manual','type':'manual','status':'active','config':{}}; pricing=price_engine(20); product={'id':DEFAULT_PRODUCT_ID,'company_id':DEFAULT_COMPANY_ID,'supplier_id':DEFAULT_SUPPLIER_ID,'sku':'TESTE-ML-001','name':'Produto Teste CommerceHub','brand':'CommerceHub','category':'Produto','description':'Produto novo, pronto para venda no Mercado Livre.','cost_price':20,'sale_price':pricing['sale_price'],'stock':5,'status':'active','raw_data':{}}
    a=await db_upsert('companies',company); b=await db_upsert('suppliers',supplier); c=await db_upsert('products',product); d=await db_insert('inventory',{'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'product_id':DEFAULT_PRODUCT_ID,'sku':product['sku'],'movement_type':'set','quantity':5,'previous_stock':0,'new_stock':5,'source':'seed','created_at':datetime.utcnow().isoformat()}); await log_event('seed','Seed inicial executado',{'sku':product['sku']}); return {'success':True,'mode':db_mode(),'company':a,'supplier':b,'product':c,'inventory':d}
@app.get('/api/commercial-test/create-product')
@app.post('/api/commercial-test/create-product')
async def commercial_test(): return await seed()
@app.get('/api/commercial-test/check')
async def commercial_check():
    products=await db_select('products','select=*'); suppliers=await db_select('suppliers','select=*'); inventory=await db_select('inventory','select=*'); return {'success':True,'mode':db_mode(),'products':len(products.get('data',[])),'suppliers':len(suppliers.get('data',[])),'inventory':len(inventory.get('data',[]))}
@app.get('/api/backend/health')
def backend_health():
    tables=['companies','suppliers','products','inventory','orders','listings','logs']; results={}
    for table in tables:
        res=supabase_request('GET',f'{table}?select=*&limit=1') if db_configured() else {'success':False,'data':[],'error':'Supabase não configurado'}; results[table]={'success':res.get('success'),'status_code':res.get('status_code'),'rows':len(res.get('data',[]) if isinstance(res.get('data'),list) else []),'error':str(res.get('error',''))[:180]}
    return {'success':True,'state':system_state(),'tables':results}
@app.get('/api/supabase/ready')
def supabase_ready(): return {'success':True,'state':system_state(),'test':supabase_request('GET','products?select=*&limit=1') if db_configured() else {'success':False,'error':'Supabase não configurado'}}
@app.get('/api/foundation/status')
def foundation_status(): return {'success':True,**system_state(),'tables':list(MEMORY.keys()),'next':'/api/foundation/seed'}
@app.get('/api/db/{table}')
async def db_table(table:str): return await db_select(table,'select=*') if table in MEMORY else {'success':False,'message':'Tabela não permitida'}
@app.post('/api/webhooks/mercadolivre')
async def webhook_ml(request:Request):
    payload=await request.json(); await db_insert('webhooks',{'id':str(uuid.uuid4()),'company_id':DEFAULT_COMPANY_ID,'marketplace':'mercado_livre','event_type':payload.get('topic') or 'unknown','payload':payload,'status':'received','created_at':datetime.utcnow().isoformat()}); await log_event('webhook_ml','Webhook ML recebido',payload); return {'success':True}
@app.get('/favicon.ico')
def favicon_ico(): return {'ok':True}
@app.get('/favicon.png')
def favicon_png(): return {'ok':True}
