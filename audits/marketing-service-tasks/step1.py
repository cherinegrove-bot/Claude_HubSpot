import sys; sys.path.insert(0,'.')
from pull import *
TP=['hs_task_subject','hubspot_owner_id','hs_task_sub_task_ids','task_catagory','hs_createdate','hs_task_status','hs_timestamp','hs_queue_membership_ids']
res={}
for s in ['Marketing Performance Review','Marketing Performance Review Checklist - Google Ads (PPC) Check']:
    ts=search('tasks',[{'propertyName':'hs_task_subject','operator':'EQ','value':s},{'propertyName':'hs_createdate','operator':'GTE','value':'2026-11-01T00:00:00Z'}],TP)
    res[s]=ts
# subtasks of a sample master (5 subs) and (4 subs) and ppc
allsub=[]
for s,ts in res.items():
    for t in ts:
        ids=(t['properties']['hs_task_sub_task_ids'] or '').split(';')
        ids=[i for i in ids if i]
        subs=batch_read('tasks',ids,['hs_task_subject','hubspot_owner_id','task_catagory','hs_task_status','hs_timestamp']) if ids else []
        t['subs']=sorted([(x['properties']['hs_task_subject'],x['properties']['hubspot_owner_id'],x['properties']['task_catagory']) for x in subs])
ids=[t['id'] for ts in res.values() for t in ts]
co=assoc('tasks','companies',ids); tk=assoc('tasks','tickets',ids)
for ts in res.values():
    for t in ts:
        t['companies']=[(x['toObjectId'],[l.get('typeId') for l in x['associationTypes']]) for x in co.get(t['id'],[])]
        t['tickets']=[(x['toObjectId'],[(l.get('category'),l.get('typeId'),l.get('label')) for l in x['associationTypes']]) for x in tk.get(t['id'],[])]
json.dump(res,open('existing_tasks.json','w'),indent=1)
from collections import Counter
for s,ts in res.items():
    print('==',s,len(ts))
    c=Counter(); 
    for t in ts: c[(t['properties']['hs_createdate'][:10],t['properties']['hubspot_owner_id'],len(t['companies']),len(t['tickets']))]+=1
    for k,v in sorted(c.items()): print('  created/owner/#co/#tk',k,v)
    pat=Counter(json.dumps(t['subs']) for t in ts)
    for k,v in pat.items(): print('  SUBS x',v); [print('     ',x) for x in json.loads(k)]
