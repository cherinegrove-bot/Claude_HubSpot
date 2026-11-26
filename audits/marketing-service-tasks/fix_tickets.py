import sys,json; sys.path.insert(0,'.')
from pull import *
from collections import Counter
R=json.load(open('rows2.json'))
tk=search('tickets',[{'propertyName':'hs_pipeline','operator':'EQ','value':'916005534'}],['subject','hs_pipeline_stage'])
print('Marketing Services tickets',len(tk))
a=assoc('tickets','companies',[t['id'] for t in tk])
STG={'1396673189':'Transitions','1396876936':'Enterprise','1396876937':'Tier 1','1396876938':'Tier 2.1','1396876939':'Tier 2.2','1396876940':'Tier 3','1396876941':'Standalone - Marketing','1408106337':'PPC Enrolled No (closed)'}
stage={t['id']:STG.get(t['properties']['hs_pipeline_stage'],t['properties']['hs_pipeline_stage']) for t in tk}
lab={};unl={}
for tid,L in a.items():
    for x in L:
        c=str(x['toObjectId']); labs=[l.get('label') for l in x['associationTypes']]
        (lab if 'Marketing' in labs else unl).setdefault(c,[]).append(tid)
lists=lambda r:r['L5523'] or r['L5525'] or r['L5527'] or r['L5529']
for r in R:
    r['mk_ticket']=[(t,stage[t]) for t in lab.get(r['id'],[])]
    r['unlabelled_mk_ticket']=[(t,stage[t]) for t in unl.get(r['id'],[])]
    r['ntk']=len(r['mk_ticket']); r['stages']=[s for _,s in r['mk_ticket']]
json.dump(R,open('rows2.json','w'),indent=1)
L=[r for r in R if lists(r)]
print('list companies: marketing-labelled MS tickets',Counter(r['ntk'] for r in L))
print('no labelled', [(r['name'],r['unlabelled_mk_ticket']) for r in L if r['ntk']==0])
print('multiple labelled',[(r['name'],r['mk_ticket']) for r in L if r['ntk']>1])
print('closed/transition stage',[(r['name'],r['stages']) for r in L if any(s in('PPC Enrolled No (closed)','Transitions') for s in r['stages'])])
