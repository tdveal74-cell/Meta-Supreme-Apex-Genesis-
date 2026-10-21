"""Deterministic AI-review validation. A signed AI record is NOT human approval.

Signatures attest to an observed model run and validated evidence references;
they do not certify that the model or the supplied source snapshots are true.
Only the host-owned orchestrator may call sign_receipt with its private key.
"""
from __future__ import annotations
import base64, copy, datetime as dt, hashlib, json, re
from typing import Any

BRANDS = ('TQO','NCO_FORGE','TSWS','ACX','EDITFORGE','WHATBROKE','DEVON','META_SUPREME_X')
POLICY = 'ecosystem-quality90-ai-v2'
SCHEMA = 'devon-ai-review-receipt-v1'
UTC = dt.timezone.utc
ALIASES = {'NCO':'NCO_FORGE','NCO FORGE':'NCO_FORGE','THE QUIET OPERATOR':'TQO',
           'THE SHADOW WE SHARE':'TSWS','META SUPREME X':'META_SUPREME_X'}
PROVIDERS = {'openai':'openai','chatgpt':'openai','codex':'openai','anthropic':'anthropic',
             'claude':'anthropic','google':'google','gemini':'google','human':'human'}

def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def canonical(value: Any) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def nonempty(value: Any) -> bool:
    return isinstance(value,str) and bool(value.strip())

def route_reviewer(provider: str) -> str:
    if not isinstance(provider,str) or provider.lower().strip() not in PROVIDERS:
        raise ValueError('producer provider must be explicitly identified')
    return 'gemini' if PROVIDERS[provider.lower().strip()]=='anthropic' else 'claude'

def prepare_packet(request: dict) -> dict:
    if not isinstance(request,dict): raise ValueError('object request required')
    brand=str(request.get('brand','')).upper().strip();brand=ALIASES.get(brand,brand)
    if brand not in BRANDS: raise ValueError('unregistered brand')
    provider=request.get('producerProvider','');reviewer=route_reviewer(provider)
    for field in ('artifact','rubricVersion','brandRules'):
        if not nonempty(request.get(field)): raise ValueError('missing '+field)
    sources=request.get('sources')
    if not isinstance(sources,list) or not sources or len(sources)>50:
        raise ValueError('1 to 50 source snapshots required')
    clean=[];seen=set()
    for source in sources:
        if not isinstance(source,dict) or any(not nonempty(source.get(k)) for k in ('id','reference','text','sha256')):
            raise ValueError('complete source identity/text/hash required')
        if source['id'] in seen or source['sha256']!=digest(source['text']):
            raise ValueError('duplicate source or wrong snapshot hash')
        if source.get('kind') not in ('source','canon'): raise ValueError('unknown source kind')
        seen.add(source['id']);clean.append({k:source[k] for k in ('id','reference','kind','text','sha256')})
    if brand in ('TSWS','ACX') and not any(s['kind']=='canon' for s in clean):
        raise ValueError('current applicable canon snapshot required')
    p={'policyVersion':POLICY,'brand':brand,'producerProvider':PROVIDERS[provider.lower().strip()],
       'reviewer':reviewer,'artifact':request['artifact'],'artifactSha256':digest(request['artifact']),
       'rubricVersion':request['rubricVersion'],'brandRules':request['brandRules'],
       'rulesSha256':digest(request['brandRules']),'sources':clean}
    if len(canonical(p))>100000: raise ValueError('packet exceeds safe included-usage size cap')
    p['packetId']=hashlib.sha256(canonical(p)).hexdigest()
    return p

def packet_valid(packet: dict) -> bool:
    try:
        return isinstance(packet,dict) and prepare_packet(packet)==packet
    except (ValueError,TypeError,KeyError): return False

def hold(reason: str) -> dict:
    return {'state':'HOLD','reason':reason,'threshold':90,'reviewKind':'AI_REVIEW',
            'humanApprovalRequired':True,'publicationAuthorized':False,'spendAuthorized':False}

def validate_report(packet: dict, report: dict) -> dict:
    if not packet_valid(packet):return hold('final artifact/source/rules identity invalid')
    if not isinstance(report,dict):return hold('model output is not a report')
    if report.get('packetId')!=packet['packetId'] or report.get('artifactSha256')!=packet['artifactSha256']:
        return hold('review is not tied to the exact final artifact and packet')
    score=report.get('score')
    if type(score) is not int or not 90<=score<=100 or report.get('verdict')!='PASS':
        return hold('quality score below 90, invalid, or not PASS')
    if report.get('coverageComplete') is not True:return hold('review coverage incomplete')
    checks=report.get('checks')
    if not isinstance(checks,dict) or any(checks.get(k) is not True for k in ('evidence','voice','brandRules')):
        return hold('evidence, voice or brand check did not pass')
    if packet['brand'] in ('TSWS','ACX') and checks.get('canon') is not True:
        return hold('required canon check did not pass')
    findings=report.get('findings')
    if not isinstance(findings,list):return hold('findings not declared')
    for finding in findings:
        if not isinstance(finding,dict) or finding.get('severity') not in ('INFO','LOW','MEDIUM'):
            return hold('unresolved critical/high/blocker finding or invalid severity')
    claims=report.get('claims')
    if not isinstance(claims,list) or not claims:return hold('no evidence-linked coverage')
    sources={s['id']:s for s in packet['sources']}
    for claim in claims:
        if not isinstance(claim,dict) or claim.get('status')!='SUPPORTED':return hold('unverified or contradicted claim')
        aq,sq=claim.get('artifactQuote'),claim.get('sourceQuote');src=sources.get(claim.get('sourceId'))
        if not nonempty(aq) or aq not in packet['artifact'] or not src or not nonempty(sq) or sq not in src['text']:
            return hold('evidence quotation missing from actual artifact/source snapshot')
    return {'state':'READY_FOR_TEE_REVIEW','threshold':90,'score':score,'reviewKind':'AI_REVIEW',
            'humanApprovalRequired':True,'publicationAuthorized':False,'spendAuthorized':False}

