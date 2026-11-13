"""Exercise the actual task runner and its checked resume without GPU or network."""
from pathlib import Path
import json, sys, tempfile
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'pipeline'))
from binder_campaign.runner import run_task
with tempfile.TemporaryDirectory() as temp:
 p=Path(temp)
 producer=p/'producer.py'
 producer.write_text('import json\nfrom pathlib import Path\nPath("metrics.json").write_text(json.dumps({"value":1.0}))\n')
 spec={'cwd':str(p),'revision':'offline-demo-v1','command':[sys.executable,str(producer)],'inputs':['producer.py'],'outputs':[{'path':'metrics.json','kind':'metrics_json','finite_keys':['value']}],'timeout_seconds':30,'state':'state.json','log':'run.log'}
 (p/'task.json').write_text(json.dumps(spec))
 first=run_task(p/'task.json');second=run_task(p/'task.json')
 assert first['status']=='success' and second['resumed'] is True
 print('PASS: real subprocess, validated metrics and hash-checked resume; no GPU used')
