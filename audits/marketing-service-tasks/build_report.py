"""Build the Marketing Service Task Audit HTML.
Usage: python3 -I build_report.py <rows2.json from step2b.py> <out.html> <template.html>
Template placeholders: {{N.x}} numbers, {{C.x}} table counts, {{T.x}} tables."""
import json,sys,html
rows=json.load(open(sys.argv[1])); OUT=sys.argv[2]; tpl=open(sys.argv[3]).read()
PORTAL='45059701'
LISTS={'5523':'At Risk','5525':'Improving','5527':'Standalone'}
def link(r): return f'<a href="https://app.hubspot.com/contacts/{PORTAL}/record/0-2/{r["id"]}" target="_blank" rel="noopener">{html.escape(r["name"])}</a>'
TIER={'Enterprise':'Enterprise','TIER 1':'Tier 1','TIER 2':'Tier 2.1','Tier 2 - L2':'Tier 2.2','TIER 3':'Tier 3','N/A':'N/A',None:'—'}
def table(L,cols):
    if not L: return '<p class="empty">None found.</p>'
    h='<div class="tw"><table><thead><tr>'+''.join(f'<th>{c}</th>' for c,_ in cols)+'</tr></thead><tbody>'
    for r in L: h+='<tr>'+''.join(f'<td>{f(r)}</td>' for _,f in cols)+'</tr>'
    return h+'</tbody></table></div>'
def wf(r): return ', '.join(v for k,v in LISTS.items() if r['L'+k]) or '—'
def exp_owner(r):
    if r['L5527']: return r['mpm'] or 'Brock (default)'
    if r['tier'] in('Enterprise','TIER 1'): return 'Brock Hegr'
    if r['tier']=='Tier 2 - L2': return 'Sarah Schlosberg'
    if r['tier']=='TIER 3': return 'Pool (unassigned)'
    return r['mpm'] or '—'
def wf_owner(r): return r['mpm'] if r['mpm'] in('Brock Hegr','Sarah Schlosberg','Mohammad Abudahab') else 'Unassigned (queue)'
BASE=[('Company',link),('Tier',lambda r:TIER.get(r['tier'],r['tier'])),('Trend',lambda r:r['trend'] or '—'),('MPM',lambda r:r['mpm'] or '<span class="muted">blank</span>')]
rev=[r for r in rows if r['L5523'] or r['L5525'] or r['L5527']]
ppc=[r for r in rows if r['L5529']]; sup=[r for r in rows if r['L5466']]
by=lambda L:sorted(L,key=lambda r:r['name'].lower())
sets={
 'noticket':(by([r for r in rows if (r in rev or r in ppc) and r['ntk']==0]),BASE+[('Review list',wf),('PPC list',lambda r:'Yes' if r['L5529'] else '—'),('Suppressed',lambda r:'Yes' if r['L5466'] else '—')]),
 'owner':(by([r for r in rev if (r['tier'] in('Enterprise','TIER 1') and r['mpm']!='Brock Hegr') or (r['tier']=='TIER 3' and not r['L5527'] and r['mpm'] not in(None,'','Not Assigned'))]),BASE+[('Sheet owner',exp_owner),('Workflow will assign',wf_owner)]),
 'ppcexcl':(by([r for r in rows if r['live']=='Yes' and not r['L5466'] and ((r['trend']=='At Risk' and r['tier'] in('Enterprise','TIER 1','TIER 2','Tier 2 - L2','TIER 3') and not r['L5523']) or (r['trend']=='Improving' and r['tier'] in('Enterprise','TIER 1','TIER 2') and not r['L5525'])) and not r['L5527']]),BASE+[('PPC Enrolled',lambda r:{'true':'Yes','false':'No'}.get(r['ppc_en'],r['ppc_en'] or 'blank'))]),
 'supp':(by(sup),BASE+[('Status',lambda r:r['live']),('In PPC list',lambda r:'Yes' if r['L5529'] else '—')]),
 'review':(by(rev),BASE+[('Workflow',wf),('Owner on task',wf_owner),('SpareFoot',lambda r:{'true':'Yes','false':'No'}.get(r['sf'],'blank')),('PPC task too',lambda r:'Yes' if r['L5529'] else '—')]),
}
N=dict(ar=sum(r['L5523'] for r in rows),im=sum(r['L5525'] for r in rows),sa=sum(r['L5527'] for r in rows),rev=len(rev),ppc=len(ppc),sup=len(sup),
       ppc_rev=sum(1 for r in ppc if r in rev),ppc_sup=sum(1 for r in ppc if r['L5466']),
       ar_excl=sum(1 for r in sets['ppcexcl'][0] if r['trend']=='At Risk'),im_excl=sum(1 for r in sets['ppcexcl'][0] if r['trend']=='Improving'))
out=tpl
for k,v in N.items(): out=out.replace('{{N.'+k+'}}',str(v))
for k,(L,cols) in sets.items(): out=out.replace('{{C.'+k+'}}',str(len(L))).replace('{{T.'+k+'}}',table(L,cols))
assert '{{' not in out, out[out.index('{{'):out.index('{{')+40]
open(OUT,'w').write(out); print('written',N,{k:len(v[0]) for k,v in sets.items()})
