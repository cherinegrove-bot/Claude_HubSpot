"""Downloads the workflow configuration (Automation v4 API) for the 13 in-scope workflows into cfg/."""
import json, os, urllib.request
IDS = ['1670039203', '1866384267', '1866658899', '1866664080', '1866664222', '1866664327', '1866659765', '1867929348',
       '1699704693', '1699666189', '1699704743', '1699730300', '1699702705']
H = {'Authorization': 'Bearer ' + os.environ['HUBSPOT_ACCESS_TOKEN']}
os.makedirs('cfg', exist_ok=True)
for i in IDS:
    d = json.load(urllib.request.urlopen(urllib.request.Request(f'https://api.hubapi.com/automation/v4/flows/{i}', headers=H)))
    json.dump(d, open(f'cfg/{i}.json', 'w'), indent=1)
    print(i, d['name'])
r = json.load(urllib.request.urlopen(urllib.request.Request('https://api.hubapi.com/crm/v3/pipelines/deals', headers=H)))
json.dump(r, open('deal_pipes.json', 'w'))
