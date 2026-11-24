import json,os,urllib.request,time
B='https://api.hubapi.com'; H={'Authorization':'Bearer '+os.environ['HUBSPOT_ACCESS_TOKEN'],'Content-Type':'application/json'}
def req(path,body=None,method=None):
    for i in range(5):
        try:
            r=urllib.request.Request(B+path,data=json.dumps(body).encode() if body is not None else None,headers=H,method=method or ('POST' if body is not None else 'GET'))
            return json.load(urllib.request.urlopen(r))
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(2); continue
            raise Exception(e.read().decode())
def search(obj,filters,props,groups=None):
    out=[];after=None
    while True:
        b={'filterGroups':groups or [{'filters':filters}],'properties':props,'limit':100}
        if after: b['after']=after
        d=req(f'/crm/v3/objects/{obj}/search',b); out+=d['results']
        after=d.get('paging',{}).get('next',{}).get('after')
        if not after: return out
        time.sleep(0.25)
def batch_read(obj,ids,props):
    out=[]
    for i in range(0,len(ids),100):
        out+=req(f'/crm/v3/objects/{obj}/batch/read',{'inputs':[{'id':x} for x in ids[i:i+100]],'properties':props})['results']
    return out
def assoc(frm,to,ids):
    out={}
    for i in range(0,len(ids),1000):
        d=req(f'/crm/v4/associations/{frm}/{to}/batch/read',{'inputs':[{'id':x} for x in ids[i:i+1000]]})
        for r in d['results']: out[r['from']['id']]=r['to']
    return out
