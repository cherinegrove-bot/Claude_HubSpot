import sys; sys.path.insert(0,'.')
from pull import *
from collections import Counter
CP=['name','customer_tier','trend_to_goal_','marketing_portfolio_mgr','sparefoot__y_n_','ppc_ads__yes_no_','ppc_active_yesno','live','standalone_services','mgt_type','hs_lastmodifieddate']
cos=search('companies',None,CP,groups=[{'filters':[{'propertyName':'live','operator':'IN','values':['Yes']}]}])
members=[m['recordId'] for m in req('/crm/v3/lists/5466/memberships?limit=250')['results']]
have={c['id'] for c in cos}
extra=[m for m in members if m not in have]
cos+=batch_read('companies',extra,CP) if extra else []
ids=[c['id'] for c in cos]
a=assoc('companies','tickets',ids)
tids=set()
for c in cos:
    mk=[x['toObjectId'] for x in a.get(c['id'],[]) if any(l.get('typeId')==64 for l in x['associationTypes'])]
    c['mkt_tickets']=[str(x) for x in mk]; tids|=set(c['mkt_tickets'])
tk={t['id']:t for t in batch_read('tickets',list(tids),['subject','hs_pipeline','hs_pipeline_stage','hubspot_owner_id','next_review_due','last_review_date'])}
for c in cos: c['mkt_ticket_objs']=[tk[t]['properties'] for t in c['mkt_tickets'] if t in tk]
json.dump({'companies':cos,'members':members},open('companies.json','w'),indent=1)
print('live companies',len(have),'list members',len(members),'members not live',len(extra))
