import json,os,urllib.request,time
H={"Authorization":"Bearer "+os.environ["HUBSPOT_ACCESS_TOKEN"],"Content-Type":"application/json"}
def req(url,body=None):
    r=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=H,method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r))
assoc=json.load(open("tr_assoc.json"))
tids=sorted({str(x[0]) for a in assoc.values() for x in a.get("tickets",[])})
print("tickets",len(tids))
stages=["1175587148","1100007030","1298054295","1094530721","1094530722","1094530723","1094493506","1094493507","1102485356","1094530724"]
allp=req("https://api.hubapi.com/crm/v3/properties/tickets")["results"]
names={p["name"]:p for p in allp}
sp=[n for n in names if any(n.endswith(s) for s in stages) and ("date_entered" in n or "date_exited" in n)]
print(sp[:6],len(sp))
props=["subject","hs_pipeline","hs_pipeline_stage","createdate","hubspot_owner_id","hs_ticket_category","hs_object_source","hs_object_source_detail_1","closed_date","hs_is_closed","target_go_live_date"]+sp
tickets=[]
for i in range(0,len(tids),100):
    d=req("https://api.hubapi.com/crm/v3/objects/tickets/batch/read",{"inputs":[{"id":x} for x in tids[i:i+100]],"properties":props})
    tickets+=d["results"]
json.dump(tickets,open("tr_tickets.json","w"))
# pipeline properties of interest for onboarding: list custom ticket props that look transition-related
json.dump([{k:p[k] for k in ("name","label","type","fieldType")} | {"options":[o["label"] for o in p.get("options",[])][:40]} for p in allp],open("ticket_props.json","w"))
# all onboarding tickets (to find tickets with no tasks)
out=[];after=None
while True:
    b={"filterGroups":[{"filters":[{"propertyName":"hs_pipeline","operator":"EQ","value":"751582029"}]}],"properties":props,"limit":200}
    if after:b["after"]=after
    d=req("https://api.hubapi.com/crm/v3/objects/tickets/search",b); out+=d["results"]; after=d.get("paging",{}).get("next",{}).get("after")
    if not after: break
json.dump(out,open("onb_tickets.json","w")); print("onboarding tickets",len(out))
