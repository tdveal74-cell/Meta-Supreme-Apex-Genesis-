"""Host-controlled profile binding and local AI receipt lookup.

No write-capable HTTP service is exposed. The model
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
