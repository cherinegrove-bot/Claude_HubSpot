# Builds structured per-workflow models from the pulled records
import pickle,collections,re,json,datetime as dt
T,R,TK,OW,STG,WF=pickle.load(open('an.pkl','rb'))
def own(x): return OW.get(x,f"Owner ID {x}") if x else None
def num(s):
    m=re.search(r'(\d+)\.',s or ''); return int(m.group(1)) if m else None
M={}
for new,stage,old in WF:
    tasks=R[new]['tasks']; enr=R[new]['enr']
    byid={t['id']:t for t in tasks}
    groups=collections.OrderedDict()
    for t in tasks:
        p=t['properties']; sub=p['hs_task_is_sub_task']=='true'; s=(p['hs_task_subject'] or '').strip()
        key=(t['idx'],'SUB',num(s)) if sub else (t['idx'],'PARENT',None)
        groups.setdefault(key,[]).append(t)
    # merge unnumbered subtasks into numbered key with same idx whose title contains text
    for k in [k for k in groups if k[1]=='SUB' and k[2] is None]:
        s=re.sub(r'\s*\(.*$','',groups[k][0]['properties']['hs_task_subject'].strip().lower())
        cand=[k2 for k2 in groups if k2[0]==k[0] and k2[1]=='SUB' and k2[2] is not None and s.replace('test ','') in groups[k2][0]['properties']['hs_task_subject'].lower() and len(s)>5]
        if cand: groups[cand[0]]+=groups.pop(k)
    G=[]
    for k,l in groups.items():
        titles=collections.Counter((x['properties']['hs_task_subject'] or '').strip() for x in l)
        tmain=titles.most_common(1)[0][0]
        owners=collections.Counter(own(x['properties']['hubspot_owner_id']) or '(no owner)' for x in l)
        bd=collections.Counter(x['bd'] for x in l); cal=collections.Counter(x['cal'] for x in l); tm=collections.Counter(x['duetime'] for x in l)
        pri=collections.Counter(x['properties']['hs_task_priority'] for x in l); typ=collections.Counter(x['properties']['hs_task_type'] for x in l)
        st=collections.Counter(x['properties']['hs_task_status'] for x in l)
        def ap(x):
            a=[]; 
            if x['tickets']: a.append('Ticket')
            if x['companies']: a.append('Company'+(f" x{len(x['companies'])}" if len(x['companies'])>1 else ''))
            if x['contacts']: a.append('Contact')
            if x['deals']: a.append('Deal')
            return ' + '.join(a) or '(no associations)'
        assoc=collections.Counter(ap(x) for x in l)
        tick_owner_match=None
        if k[1]=='PARENT':
            m=sum(1 for x in l if x['tickets'] and TK.get(x['tickets'][0]) and TK[x['tickets'][0]]['properties'].get('hubspot_owner_id')==x['properties']['hubspot_owner_id'])
            tick_owner_match=(m,len(l))
        variants=[(tt,c,sorted({f"{x['c']:%Y-%m-%d}" for x in l if (x['properties']['hs_task_subject'] or '').strip()==tt})) for tt,c in titles.items() if tt!=tmain]
        parent_title=None
        if k[1]=='SUB':
            pt=collections.Counter((byid.get(x['properties']['hs_task_parent_task_id'],{}).get('properties',{}).get('hs_task_subject') or '(parent not found)').strip() for x in l)
            parent_title=pt.most_common(1)[0][0]
        G.append(dict(key=k,idx=k[0],kind=k[1],n=len(l),title=tmain,titles=titles,variants=variants,owners=owners,bd=bd,cal=cal,time=tm,pri=pri,typ=typ,st=st,assoc=assoc,tom=tick_owner_match,parent=parent_title,
            first=min(x['c'] for x in l),last=max(x['c'] for x in l),
            open_under_done=sum(1 for x in l if x['properties']['hs_task_status'] not in('COMPLETED','DEFERRED') and byid.get(x['properties']['hs_task_parent_task_id'],{}).get('properties',{}).get('hs_task_status')=='COMPLETED')))
    G.sort(key=lambda g:(g['idx'],g['kind']!='PARENT',g['key'][2] or 0))
    M[new]=dict(stage=stage,old=old,groups=G,enr=enr,tasks=tasks)
pickle.dump(M,open('model.pkl','wb'))
for new in M:
    print(new, [(g['idx'],g['kind'],g['key'][2],g['n']) for g in M[new]['groups']][:40])
