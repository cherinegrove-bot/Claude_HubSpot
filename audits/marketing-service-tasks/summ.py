import json,sys,hashlib
OWN={'87928198':'87928198','88093745':'88093745','81311893':'81311893'}
def summ(path):
    d=json.load(open(path)); A={a['actionId']:a for a in d['actions']}
    print('=====',d['id'],d['name'],'enabled=',d['isEnabled'],'rev',d['revisionId'],'updated',d['updatedAt'])
    print('enroll:',json.dumps(d['enrollmentCriteria']))
    print('suppression:',json.dumps(d.get('suppressionFilterBranch'))[:400])
    print('dataSources:',[(x['objectTypeId'],x.get('associationTypeId'),x.get('associationCategory')) for x in d.get('dataSources',[])])
    def walk(aid,ind=0,seen=set()):
        if aid is None: return
        a=A[aid]; p='  '*ind
        t=a['type']
        if t=='STATIC_BRANCH':
            print(p+f'[{aid}] BRANCH on {a["inputValue"]}')
            for b in a['staticBranches']:
                print(p+f'  = {b["branchValue"]!r} ->'); walk(b['connection']['nextActionId'],ind+2)
            if 'defaultBranch' in a: print(p+'  default ->'); walk(a['defaultBranch']['nextActionId'],ind+2)
        elif t=='LIST_BRANCH':
            for b in a['listBranches']:
                print(p+f'[{aid}] IF {b.get("branchName")}: {json.dumps(b["filterBranch"])[:600]} -> {b.get("connection")}')
                if b.get('connection'): walk(b['connection']['nextActionId'],ind+2)
            print(p+'  default ->'); walk(a.get('defaultBranch',{}).get('nextActionId'),ind+2)
        else:
            f=a.get('fields',{})
            if a.get('actionTypeId')=='0-3':
                body=f.get('body','')
                print(p+f'[{aid}] TASK subj={f.get("subject")!r} owner={f.get("owner_assignment")} queue={f.get("queue_id")} prio={f.get("priority")} due={f.get("due_time",{}).get("delta")}{f.get("due_time",{}).get("timeUnit")} type={f.get("task_type")} body#={hashlib.md5(body.encode()).hexdigest()[:6]} assoc={[(x["target"]["associationTypeId"],x["value"]["type"],x["value"].get("sourceSpec",{}).get("associationTypeId")) for x in f.get("associations",[])]} otherkeys={sorted(set(f)-{"subject","owner_assignment","queue_id","priority","due_time","task_type","body","associations","use_explicit_associations"})}')
            else:
                print(p+f'[{aid}] ACTION {a.get("actionTypeId")} v{a.get("actionTypeVersion")} {json.dumps(f)[:400]}')
            walk(a.get('connection',{}).get('nextActionId'),ind)
    walk(d['startActionId'])
for p in sys.argv[1:]: summ(p)
