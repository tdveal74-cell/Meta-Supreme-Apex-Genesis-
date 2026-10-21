"""Authenticated loopback API for AI review and no-cost receipt verification.

Expose ONLY through a TLS proxy restricted to the user's n8n host. The model
has no tools. Private receipt keys stay on this host. The API never publishes.
"""
from __future__ import annotations
import argparse,datetime as dt,hmac,json,os,pathlib,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from cryptography.hazmat.primitives import serialization
from review_core import ALIASES,BRANDS,canonical,digest,hold,prepare_packet,verify_receipt,route_reviewer
from claude_runner import review_request,safe_dir

SLUGS={'TQO':'tqo','NCO_FORGE':'nco-forge','TSWS':'tsws','ACX':'acx','EDITFORGE':'editforge','WHATBROKE':'whatbroke','DEVON':'devon','META_SUPREME_X':'meta-supreme-x'}
SCOPES={'script':'Final presenter script. Apply its actual brand/voice/evidence rules. Do not invent sources or personal experience.',
 'story':'Final dramatic story/script. Require applicable canon and no locked-rule violation.',
 'technical_output':'Technical or operating artifact. Require reproducible evidence and clear limits.',
 'policy_brief':'Short internal operating-policy brief, not a video script. No video-duration or promotional-CTA requirement.'}

def rules_for(brand,scope,brands):
    if brand not in SLUGS or scope not in SCOPES:raise ValueError('unknown brand or review scope')
    path=pathlib.Path(brands)/SLUGS[brand]
    gate=path/'gates.md';profile=path/'profile.md'
    if gate.is_symlink() or profile.is_symlink():raise ValueError('symlink rules refused')
    text=gate.read_text();voice=profile.read_text() if profile.exists() else ''
    return ('Review scope: '+SCOPES[scope]+'\nFormal acceptance: integer 90/100 or higher, all hard gates intact. '
            'Score fidelity/evidence 50, completeness for this declared scope 30, clarity/voice 20. '
            'A missing source or unresolved high defect always HOLD. Tee grants final publication approval.\n'
            'APPROVED GATES\n'+text+'\nBRAND PROFILE\n'+voice)

def bound_request(request,brands):
    if not isinstance(request,dict):raise ValueError('JSON object required')
    brand=str(request.get('brand','')).upper().strip();brand=ALIASES.get(brand,brand)
    route_reviewer(request.get('producerProvider',''))
    scope=request.get('scope','script')
    # Host rules override all caller-authored rule/rubric fields.
    result={'brand':brand,'producerProvider':request.get('producerProvider'),
       'artifact':request.get('artifact'),'sources':request.get('sources'),
       'rubricVersion':f'{brand.lower()}-{scope}-ai-v2',
       'brandRules':rules_for(brand,scope,brands)}
    prepare_packet(result)
    return result

def verify_latest(request,root,brands):
    root=pathlib.Path(root)
    try:
        brand=str(request.get('brand','')).upper().strip();brand=ALIASES.get(brand,brand)
        scope=request.get('scope','script');artifact=request.get('artifact')
        if not isinstance(artifact,str) or not artifact.strip():return hold('final artifact missing')
        rubric=f'{brand.lower()}-{scope}-ai-v2';current_rules=rules_for(brand,scope,brands)
        pub=serialization.load_pem_public_key((root/'issuer/receipt-ed25519.pub.pem').read_bytes())
        # Newer verdicts supersede older results for the same exact artifact.
        for folder in sorted((root/'runs').glob('*'),reverse=True):
            if not folder.is_dir() or folder.is_symlink():continue
            try:
                packet=json.loads((folder/'packet.json').read_text())
                if (packet.get('artifact')!=artifact or packet.get('brand')!=brand or
                    packet.get('rubricVersion')!=rubric):continue
                if packet.get('brandRules')!=current_rules:return hold('brand rules changed since the review')
                if request.get('packetId') and request['packetId']!=packet['packetId']:
                    return hold('requested evidence packet is stale')
                if request.get('sources') is not None:
                    checked=prepare_packet(bound_request(request,brands))
                    if checked['packetId']!=packet['packetId']:return hold('source/rules manifest changed')
                receipt=json.loads((folder/'receipt.json').read_text())
                result=verify_receipt(receipt,packet,pub)
                return {**result,'reviewId':folder.name,'packetId':packet['packetId'],
                        'artifactSha256':packet['artifactSha256'],'brand':brand,'scope':scope,
                        'model':receipt['payload']['observation']['model'],
                        'verifiedBy':'DEVON-AI-review-orchestrator'}
            except (OSError,ValueError,KeyError,TypeError):
                return hold('newest matching review is incomplete or corrupt')
        return hold('no AI review matches the exact final artifact and scope')
    except Exception:return hold('AI review registry or current rules unavailable')

class ReviewServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,root,brands,token):
        self.root=pathlib.Path(root);self.brands=pathlib.Path(brands);self.token=token
        self.review_lock=threading.Lock();self.recent=[]
        super().__init__(address,Handler)

class Handler(BaseHTTPRequestHandler):
    server_version='DEVON-AIReview/1'
    def log_message(self,*args):pass # Never log request text or Authorization.
    def answer(self,code,obj):
        data=canonical(obj);self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/healthz':return self.answer(200,{'status':'ok','reviewKind':'AI_REVIEW','publicationAuthorized':False})
        self.answer(404,hold('route unavailable'))
    def do_POST(self):
        if self.path not in ('/review','/verify'):return self.answer(404,hold('route unavailable'))
        supplied=self.headers.get('Authorization','')
        if not hmac.compare_digest(supplied,'Bearer '+self.server.token):return self.answer(401,hold('request authentication failed'))
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=100000 or self.headers.get('Transfer-Encoding'):raise ValueError('invalid body')
            req=json.loads(self.rfile.read(size))
            if not isinstance(req,dict):raise ValueError('object required')
        except Exception:return self.answer(400,hold('invalid review request'))
        if self.path=='/verify':return self.answer(200,verify_latest(req,self.server.root,self.server.brands))
        if req.get('reviewAuthorized') is not True:return self.answer(403,hold('explicit per-request review authorization required'))
        if not self.server.review_lock.acquire(blocking=False):return self.answer(409,hold('another review is in progress'))
        try:
            cutoff=time.time()-86400
            self.server.recent=[x for x in self.server.recent if x>cutoff]
            # Tight rollout cap; no perpetual unbounded subscription consumer.
            if len(self.server.recent)>=8:return self.answer(429,hold('daily review limit reached'))
            bound=bound_request(req,self.server.brands)
            self.server.recent.append(time.time())
            result=review_request(bound,self.server.root)
            result.pop('receiptPath',None)
            return self.answer(200,result)
        except Exception:return self.answer(400,hold('review could not be validated'))
        finally:self.server.review_lock.release()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='/opt/devon/quality90-ai-review')
    ap.add_argument('--brands',default='/opt/creator-workspace/brands');ap.add_argument('--port',type=int,default=7321)
    args=ap.parse_args();root=safe_dir(args.root);tokenfile=root/'transport.token'
    st=tokenfile.lstat()
    if tokenfile.is_symlink() or st.st_uid!=os.getuid() or st.st_mode&0o077:raise SystemExit('unsafe transport authentication file')
    token=tokenfile.read_text().strip()
    if len(token)<43:raise SystemExit('transport authentication not configured')
    ReviewServer(('127.0.0.1',args.port),root,args.brands,token).serve_forever()
if __name__=='__main__':main()
