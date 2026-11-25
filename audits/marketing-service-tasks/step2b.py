import sys; sys.path.insert(0,'.')
from pull import *
CP=['name','customer_tier','trend_to_goal_','marketing_portfolio_mgr','sparefoot__y_n_','ppc_ads__yes_no_','ppc_active_yesno','live','standalone_services']
L={}
for l in ['5523','5525','5527','5529','5466']:
    ids=[];after=None
    while True:
        d=req(f'/crm/v3/lists/{l}/memberships?limit=250'+(f'&after={after}' if after else ''))
        ids+=[m['recordId'] for m in d['results']]; after=d.get('paging',{}).get('next',{}).get('after')
        if not after: break
    L[l]=ids
cos=search('companies',None,CP,groups=[{'filters':[{'propertyName':'live','operator':'IN','values':['Yes']}]}])
have={c['id'] for c in cos}; allids=set(i for v in L.values() for i in v)
cos+=batch_read('companies',[i for i in allids if i not in have],CP)
a=assoc('companies','tickets',[c['id'] for c in cos]); tids=set()
for c in cos:
    c['mk']=[str(x['toObjectId']) for x in a.get(c['id'],[]) if any(l.get('typeId')==64 for l in x['associationTypes'])]; tids|=set(c['mk'])
tk={t['id']:t['properties'] for t in batch_read('tickets',list(tids),['hs_pipeline','hs_pipeline_stage'])}
STG={'1396673189':'Transitions','1396876936':'Enterprise','1396876937':'Tier 1','1396876938':'Tier 2.1','1396876939':'Tier 2.2','1396876940':'Tier 3','1396876941':'Standalone - Marketing','1408106337':'PPC Enrolled No (closed)'}
rows=[]
for c in cos:
    p=c['properties']
    r=dict(id=c['id'],name=p['name'],tier=p['customer_tier'],trend=p['trend_to_goal_'],mpm=p['marketing_portfolio_mgr'],sf=p['sparefoot__y_n_'],ppc_en=p['ppc_ads__yes_no_'],ppc_act=p['ppc_active_yesno'],live=p['live'],standalone=p['standalone_services'],
      stages=[STG.get(tk[t]['hs_pipeline_stage'],tk[t]['hs_pipeline']+'/'+tk[t]['hs_pipeline_stage']) for t in c['mk'] if t in tk],ntk=len(c['mk']))
    for l in L: r['L'+l]=c['id'] in L[l]
    rows.append(r)
json.dump(rows,open('rows2.json','w'),indent=1)
print({k:len(v) for k,v in L.items()})
