"""Build an in-memory n8n final-artifact AI review patch. Never deploys itself.
The operator must pin the input SHA, preserve rollback, and read back publication.
Only fixed HTTPS registry GETs occur; this cannot invoke a model or sign a receipt.
"""

import argparse
import copy
import hashlib
import json
import pathlib
import uuid

NAMES = ["AI Review: Final Identity", "AI Review: Fetch Receipt", "AI Review: Verified Result"]
BASE = "https://editforge.online/internal/quality90-ai"
ALIASES = {
    "TQO": "TQO",
    "THE QUIET OPERATOR": "TQO",
    "NCO": "NCO_FORGE",
    "NCO_FORGE": "NCO_FORGE",
    "NCO FORGE": "NCO_FORGE",
    "TSWS": "TSWS",
    "THE SHADOW WE SHARE": "TSWS",
    "ACX": "ACX",
    "ASCENSION CAUDEX": "ACX",
}


def once(s, old, new, label):
    if not isinstance(s, str) or s.count(old) != 1:
        raise ValueError("HOLD: " + label + " source drift")
    return s.replace(old, new)


def node(w, name):
    found = [n for n in w["nodes"] if n["name"] == name]
    if len(found) != 1:
        raise ValueError("HOLD: missing/duplicate " + name)
    return found[0]


def review_nodes(mode, verifier, pub):
    if "module.exports={verifyAIReview};" not in verifier:
        raise ValueError("validator export drift")
    validator = verifier.replace("module.exports={verifyAIReview};", "")
    is_v5 = mode == "v5"
    raw = (
        "const row=$input.first().json; const f=row.fields||row; const ctx=$('Show Context: Publish').first().json; const label=String(ctx.show||ctx.channel||'').trim().toUpperCase(); const artifact=typeof f.Script==='string'?f.Script:'';"
        if is_v5
        else "const row=$input.first().json; const f=row; const label=String(f.brand||'').trim().toUpperCase(); const artifact=typeof f.finalScript==='string'?f.finalScript:'';"
    )
    identity = (
        "const crypto=require('crypto');\n"
        + raw
        + "\nconst brand=("
        + json.dumps(ALIASES)
        + ")[label]||'UNREGISTERED';\n"
        + "const scope=['TSWS','ACX'].includes(brand)?'story':'script';\nconst artifactSha256=crypto.createHash('sha256').update(artifact,'utf8').digest('hex');\nconst aiReviewIdentity={brand,scope,artifactSha256};\nreturn [{json:{...row,aiReviewIdentity,aiReviewLookupUrl:"
        + json.dumps(BASE)
        + "+'/receipt/'+brand+'/'+scope+'/'+artifactSha256}}];"
    )
    get_artifact = (
        "const f=original.fields||original; const artifact=typeof f.Script==='string'?f.Script:'';"
        if is_v5
        else "const artifact=typeof original.finalScript==='string'?original.finalScript:'';"
    )
    verify = (
        validator
        + "\nconst original=$('AI Review: Final Identity').first().json;\n"
        + get_artifact
        + "\nconst expected={...original.aiReviewIdentity,artifact};\nconst publicKeyPem="
        + json.dumps(pub)
        + ";\nconst aiReview=verifyAIReview($input.first().json,expected,publicKeyPem);\nreturn [{json:{...original,aiReview}}];"
    )
    common = {"type": "n8n-nodes-base.code", "typeVersion": 2}
    result = []
    for name, code, pos in [(NAMES[0], identity, [400, 400]), (NAMES[2], verify, [840, 400])]:
        result.append(
            {
                **common,
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "q90/" + mode + "/" + name)),
                "name": name,
                "position": pos,
                "parameters": {"jsCode": code},
            }
        )
    fetch = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "q90/" + mode + "/" + NAMES[1])),
        "name": NAMES[1],
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [620, 400],
        "parameters": {
            "method": "GET",
            "url": "={{ $json.aiReviewLookupUrl }}",
            "options": {
                "timeout": 8000,
                "response": {"response": {"neverError": True, "responseFormat": "json"}},
            },
        },
        "onError": "continueRegularOutput",
    }
    return [result[0], fetch, result[1]]


