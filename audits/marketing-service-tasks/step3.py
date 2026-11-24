import json
from collections import Counter
d=json.load(open('companies.json')); cos=d['companies']; members=set(d['members'])
ex=json.load(open('existing_tasks.json'))
STG={'1396673189':'Transitions','1396876936':'Enterprise','1396876937':'Tier 1','1396876938':'Tier 2.1','1396876939':'Tier 2.2','1396876940':'Tier 3','1396876941':'Standalone - Marketing','1408106337':'PPC Enrolled No (closed)'}
nov5_master={str(c[0]) for t in ex['Marketing Performance Review'] if t['properties']['hs_createdate'].startswith('2026-11-05') for c in t['companies']}
nov5_ppc={str(c[0]) for t in ex['Marketing Performance Review Checklist - Google Ads (PPC) Check'] for c in t['companies']}
rows=[]
for c in cos:
    p=c['properties']; tks=c['mkt_ticket_objs']
    stages=[STG.get(t['hs_pipeline_stage'],t['hs_pipeline']+'/'+t['hs_pipeline_stage']) for t in tks]
    r=dict(id=c['id'],name=p['name'],tier=p['customer_tier'],trend=p['trend_to_goal_'],mpm=p['marketing_portfolio_mgr'],sf=p['sparefoot__y_n_'],ppc_en=p['ppc_ads__yes_no_'],ppc_act=p['ppc_active_yesno'],live=p['live'],standalone=p['standalone_services'],ntk=len(tks),stages=stages,inlist=c['id'] in members,nov5m=c['id'] in nov5_master,nov5p=c['id'] in nov5_ppc)
    r['lane']=stages[0] if len(stages)==1 else ('NONE' if not stages else 'MULTI')
    r['wf_atrisk']=r['trend']=='At Risk' and r['lane']!='Standalone - Marketing'
    r['wf_impr']=r['trend']=='Improving' and r['tier'] in ('Enterprise','TIER 1','TIER 2')
    r['wf_sa']=r['lane']=='Standalone - Marketing'
    pe=r['ppc_en']=='true' and r['ppc_act']=='true' and r['live']=='Yes'
    r['wf_ppc']=pe and (r['trend']=='At Risk' or (r['trend']=='Improving' and r['tier'] in ('Enterprise','TIER 1','TIER 2')))
    rows.append(r)
json.dump(rows,open('rows.json','w'),indent=1)
C=Counter
print('trend',C(r['trend'] for r in rows if r['live']=='Yes'))
print('tier',C(r['tier'] for r in rows if r['live']=='Yes'))
print('lane',C(r['lane'] for r in rows if r['live']=='Yes'))
print('mpm',C(r['mpm'] for r in rows if r['live']=='Yes'))
print('sf',C(r['sf'] for r in rows if r['live']=='Yes'))
print('ntk',C(r['ntk'] for r in rows if r['live']=='Yes'))
print('tier x lane',C((r['tier'],r['lane']) for r in rows if r['live']=='Yes'))
print('standalone_services x lane',C((r['standalone'],r['lane']) for r in rows if r['lane']=='Standalone - Marketing' or (r['standalone'] or '').find('Marketing')>=0))
cand=[r for r in rows if r['wf_atrisk'] or r['wf_impr'] or r['wf_sa']]
print('candidates master',len(cand),'atrisk',sum(r['wf_atrisk'] for r in rows),'impr',sum(r['wf_impr'] for r in rows),'sa',sum(r['wf_sa'] for r in rows),'ppc',sum(r['wf_ppc'] for r in rows))
print('improving T2.2/T3 (should NOT get Improving)',sum(1 for r in rows if r['trend']=='Improving' and r['tier'] not in ('Enterprise','TIER 1','TIER 2')))
print('members: nov5 master',sum(r['nov5m'] for r in rows if r['inlist']),'nov5 ppc',sum(r['nov5p'] for r in rows if r['inlist']),'candidates in list', sum(1 for r in cand if r['inlist']), 'ppc cands in list',sum(1 for r in rows if r['wf_ppc'] and r['inlist']))
print('members trend',C(r['trend'] for r in rows if r['inlist']), 'live',C(r['live'] for r in rows if r['inlist']),'lane',C(r['lane'] for r in rows if r['inlist']))
print('nov5 master companies',len(nov5_master),'in list',len(nov5_master&members),'nov5 ppc',len(nov5_ppc),'in list',len(nov5_ppc&members))
def show(title,f):
    L=[r for r in cand if f(r)]; print('\n##',title,len(L))
    for r in L[:40]: print('  ',r['id'],r['name'][:40],r['tier'],r['trend'],r['mpm'],'sf=',r['sf'],'lane=',r['lane'],r['stages'],'list=',r['inlist'])
show('sparefoot blank (falls out, no task)',lambda r:r['sf'] not in ('true','false'))
show('mpm blank/Not Assigned (unassigned task) non-T3',lambda r:r['mpm'] in (None,'','Not Assigned') and r['tier']!='TIER 3')
show('Tier3 with named MPM',lambda r:r['tier']=='TIER 3' and r['mpm'] not in (None,'','Not Assigned'))
show('MPM Mohammad',lambda r:r['mpm']=='Mohammad Abudahab')
show('Ent/T1 not Brock',lambda r:r['tier'] in('Enterprise','TIER 1') and r['mpm']!='Brock Hegr')
show('T2.2 not Sarah',lambda r:r['tier']=='Tier 2 - L2' and r['mpm']!='Sarah Schlosberg')
show('no Marketing ticket',lambda r:r['ntk']==0)
show('multiple Marketing tickets',lambda r:r['ntk']>1)
show('ticket in closed/transitions stage',lambda r:any(s in('PPC Enrolled No (closed)','Transitions') or '/' in s for s in r['stages']))
show('tier vs lane mismatch',lambda r:r['lane'] not in ('MULTI','NONE','Standalone - Marketing') and {'Enterprise':'Enterprise','TIER 1':'Tier 1','TIER 2':'Tier 2.1','Tier 2 - L2':'Tier 2.2','TIER 3':'Tier 3'}.get(r['tier'])!=r['lane'])
show('in suppression list now',lambda r:r['inlist'])
show('atrisk AND standalone',lambda r:r['trend']=='At Risk' and r['wf_sa'])
