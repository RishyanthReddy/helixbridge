"""Query-only public-target MMseqs2 search; persist ticket IDs for resumption."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

parser=argparse.ArgumentParser()
parser.add_argument("--manifest",required=True)
parser.add_argument("--output",required=True)
args=parser.parse_args()
manifest=json.loads(Path(args.manifest).read_text())
sequence=manifest["sequence"]
output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
server="https://api.colabfold.com"
headers={"User-Agent":"Changjiang-research-pipeline/0.1"}
ticket_path=output/'ticket.json'
fingerprint=hashlib.sha256(sequence.encode()).hexdigest()

def read_json(request):
    with urlopen(request,timeout=60) as response:
        return json.load(response)

if ticket_path.exists():
    ticket=json.loads(ticket_path.read_text())
    if ticket["sequence_sha256"] != fingerprint:
        raise ValueError("Target changed; use a new MSA directory")
else:
    payload=urlencode({"q":">101\n"+sequence+"\n","mode":"env"}).encode()
    reply=read_json(Request(server+'/ticket/msa',data=payload,headers=headers))
    if not reply.get('id'):
        raise RuntimeError("MSA service did not accept a ticket: "+json.dumps(reply))
    ticket={"server":server,"id":reply['id'],"sequence_sha256":fingerprint,"target_id":manifest['id'],"mode":"env","public_target_only":True}
    ticket_path.write_text(json.dumps(ticket,indent=2)+'\n')
    print('Accepted ticket',ticket['id'],flush=True)

deadline=time.monotonic()+600
while True:
    reply=read_json(Request(server+'/ticket/'+ticket['id'],headers=headers))
    print('MSA state',reply.get('status'),flush=True)
    (output/'last-status.json').write_text(json.dumps(reply,indent=2)+'\n')
    if reply['status']=='COMPLETE': break
    if reply['status'] in ('ERROR','MAINTENANCE','UNKNOWN','RATELIMIT'):
        raise RuntimeError('MSA service status: '+reply['status'])
    if time.monotonic()>deadline:
        raise TimeoutError('MSA search still pending; ticket preserved for later resumption')
    time.sleep(10)

archive=output/'result.tar.gz'
if not archive.exists():
    with urlopen(Request(server+'/result/download/'+ticket['id'],headers=headers),timeout=90) as response:
        archive.write_bytes(response.read())
entries=[]
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        if not member.name.endswith('.a3m') or not member.isfile(): continue
        if member.size > 100_000_000: raise ValueError('Unexpectedly large MSA member')
        raw=tar.extractfile(member).read().decode().replace('\x00','')
        name=None; seq=[]
        for line in raw.splitlines()+['>END']:
            if line.startswith('#'): continue
            if line.startswith('>'):
                if name is not None: entries.append((name,''.join(seq)))
                name=line[1:];seq=[]
            else: seq.append(line.strip())
seen=set(); kept=[]
for name,seq in entries:
    if not seq: continue
    aligned=''.join(x for x in seq if not x.islower())
    if len(aligned)!=len(sequence): raise ValueError('MSA alignment width mismatch')
    if seq not in seen:
        seen.add(seq);kept.append((name,seq))
if not kept or kept[0][1]!=sequence:
    raise ValueError('MSA query does not match official target')
kept=kept[:1024]
if len(kept)<2: raise ValueError('No homologs returned; do not claim MSA-conditioned screening')
path=output/'target.a3m'
path.write_text(''.join('>'+name+'\n'+seq+'\n' for name,seq in kept))
(output/'manifest.json').write_text(json.dumps({**ticket,"rows":len(kept),"msa_sha256":hashlib.sha256(path.read_bytes()).hexdigest()},indent=2)+'\n')
print('Saved target-only MSA:',len(kept),'rows',flush=True)