def connect(w, source, port, old_target, new_target):
    edges = w["connections"].get(source, {}).get("main", [])
    if len(edges) <= port or len(edges[port]) != 1 or edges[port][0].get("node") != old_target:
        raise ValueError("HOLD: unexpected graph edge " + source)
    edges[port][0]["node"] = new_target


def build(workflow, mode, verifier, pub):
    w = copy.deepcopy(workflow)
    if not isinstance(w.get("nodes"), list) or any(n["name"] in NAMES for n in w["nodes"]):
        raise ValueError("HOLD: candidate already integrated or invalid")
    original_node_names = [n["name"] for n in w["nodes"]]
    original_credentials = [n.get("credentials") for n in w["nodes"]]
    w["nodes"].extend(review_nodes(mode, verifier, pub))
    w["connections"][NAMES[0]] = {"main": [[{"node": NAMES[1], "type": "main", "index": 0}]]}
    w["connections"][NAMES[1]] = {"main": [[{"node": NAMES[2], "type": "main", "index": 0}]]}
    if mode == "v5":
        connect(w, "One Row at a Time", 1, "Preflight: Can This Clear?", NAMES[0])
        w["connections"][NAMES[2]] = {
            "main": [[{"node": "Preflight: Can This Clear?", "type": "main", "index": 0}]]
        }
        pre = node(w, "Preflight: Can This Clear?")["parameters"]
        pre["jsCode"] = once(
            pre["jsCode"],
            "const blockers = [];",
            "const blockers = [];\nconst aiReview = $json.aiReview || {};\nif (aiReview.aiReviewPassed !== true) blockers.push('AI final-script review: ' + (aiReview.reason || 'verified Claude receipt missing'));",
            "preflight evidence",
        )
        publish = node(w, "OS 28: Publish Gate")["parameters"]
        guard = "const aiReview=$('AI Review: Verified Result').first().json.aiReview || {};\nconst aiFinalHash=require('crypto').createHash('sha256').update(typeof f.Script==='string'?f.Script:'','utf8').digest('hex');\nif (aiReview.aiReviewPassed!==true || aiReview.artifactSha256!==aiFinalHash || aiReview.scope!=='script') blocking.push('AI final-script review unavailable, stale, or below 90');"
        publish["jsCode"] = once(
            publish["jsCode"],
            "blocking.push('Universal 90 independent final-script receipt not yet integrated');",
            guard,
            "publish evidence hold",
        )
        doctor = node(w, "QC Doctor Gate")["parameters"]
        s = doctor["jsCode"]
        anchor = "const f = row.fields || row;"
        s = once(
            s,
            anchor,
            anchor
            + "\nconst aiReview=$('AI Review: Verified Result').first().json.aiReview || {};\nconst finalHash=require('crypto').createHash('sha256').update(typeof f.Script==='string'?f.Script:'','utf8').digest('hex');\nconst aiClear=aiReview.aiReviewPassed===true && aiReview.artifactSha256===finalHash && aiReview.scope==='script';\nconst compositeRubric='quality90-ai-v2+os28';",
            "doctor AI evidence",
        )
        s = s.replace("String(qc.artifact_hash || f.id + '-' + (f.updatedAt || ''))", "finalHash")
        s = s.replace("String(qc.rubric_version || 'os28-rev2-2026-09-30')", "compositeRubric")
        s = once(
            s,
            "  reports: [{",
            "  reports: [{scope:'script',artifactHash:finalHash,rubricVersion:compositeRubric,qcVerdict:aiClear?'PASS':'FAIL',evidenceComplete:aiClear,openP0P1:aiClear?0:1,criticalOrHigh:aiClear?0:1,score:aiClear?aiReview.score:0,reviewKind:'AI_REVIEW',reviewId:aiReview.reviewId||''}, {",
            "doctor script scope",
        )
        s = once(
            s,
            "  releaseEvidenceValidated: (verdict === 'SHIP'),",
            "  releaseEvidenceValidated: (verdict === 'SHIP' && aiClear),",
            "doctor evidence binding",
        )
        doctor["jsCode"] = s
    elif mode == "repurpose":
        validate = node(w, "Validate Handoff")["parameters"]
        s = validate["jsCode"]
        s = once(
            s,
            "const brand = String(b.brand || '');",
            "const brand = String(b.brand || '');\nconst finalScript=typeof b.finalScript==='string'?b.finalScript:'';\nif (!finalScript.trim()) return fail('finalScript is required so AI review matches the exact finished text');",
            "handoff exact text",
        )
        s = once(
            s,
            "  brand,\n  approvedBy:",
            "  brand,\n  finalScript,\n  approvedBy:",
            "handoff final text output",
        )
        validate["jsCode"] = s
        connect(w, "Valid?", 0, "Get QC Verdicts", NAMES[0])
        w["connections"][NAMES[2]] = {
            "main": [[{"node": "Get QC Verdicts", "type": "main", "index": 0}]]
        }
        gate = node(w, "QC Gate")["parameters"]
        s = gate["jsCode"]
        guard = "const ai=$('AI Review: Verified Result').first().json.aiReview||{};\nconst finalHash=require('crypto').createHash('sha256').update(v.finalScript||'','utf8').digest('hex');\nif(ai.aiReviewPassed!==true||ai.artifactSha256!==finalHash) blocks.push('Exact final-script AI review missing or stale');"
        s = once(
            s,
            "blocks.push('Universal independent final-script receipt not yet connected');",
            guard,
            "repurpose AI hold",
        )
        fingerprint = "const legacyFp=(str)=>{let h1=0xdeadbeef,h2=0x41c6ce57;for(let i=0;i<str.length;i++){let ch=str.charCodeAt(i);h1=Math.imul(h1^ch,2654435761);h2=Math.imul(h2^ch,1597334677);}h1=Math.imul(h1^(h1>>>16),2246822507)^Math.imul(h2^(h2>>>13),3266489909);h2=Math.imul(h2^(h2>>>16),2246822507)^Math.imul(h1^(h1>>>13),3266489909);return(4294967296*(2097151&h2)+(h1>>>0)).toString(16);};\nconst actualFp=legacyFp(v.finalScript||'');\nif(!s||!q||s.script_fingerprint!==actualFp||q.script_fingerprint!==actualFp) blocks.push('Recorded script/QC versions differ from the AI-reviewed final text');"
        s = once(
            s,
            "const h = latest.human && latest.human.r;",
            "const h = latest.human && latest.human.r;\n" + fingerprint,
            "repurpose actual fingerprint",
        )
        gate["jsCode"] = s
    else:
        raise ValueError("unknown mode")
    if original_credentials != [
        n.get("credentials") for n in w["nodes"][: len(original_node_names)]
    ]:
        raise ValueError("credential drift")
    if [n["name"] for n in w["nodes"][: len(original_node_names)]] != original_node_names:
        raise ValueError("node order changed")
    if (
        w.get("settings") != workflow.get("settings")
        or w.get("id") != workflow.get("id")
        or w.get("active") != workflow.get("active")
    ):
        raise ValueError("workflow identity/settings drift")
    return w


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--mode", choices=["v5", "repurpose"], required=True)
    p.add_argument("--public-key", required=True)
    p.add_argument("--verifier", required=True)
    a = p.parse_args()
    raw = pathlib.Path(a.input).read_bytes()
    if hashlib.sha256(raw).hexdigest() != a.expected_sha:
        raise SystemExit("HOLD input SHA changed")
    source = json.loads(raw)
    work = source[0] if isinstance(source, list) else source
    result = build(
        work, a.mode, pathlib.Path(a.verifier).read_text(), pathlib.Path(a.public_key).read_text()
    )
    out = [result] if isinstance(source, list) else result
    with open(a.output, "x") as f:
        json.dump(out, f, separators=(",", ":"))
    pathlib.Path(a.output).chmod(0o600)
    changed = [
        n["name"]
        for n in result["nodes"]
        if n["name"] not in [x["name"] for x in work["nodes"]]
        or n.get("parameters") != node(work, n["name"]).get("parameters")
    ]
    print(
        json.dumps(
            {
                "mode": a.mode,
                "id": result["id"],
                "originalNodes": len(work["nodes"]),
                "resultNodes": len(result["nodes"]),
                "changed": changed,
                "active": result.get("active"),
                "inputSHA256": a.expected_sha,
                "outputSHA256": hashlib.sha256(pathlib.Path(a.output).read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