def utcnow() -> dt.datetime: return dt.datetime.now(UTC)

def sign_receipt(packet: dict, report: dict, observation: dict, private_key: Any, *, now=None) -> dict:
    """Host orchestration only. Never expose this key or function to model tools."""
    now=now or utcnow()
    if not packet_valid(packet):raise ValueError('invalid packet')
    expected='anthropic' if packet['reviewer']=='claude' else 'google'
    if (not isinstance(observation,dict) or observation.get('provider')!=expected or
        observation.get('provider')==packet['producerProvider'] or
        observation.get('source')!='observed_cli_run' or
        not nonempty(observation.get('model')) or not nonempty(observation.get('sessionId'))):
        raise ValueError('observed different-provider runtime provenance required')
    result=validate_report(packet,report)
    payload={'schemaVersion':SCHEMA,'issuer':'DEVON-AI-review-orchestrator',
             'reviewKind':'AI_REVIEW','packetId':packet['packetId'],'artifactSha256':packet['artifactSha256'],
             'policyVersion':POLICY,'brand':packet['brand'],'producerProvider':packet['producerProvider'],
             'reviewer':packet['reviewer'],'rulesSha256':packet['rulesSha256'],
             'rubricVersion':packet['rubricVersion'],'report':copy.deepcopy(report),
             'reportSha256':hashlib.sha256(canonical(report)).hexdigest(),
             'observation':copy.deepcopy(observation),'score':report.get('score'),
             'validation':result,'issuedAt':now.isoformat(),
             'expiresAt':(now+dt.timedelta(hours=24)).isoformat(),
             'humanApproval':None,'publicationAuthorized':False,'spendAuthorized':False,
             'limitation':'AI assessment of supplied snapshots, not a human audit or a guarantee of truth.'}
    return {'payload':payload,'signature':base64.b64encode(private_key.sign(canonical(payload))).decode('ascii')}

def verify_receipt(receipt: dict, packet: dict, public_key: Any, *, now=None) -> dict:
    now=now or utcnow()
    try:
        if not packet_valid(packet):return hold('current final packet invalid or changed')
        p=receipt['payload'];sig=base64.b64decode(receipt['signature'],validate=True)
        public_key.verify(sig,canonical(p))
        if p['schemaVersion']!=SCHEMA or p['reviewKind']!='AI_REVIEW' or p['issuer']!='DEVON-AI-review-orchestrator':
            return hold('wrong receipt kind or issuer')
        if p['packetId']!=packet['packetId'] or p['artifactSha256']!=packet['artifactSha256'] or p['brand']!=packet['brand']:
            return hold('reviewed artifact/brand/packet changed')
        if p['rulesSha256']!=packet['rulesSha256'] or p['rubricVersion']!=packet['rubricVersion'] or p['policyVersion']!=POLICY:
            return hold('review policy or rules changed')
        issued=dt.datetime.fromisoformat(p['issuedAt']);expiry=dt.datetime.fromisoformat(p['expiresAt'])
        if issued.tzinfo is None or expiry.tzinfo is None or issued>now+dt.timedelta(minutes=2) or now>=expiry or expiry-issued>dt.timedelta(hours=24):
            return hold('expired or future dated receipt')
        obs=p['observation'];expected='anthropic' if packet['reviewer']=='claude' else 'google'
        if obs.get('source')!='observed_cli_run' or obs.get('provider')!=expected or obs.get('provider')==packet['producerProvider']:
            return hold('reviewer independence not established')
        if p['humanApproval'] is not None or p['publicationAuthorized'] is not False or p['spendAuthorized'] is not False:
            return hold('AI receipt improperly grants human/spend authority')
        if p['reportSha256']!=hashlib.sha256(canonical(p['report'])).hexdigest():return hold('report changed')
        return validate_report(packet,p['report'])
    except Exception:
        return hold('invalid signature or malformed review receipt')

def included_usage_ok(auth: dict, usage: str) -> bool:
    if not isinstance(auth,dict) or auth.get('loggedIn') is not True or auth.get('authMethod')!='claude.ai' or auth.get('apiProvider')!='firstParty' or auth.get('subscriptionType') not in ('pro','max'):
        return False
    if not isinstance(usage,str) or 'using your subscription' not in usage.lower() or re.search(r'now\s+(?:you.re\s+)?using\s+(?:usage\s+)?credits',usage,re.I):return False
    session=re.search(r'Current session:\s*(\d+(?:\.\d+)?)% used',usage)
    week=re.search(r'Current week \(all models\):\s*(\d+(?:\.\d+)?)% used',usage)
    return bool(session and week and 0<=float(session[1])<50 and 0<=float(week[1])<50)
