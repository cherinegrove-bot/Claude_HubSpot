"""Build the Marketing Service Task Audit HTML from rows.json (step3.py output).
Usage: python3 -I build_report.py <rows.json> <out.html>
Findings text is maintained below; data tables are generated."""
import json,sys,html
rows=json.load(open(sys.argv[1])); OUT=sys.argv[2]
PORTAL='45059701'
def link(r): return f'<a href="https://app.hubspot.com/contacts/{PORTAL}/record/0-2/{r["id"]}" target="_blank" rel="noopener">{html.escape(r["name"])}</a>'
TIER={'Enterprise':'Enterprise','TIER 1':'Tier 1','TIER 2':'Tier 2.1','Tier 2 - L2':'Tier 2.2','TIER 3':'Tier 3','N/A':'N/A',None:'—'}
def table(L,cols):
    if not L: return '<p class="empty">None found.</p>'
    h='<div class="tw"><table><thead><tr>'+''.join(f'<th>{c}</th>' for c,_ in cols)+'</tr></thead><tbody>'
    for r in L: h+='<tr>'+''.join(f'<td>{f(r)}</td>' for _,f in cols)+'</tr>'
    return h+'</tbody></table></div>'
C_STD=[('Company',link),('Tier',lambda r:TIER.get(r['tier'],r['tier'])),('Trend',lambda r:r['trend'] or '—'),('MPM',lambda r:r['mpm'] or '<span class="muted">blank</span>'),('Ticket lane',lambda r:', '.join(r['stages']) or '<span class="muted">no Marketing ticket</span>')]
cand=[r for r in rows if r['wf_atrisk'] or r['wf_impr'] or r['wf_sa']]
ppc=[r for r in rows if r['wf_ppc']]
inlist=[r for r in rows if r['inlist']]
sets={
 'supp':sorted(inlist,key=lambda r:r['name']),
 'noticket':sorted([r for r in cand if r['ntk']==0],key=lambda r:r['name']),
 'closed':sorted([r for r in cand if any('closed' in s or s=='Transitions' for s in r['stages'])],key=lambda r:r['name']),
 'entsarah':sorted([r for r in cand if r['tier'] in('Enterprise','TIER 1') and r['mpm']!='Brock Hegr'],key=lambda r:r['name']),
 't3named':sorted([r for r in cand if r['tier']=='TIER 3' and r['mpm'] not in(None,'','Not Assigned') and not r['wf_sa']],key=lambda r:r['name']),
 'blankmpm':sorted([r for r in cand if r['mpm'] in(None,'','Not Assigned') and r['tier']!='TIER 3'],key=lambda r:r['name']),
 'imprinel':sorted([r for r in rows if r['trend']=='Improving' and r['live']=='Yes' and not r['wf_impr'] and not r['wf_sa']],key=lambda r:r['name']),
}
live=[r for r in cand if not r['inlist']]
N=dict(atrisk=sum(r['wf_atrisk'] for r in cand),impr=sum(r['wf_impr'] for r in cand),sa=sum(r['wf_sa'] for r in cand),cand=len(cand),
       live=len(live),ppc=len(ppc),ppclive=sum(1 for r in ppc if not r['inlist']),supp=len(inlist),
       supp_nov5m=sum(r['nov5m'] for r in inlist),supp_not_nov5m=sum(1 for r in inlist if not r['nov5m']))
data=dict(N=N,tables={k:table(v,C_STD+([('In supp. list',lambda r:'Yes' if r['inlist'] else '')] if k!='supp' else [('Nov 5 review task',lambda r:'Yes' if r['nov5m'] else '—'),('Nov 5 PPC task',lambda r:'Yes' if r['nov5p'] else '—')])) for k,v in sets.items()},counts={k:len(v) for k,v in sets.items()})
tpl=open(sys.argv[3]).read() if len(sys.argv)>3 else None
out=tpl
for k,v in N.items(): out=out.replace('{{N.'+k+'}}',str(v))
for k,v in data['counts'].items(): out=out.replace('{{C.'+k+'}}',str(v))
for k,v in data['tables'].items(): out=out.replace('{{T.'+k+'}}',v)
open(OUT,'w').write(out)
print('written',OUT,N,data['counts'])
