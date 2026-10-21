"""Final deployment wrapper: AI review cannot reuse a stale human checkbox.
V5's existing string human_review field carries approved:<current SHA-256>.
Only an authenticated human approval action may set it; this code never does.
Repurpose's existing human QC record must identify the same final text.
"""
import argparse,copy,hashlib,json,pathlib
from build_review_integration import build, node, once

def bind_current_approval(workflow,mode):
    w=copy.deepcopy(workflow)
    if mode=='v5':
        pre=node(w,'Preflight: Can This Clear?')['parameters']
        s=pre['jsCode']
        s=once(s,'if (!(reviewRaw === true || TICKED.includes(reviewStr))) {',"if (!(aiReview.aiReviewPassed === true && reviewStr === 'approved:' + aiReview.artifactSha256)) {",'human preflight exact artifact')
        s=once(s,"blockers.push('Human Review is not ticked'","blockers.push('Human Review is not approved for this exact AI-reviewed script'",'human preflight message')
        s=once(s,"+ '. Accepted: ' + TICKED.join(', '));","+ '. Required: approved:' + (aiReview.artifactSha256 || '<current final-script SHA256>'));",'human preflight approval format')
        pre['jsCode']=s
        publish=node(w,'OS 28: Publish Gate')['parameters'];s=publish['jsCode']
        s=once(s,'gates.authorship = reviewRaw === true || TICKED.includes(reviewStr);',"gates.authorship = aiReview.aiReviewPassed === true && reviewStr === 'approved:' + aiFinalHash;",'human publisher exact artifact')
        s=once(s,"blocking.push('authorship: Human Review is not ticked'","blocking.push('authorship: Human Review is not approved for the current script hash'",'human publish message')
        s=once(s,"+ '. Accepted: ' + TICKED.join(', '));","+ '. Required: approved:' + aiFinalHash);",'human publish approval format')
        publish['jsCode']=s
    elif mode=='repurpose':
        gate=node(w,'QC Gate')['parameters'];gate['jsCode']=once(gate['jsCode'],
            "if (!h) blocks.push('no human review recorded');",
            "if (h && h.script_fingerprint !== actualFp) blocks.push('Human approval is not bound to the exact final script');\nif (!h) blocks.push('no human review recorded');",'repurpose human approval binding')
    else:raise ValueError('unknown mode')
    return w

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--expected-sha',required=True);p.add_argument('--mode',choices=['v5','repurpose'],required=True);p.add_argument('--public-key',required=True);p.add_argument('--verifier',required=True)
    a=p.parse_args();raw=pathlib.Path(a.input).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.expected_sha:raise SystemExit('HOLD: live input changed')
    source=json.loads(raw);work=source[0] if isinstance(source,list) else source
    result=bind_current_approval(build(work,a.mode,pathlib.Path(a.verifier).read_text(),pathlib.Path(a.public_key).read_text()),a.mode)
    with open(a.output,'x') as f:json.dump([result] if isinstance(source,list) else result,f,separators=(',',':'))
    pathlib.Path(a.output).chmod(0o600)
    print(json.dumps({'id':result['id'],'nodes':len(result['nodes']),'mode':a.mode,'currentHumanApprovalRequired':True,'inputSHA256':a.expected_sha,'outputSHA256':hashlib.sha256(pathlib.Path(a.output).read_bytes()).hexdigest()}))
if __name__=='__main__':main()
