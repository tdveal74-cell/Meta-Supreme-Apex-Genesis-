"""Build the standalone Jev image-lane harness, ruled by Tee 2026-10-27 on a card,
"Standalone harness".

    python3 n8n/tqo-v5/jev-harness/build_harness.py OUT.json

The lane code is read from n8n/tqo-v5 unchanged. The upstream nodes are stubs named
like the live nodes, fed from fixtures/pexels_video_search_2221.json. Thumb:
Download Still and Thumb: Compose are copied from the export, where they equal the
live version fc75f7a6. The workflow it builds holds no key: the Jev nodes name the
n8n credential by id. harness_as_run_4737.json is the exact body that ran.
"""
import copy
import json
import os
import sys

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
OUT = sys.argv[1]
def src(f):
    return open(REPO + f).read()


fx = json.load(open(REPO + 'fixtures/pexels_video_search_2221.json'))
live = {n['name']: n for n in json.load(open(REPO + 'exports/qEkGOUsNyVaRAmm6_active.json'))['nodes']}

STUB = '// HARNESS STUB, not the live node. Same name as the live node so the unmodified lane code finds it.\n'
seg0 = dict(fx['segment'], narration='Open the workflow dashboard and read it before you change anything.', videoTitle='Jev harness, not for the channel')
seg1 = dict(seg0, segIndex=1, start=8, duration=8, narration='A laptop screen shows the queue of tasks waiting for review.')
segs_code = STUB + 'return ' + json.dumps([{'json': seg0}, {'json': seg1}]) + ';'
pexels_code = STUB + '// Both segments get the real Pexels response read in execution 2221 on 2026-10-06.\nconst px = ' + json.dumps(fx['pexels']) + ';\nreturn [{ json: px }, { json: JSON.parse(JSON.stringify(px)) }];'
attach_code = STUB + "return [{ json: { presenterClips: [], rowId: 'harness', videoTitle: 'Jev harness, not for the channel' } }];"
plan = {'airtableId': 'harness', 'brand': 'The Quiet Operator', 'kicker': 'THE QUIET OPERATOR', 'headline': 'READ THE DASHBOARD FIRST',
        'headlineSource': 'harness', 'query': 'laptop workflow screen', 'queryRaw': 'laptop workflow screen', 'isNCO': False}
plan_code = STUB + 'return [{ json: ' + json.dumps(plan) + ' }];'
photos = [{'id': v['id'], 'photographer': 'Pexels video poster, harness fixture', 'url': v.get('url'),
           'src': {'landscape': v['image'], 'large': v['image']}} for v in fx['pexels']['videos'][:3]]
find_code = STUB + '// Stands in for a /v1/search photo response with three Pexels VIDEO POSTERS from execution 2221.\nreturn [{ json: ' + json.dumps({'page': 1, 'per_page': 3, 'photos': photos, 'total_results': 3}) + ' }];'

