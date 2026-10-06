import json,collections,re,datetime as dt
from zoneinfo import ZoneInfo
ET=ZoneInfo("US/Eastern")
T=json.load(open('tr_tasks.json')); A=json.load(open('tr_assoc.json'))
TK={t['id']:t for t in json.load(open('tr_tickets.json'))}
OB={t['id']:t for t in json.load(open('onb_tickets.json'))}
TK.update(OB)
OW={str(o['id']):(o.get('firstName','')+' '+o.get('lastName','')).strip() or o.get('email') for o in json.load(open('owners.json'))}
STG={"1175587148":"On Hold","1100007030":"UNASSIGNED","1298054295":"Website Only","1094530721":"Transition Kickoff","1094530722":"Pre-Launch Setup","1094530723":"Launch Readiness","1094493506":"Go-Live Execution","1094493507":"Final Signoff","1102485356":"Post 30-Day Monitoring (OM/SM)","1094530724":"Transition Completed"}
WF=[("Transitions - Transition Kickoff Tasks (+SubTask)","1094530721","Transitions - Transition Kickoff Tasks"),
("Transitions - Pre Launch Setup Tasks (+SubTask)","1094530722","Transitions - Pre Launch Setup Tasks"),
("Transitions - Launch Readiness Tasks (+SubTask)","1094530723","Transitions - Launch Readiness Tasks"),
("Transitions - Go Live Execution Tasks (+SubTask)","1094493506","Transitions - Go Live Execution Tasks"),
("Transitions - Final Sign Off Tasks (+SubTask)","1094493507","Transitions - Final Sign Off Tasks"),
("Transitions - 30-Day Monitoring (+SubTask)","1102485356","Transitions - 30-Day Monitoring"),
("Transitions - TRANSITION COMPLETE (+SubTask)","1094530724",None)]
def P(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00')) if s else None
def bdays(a,b):
    n=0;d=a
    step=1 if b>=a else -1
    while d!=b:
        d+=dt.timedelta(days=step)
        if d.weekday()<5: n+=step
    return n
for t in T:
    p=t['properties']; m=re.match(r'enrollmentId:(\d+);actionExecutionIndex:(\d+)',p['hs_object_source_id'] or '')
    t['enr']=m.group(1); t['idx']=int(m.group(2)); t['c']=P(p['hs_createdate']); t['due']=P(p['hs_timestamp'])
    t['tickets']=[str(x[0]) for x in A.get(t['id'],{}).get('tickets',[])]
    t['companies']=[str(x[0]) for x in A.get(t['id'],{}).get('companies',[])]
    t['contacts']=[str(x[0]) for x in A.get(t['id'],{}).get('contacts',[])]
    t['deals']=[str(x[0]) for x in A.get(t['id'],{}).get('deals',[])]
    cd=t['c'].astimezone(ET).date(); dd=t['due'].astimezone(ET) if t['due'] else None
    t['cal']=(dd.date()-cd).days if dd else None; t['bd']=bdays(cd,dd.date()) if dd else None
    t['duetime']=dd.strftime('%H:%M') if dd else None; t['duewd']=dd.strftime('%a') if dd else None
R={}
for new,stage,old in WF:
    ts=[t for t in T if t['properties']['hs_object_source_detail_1']==new]
    enr=collections.defaultdict(list)
    for t in ts: enr[t['enr']].append(t)
    info=[]
    for e,l in enr.items():
        start=min(x['c'] for x in l); tix=sorted({x for t in l for x in t['tickets']})
        tk=TK.get(tix[0]) if tix else None
        de=P(tk['properties'].get('hs_v2_date_entered_'+stage)) if tk else None
        sig=tuple(sorted((t['idx'],t['properties']['hs_task_is_sub_task'],re.sub(r'\s*\(.*\)$','',(t['properties']['hs_task_subject'] or '').strip())) for t in l))
        info.append(dict(enr=e,start=start,tickets=tix,n=len(l),entered=de,delta=(start-de).total_seconds() if de else None,sig=sig,tasks=l))
    info.sort(key=lambda x:x['start'])
    R[new]=dict(stage=stage,old=old,tasks=ts,enr=info)
    d=[i['delta'] for i in info if i['delta'] is not None]
    w5=sum(1 for x in d if -60<=x<=600)
    sigs=collections.Counter(i['sig'] for i in info)
    tickets=collections.Counter(x for i in info for x in i['tickets'])
    print(f"\n### {new} | tasks {len(ts)} enr {len(info)} tickets {len(tickets)} | first {info[0]['start']:%Y-%m-%d} last {info[-1]['start']:%Y-%m-%d}")
    print(f"  stage-entry match (enrollment start within -1..+10 min of ticket entering {STG[stage]}): {w5}/{len(d)}; deltas(min) sample", sorted(round(x/60,1) for x in d)[:5], sorted(round(x/60,1) for x in d)[-5:])
    print("  tickets with >1 enrollment:", {k:v for k,v in tickets.items() if v>1}, " enrollments w/o ticket:", sum(1 for i in info if not i['tickets']), " w/ >1 ticket:", sum(1 for i in info if len(i['tickets'])>1))
    print("  distinct structure signatures:",len(sigs), [c for s,c in sigs.most_common()])
    idxs=collections.Counter(t['idx'] for t in ts); print("  exec indexes used:",sorted(idxs.items()))
json.dump({},open('/dev/null','w'))
import pickle; pickle.dump((T,R,TK,OW,STG,WF),open('an.pkl','wb'))
