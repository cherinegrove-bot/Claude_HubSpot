import json,os,urllib.request,time
H={"Authorization":"Bearer "+os.environ["HUBSPOT_ACCESS_TOKEN"],"Content-Type":"application/json"}
def req(url,body=None):
    for a in range(5):
        try:
            r=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=H,method="POST" if body is not None else "GET")
            return json.load(urllib.request.urlopen(r))
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(2*(a+1)); continue
            raise
NEW=["Transitions - Transition Kickoff Tasks (+SubTask)","Transitions - Pre Launch Setup Tasks (+SubTask)","Transitions - Launch Readiness Tasks (+SubTask)","Transitions - Go Live Execution Tasks (+SubTask)","Transitions - Final Sign Off Tasks (+SubTask)","Transitions - 30-Day Monitoring (+SubTask)","Transitions - TRANSITION COMPLETE (+SubTask)"]
OLD=["Transitions - Transition Kickoff Tasks","Transitions - Pre Launch Setup Tasks","Transitions - Launch Readiness Tasks","Transitions - Go Live Execution Tasks","Transitions - Final Sign Off Tasks","Transitions - 30-Day Monitoring","Website Only Onboarding"]
props=["hs_task_subject","hs_task_body","hs_object_source","hs_object_source_id","hs_object_source_detail_1","hs_object_source_detail_2","hs_object_source_detail_3","hs_task_is_sub_task","hs_task_parent_task_id","hs_task_sub_task_ids","hs_task_uncompleted_sub_task_ids","hubspot_owner_id","hs_createdate","hs_task_status","hs_task_priority","hs_timestamp","hs_task_type","hs_task_completion_date","hs_queue_membership_ids","hs_task_reminders","hs_task_template_id","hs_lastmodifieddate"]
tasks=[]
for wf in NEW+OLD:
    after=None
    while True:
        body={"filterGroups":[{"filters":[{"propertyName":"hs_object_source_detail_1","operator":"EQ","value":wf}]}],"properties":props,"limit":200,"sorts":[{"propertyName":"hs_createdate","direction":"ASCENDING"}]}
        if after: body["after"]=after
        d=req("https://api.hubapi.com/crm/v3/objects/tasks/search",body)
        tasks+=d["results"]; after=d.get("paging",{}).get("next",{}).get("after")
        if not after: break
        time.sleep(0.15)
    print(wf, sum(1 for t in tasks if t["properties"]["hs_object_source_detail_1"]==wf), d.get("total"))
json.dump(tasks,open("tr_tasks.json","w"))
# associations task->ticket, company, contact
assoc={}
ids=[t["id"] for t in tasks]
for obj in ["tickets","companies","contacts","deals"]:
    for i in range(0,len(ids),1000):
        d=req(f"https://api.hubapi.com/crm/v4/associations/tasks/{obj}/batch/read",{"inputs":[{"id":x} for x in ids[i:i+1000]]})
        for r in d.get("results",[]):
            assoc.setdefault(r["from"]["id"],{})[obj]=[(t["toObjectId"],[l.get("label") or l.get("typeId") for l in t["associationTypes"]]) for t in r["to"]]
json.dump(assoc,open("tr_assoc.json","w"))
owners=[];after=None
while True:
    d=req("https://api.hubapi.com/crm/v3/owners?limit=100&archived=false"+(f"&after={after}" if after else ""))
    owners+=d["results"]; after=d.get("paging",{}).get("next",{}).get("after")
    if not after: break
d=req("https://api.hubapi.com/crm/v3/owners?limit=100&archived=true"); owners+=d["results"]
json.dump(owners,open("owners.json","w"))
print(len(tasks),len(assoc),len(owners))