def code(name, js, pos):
    return {'name': name, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': pos, 'parameters': {'jsCode': js}}
def fetch(name, url_expr, pos):
    return {'name': name, 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': pos,
            'parameters': {'url': url_expr, 'options': {'response': {'response': {'responseFormat': 'file'}}, 'timeout': 10000}},
            'onError': 'continueRegularOutput', 'alwaysOutputData': True}
def b64(name, prop, pos):
    return {'name': name, 'type': 'n8n-nodes-base.extractFromFile', 'typeVersion': 1.1, 'position': pos,
            'parameters': {'operation': 'binaryToPropery', 'binaryPropertyName': prop, 'destinationKey': 'still_b64'},
            'onError': 'continueRegularOutput'}
def jev(name, pos):
    return {'name': name, 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': pos,
            'parameters': {'method': 'POST', 'url': 'https://api.typesafe.ai/v1/systemone', 'authentication': 'genericCredentialType',
                           'genericAuthType': 'httpHeaderAuth', 'sendHeaders': True,
                           'headerParameters': {'parameters': [{'name': 'TypeSafe-Danger-Zone-Images', 'value': 'true'}]},
                           'sendBody': True, 'specifyBody': 'json', 'jsonBody': '={{ JSON.stringify($json.body) }}', 'options': {'timeout': 30000}},
            'credentials': {'httpHeaderAuth': {'id': 'AJM16uvmcW88bSL4', 'name': 'Jev'}},
            'onError': 'continueRegularOutput', 'alwaysOutputData': True}
def real(name, pos):
    n = copy.deepcopy(live[name])
    keep = {k: n[k] for k in ('name', 'type', 'typeVersion', 'parameters')}
    for k in ('onError', 'alwaysOutputData', 'retryOnFail', 'maxTries', 'waitBetweenTries'):
        if n.get(k) is not None:
            keep[k] = n[k]
    keep['position'] = pos
    return keep

nodes = [
    {'name': 'Run Harness', 'type': 'n8n-nodes-base.manualTrigger', 'typeVersion': 1, 'position': [0, 400], 'parameters': {}},
    code('Plan B-Roll Segments', segs_code, [250, 100]),
    code('Pexels Search', pexels_code, [500, 100]),
    code('Jev: B-Roll Stills', src('jev_broll_stills.js'), [750, 0]),
    fetch('Jev: Fetch B-Roll Still', '={{ $json.stillUrl }}', [1000, 0]),
    b64('Jev: Still To Base64', 'data', [1250, 0]),
    code('Jev: B-Roll Bodies', src('jev_broll_bodies.js'), [1500, 0]),
    jev('Jev: Rank B-Roll', [1750, 0]),
    code('Presenter: Attach Clips', attach_code, [750, 200]),
    code('Build Movie', src('build_movie.js'), [1000, 200]),
    code('Thumb: Plan', plan_code, [250, 600]),
    code('Thumb: Find Still', find_code, [500, 600]),
    code('Jev: Thumb Stills', src('jev_thumb_stills.js'), [750, 500]),
    fetch('Jev: Fetch Thumb Still', '={{ $json.fetchUrl }}', [1000, 500]),
    b64('Jev: Thumb To Base64', 'data', [1250, 500]),
    code('Jev: Thumb Body', src('jev_thumb_body.js'), [1500, 500]),
    jev('Jev: Rank Stills', [1750, 500]),
    code('Thumb: Pick Still', src('thumb_pick_still.js'), [750, 700]),
    real('Thumb: Download Still', [1000, 700]),
    real('Thumb: Compose', [1250, 700]),
    b64('Jev: Thumb To Base64 (Composed)', 'thumbData', [1500, 620]),
    code('Jev: Thumb Check Body', src('jev_thumb_check_body.js'), [1750, 620]),
    jev('Jev: Check Thumb', [2000, 620]),
    code('Jev: Thumb Verdict', src('jev_thumb_check_verdict.js'), [2250, 620]),
    code('Shim: Thumbnail To Binary', src('shim_thumbnail_to_binary.js'), [1500, 800]),
]
edges = [('Run Harness', 'Plan B-Roll Segments'), ('Run Harness', 'Thumb: Plan'), ('Plan B-Roll Segments', 'Pexels Search'),
         ('Pexels Search', 'Jev: B-Roll Stills'), ('Jev: B-Roll Stills', 'Jev: Fetch B-Roll Still'), ('Jev: Fetch B-Roll Still', 'Jev: Still To Base64'),
         ('Jev: Still To Base64', 'Jev: B-Roll Bodies'), ('Jev: B-Roll Bodies', 'Jev: Rank B-Roll'),
         ('Pexels Search', 'Presenter: Attach Clips'), ('Presenter: Attach Clips', 'Build Movie'),
         ('Thumb: Plan', 'Thumb: Find Still'), ('Thumb: Find Still', 'Jev: Thumb Stills'), ('Jev: Thumb Stills', 'Jev: Fetch Thumb Still'),
         ('Jev: Fetch Thumb Still', 'Jev: Thumb To Base64'), ('Jev: Thumb To Base64', 'Jev: Thumb Body'), ('Jev: Thumb Body', 'Jev: Rank Stills'),
         ('Thumb: Find Still', 'Thumb: Pick Still'), ('Thumb: Pick Still', 'Thumb: Download Still'), ('Thumb: Download Still', 'Thumb: Compose'),
         ('Thumb: Compose', 'Jev: Thumb To Base64 (Composed)'), ('Jev: Thumb To Base64 (Composed)', 'Jev: Thumb Check Body'),
         ('Jev: Thumb Check Body', 'Jev: Check Thumb'), ('Jev: Check Thumb', 'Jev: Thumb Verdict'), ('Thumb: Compose', 'Shim: Thumbnail To Binary')]
conns = {}
for a, b in edges:
    conns.setdefault(a, {'main': [[]]})['main'][0].append({'node': b, 'type': 'main', 'index': 0})
names = {n['name'] for n in nodes}
assert all(a in names and b in names for a, b in edges), 'edge to a missing node'
assert len(names) == len(nodes)
wf = {'name': 'HARNESS Jev image lanes (inactive, archive after one run)', 'nodes': nodes, 'connections': conns,
      'settings': {'executionOrder': 'v1', 'binaryMode': 'separate', 'saveManualExecutions': True, 'saveDataSuccessExecution': 'all',
                   'saveDataErrorExecution': 'all', 'saveExecutionProgress': True, 'timezone': 'America/New_York',
                   'callerPolicy': 'workflowsFromSameOwner', 'availableInMCP': True}}
json.dump(wf, open(OUT, 'w'))
print(len(nodes), 'nodes', len(edges), 'edges', len(json.dumps(wf)), 'bytes')
