import json,os,urllib.request
H={"Authorization":"Bearer "+os.environ["HUBSPOT_ACCESS_TOKEN"],"Content-Type":"application/json"}
def req(url,body=None):
    r=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=H,method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r))
try: print(req("https://api.hubapi.com/account-info/v3/details"))
except Exception as e: print("acct",e)
ob=json.load(open("onb_tickets.json")); ids=[t["id"] for t in ob]
out={}
for obj in ["deals","companies"]:
    d=req(f"https://api.hubapi.com/crm/v4/associations/tickets/{obj}/batch/read",{"inputs":[{"id":x} for x in ids]})
    for r in d["results"]: out.setdefault(r["from"]["id"],{})[obj]=[x["toObjectId"] for x in r["to"]]
json.dump(out,open("onb_ticket_assoc.json","w"))
dids=sorted({str(x) for v in out.values() for x in v.get("deals",[])})
deals=[]
for i in range(0,len(dids),100):
    deals+=req("https://api.hubapi.com/crm/v3/objects/deals/batch/read",{"inputs":[{"id":x} for x in dids[i:i+100]],"properties":["dealname","dealstage","pipeline","closedate","hs_is_closed_won"]})["results"]
json.dump(deals,open("onb_deals.json","w"))
print(len(out),len(deals))
