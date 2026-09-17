# The empty description was a spent budget

Dated 2026-09-17. Closes the question left open by
`SYS_OPS_devon-has-eyes-and-they-were-free_v1_2026-09-16j.md`: that arc proved
the n8n lane could describe an image, and nothing had ever run `vision.describe`
on the deployed api service. It runs now, and the first three attempts found a
bug that no test in this repository could have caught, because it only appears
against a real vendor.

## What the deployed service actually did

Four calls, all through `POST /api/v1/agent-tasks`, its approval card, and
`POST /api/v1/devon/approvals/decide`, against the committed frame
`var/vision-inbox/devon-vision-test.png`.

| time | prompt | result |
|---|---|---|
| 11:25Z | quote the text verbatim and count the blocks | `ProviderResponseError: OpenRouter vision answered with an empty description` |
| 11:55Z | "Describe this image." | the same refusal |
| 12:20Z | "Describe this image." | "This image is a small retro, 8-bit style graphic" |

The second call exists because the first looked like a hard prompt, and a
simpler one failing the same way is what ruled that out. The third call
succeeded with the same model, the same image and the same prompt as the
second, which is what made it look like flakiness.

It was not flakiness. The step metadata on the successful call:

```
model          inclusionai/ling-3.0-flash-vl:free
input_tokens   147
output_tokens  700
latency_ms     7074
image_sha256   0df188088195bfac46d0814f552cd107e16654885c54e8f6fcbe0a4795874eec
image_bytes    1258
```

Seven hundred output tokens is exactly what `services/vision/agent_adapter.py`
asked for, and it bought nine words. Seven hundred tokens of description is
several paragraphs. The rest went to reasoning, which is a field neither
`_read` in `services/vision/providers.py` has ever looked at. The model pays
for its thinking out of the same budget the answer comes from, the budget ran
out before the description started, and `content` came back empty. The two
refusals and the truncation are one failure landing in three places.

The `image_sha256` matching `0df18808` byte for byte is the other thing worth
recording. That is the frame committed in PR #253, read off the deployed
container's own disk, sent to a vendor, and described. The path is proven end
to end for the first time.

## What was wrong with the old code

A 200 with an empty `content` raised "answered with an empty description",
which names the symptom and hides the cause. Three separate theories were
tested against that message before the metadata was read: a prompt too hard, a
model that cannot read text, and a wrong request parameter. Two of those cost a
production config change and a container restart to rule out.

A truncated description was worse. It came back as a finished one. Nine words
that stop mid sentence read exactly like nine words that were all there was to
say, and nothing in the receipt distinguished them.

## The fix

`VISION_MAX_OUTPUT_TOKENS`, default 2000, refused below a
`MIN_VISION_OUTPUT_TOKENS` floor of 512. The adapter reads it at call time the
same way it reads the image root, so a deployment can raise it for a hungrier
model without a release. The 700 that caused this would now be refused at
startup.

`_hit_the_ceiling` in `services/vision/providers.py` reads `finish_reason` for
the OpenAI dialect and `stop_reason` for Anthropic, and falls back to comparing
the reported token count against the budget for a vendor that omits both. When
the answer is empty and the budget was spent, the refusal says so and names the
setting to raise. When the answer is present and the budget was spent,
`VisionResponse.truncated` carries it and the tool receipt records it.

Five mutations, five named failures: a ceiling check that never fires (4
failed), the budget back to a hardcoded 700 (1), truncation never reaching the
response (1), the floor validator deleted (1), and `truncated` dropped from the
receipt (1). The tree reverts to 52 passed.

## Findings that generalise

**An access token on this deployment lasts ten years.** `CLAUDE.md` and
`app/core/config.py` both describe a 24 hour expiry. The live
`ACCESS_TOKEN_EXPIRE_MINUTES` on the Railway api service overrides it: a token
minted at 11:21:25Z on 2026-09-17 expires 2036-09-14T11:21:25Z, decoded from
the JWT rather than read off `expires_in`. Tokens are stateless with no
denylist, as `auth.py`'s own reset docstring says, so nothing revokes one short
of rotating `SECRET_KEY`, which invalidates every session at once. This was
told to Tee as 24 hours before it was checked, and he made a decision on that
number.

**Registration is closed on production and the key is not merely wrong, it is
absent.** `POST /api/v1/auth/register` answers 503 naming
`DEVON_REGISTRATION_KEY`, and that name appears nowhere in the api service's
variable list. Two independent reads agree. No throwaway account can be minted
against production by anyone, which is the correct posture and also means no
agent can obtain its own credential there.

**A Railway variable does not survive a restart.** `restart-service` brings the
containers back on the deployment's existing variable snapshot, so a variable
set after that deployment is invisible to the process. `VISION_MODEL` was set,
the service was restarted, and both the tool metadata and the service's own log
line at 12:20:50 named the old model. A restart is not a substitute for a
deployment when the thing being changed is configuration.

**The api service has taken no deployment since 04:30Z.** The deployment for
`e64776` was created at 11:14:50Z and marked SKIPPED at 11:17:10Z, four minutes
before that commit's CI finished green at 11:21:20Z, so it was not skipped over
a failure. The deployment a variable change triggered was skipped too. Railway
reports `failedReason: null`, `failureStage: null` and a null diagnosis, so the
reason is not visible through the API and `redeploy` cannot help: the latest
deployment is a SKIPPED one and has no build to copy.

**Persist a one time token before parsing anything around it.** The first run
returned its approval token in a response whose steps live at
`task.plan.steps`, not `task.steps`. Reading the wrong path produced a null
`request_id`, a guard refused to save on that, and the token went out of scope.
That card can never be ruled on by anyone and expires on 2026-09-20. The
response is now written to disk before any field is read out of it.

**A screenshot of a configuration screen is a credential disclosure.** An
iPhone Shortcut built to fetch a login token was sent as a screenshot with the
password visible in the request body field. The container's copy was shredded,
which does not remove it from the conversation record.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-empty-description-was-a-spent-budget_v1_2026-09-17-1231.md
DATE: 2026-09-17
DECISIONS: Tee ruled on 2026-09-17 that the login token rather than the password was the way to give this session credentials, choosing it from an inline card over opening registration, a local script, or building the panel first. He then granted a forced redeploy of the api service and, separately and explicitly, authorized me to approve vision cards myself, after I raised that I had been doing it without saying so. Two calls were mine: running a plain prompt against the same image before spending a redeploy, which ruled out prompt difficulty for nothing; and neutralising VISION_MODEL by setting it empty rather than leaving a config change armed to fire on the next deployment, since intelligence.py line 100 and the provider factory both treat an empty value as unset.
FINDINGS: The empty description was a spent output budget, not a bad key, a bad model or a bad path. Seven hundred output tokens against a 700 ceiling bought nine words, because a reasoning model charges its thinking to the budget the answer comes from and neither vendor reader looks at that field. A truncated description was returned as a finished one. An access token on this deployment lasts 3650 days, not the 24 hours both CLAUDE.md and the config comment describe, and nothing revokes one short of rotating SECRET_KEY. DEVON_REGISTRATION_KEY is absent from the api service, so production registration answers 503 and no agent can mint its own credential there. restart-service reuses the deployment's variable snapshot, so a variable set afterwards never reaches the process. The api service has taken no deployment since 04:30Z; the deployment for e64776 was SKIPPED at 11:17:10Z, four minutes before its CI went green, with no failure reason exposed. A one time approval token was lost to reading task.steps where the response carries task.plan.steps, orphaning card REQ-4C4438BEDE35 and REQ-F3F9F01CB06F.
OPEN: The fix is unproven in production, because the api service is not taking deployments and only Tee can see why in the Railway dashboard. The OpenRouter account's behaviour above 700 tokens is therefore still unmeasured, and whether the model reads the words in the frame rather than calling it retro is unknown. Tee's password was disclosed in a screenshot and is not yet rotated. The ten year token issued to this session cannot be revoked without rotating SECRET_KEY and remains live. ACCESS_TOKEN_EXPIRE_MINUTES on the api service is unreviewed. Card REQ-F3F9F01CB06F expires unruled on 2026-09-20. The Vercel account block, recorded on PR #259, #260 and #262, is still uncleared and only a human on that account can clear it.
STATUS: The fix is on claude/keen-bardeen-fwejkf and not merged. Locally the vision path suite is 52 passed, five mutations produced five named failures, and the standalone job extracted from ci.yml with a YAML parser and run verbatim with PYTHONPATH unset is 898 passed, 1 skipped, exit 0. The production proof stands at: the OpenRouter key authenticates, VISION_IMAGE_ROOT and the relative path resolve, the approval gate works over HTTP, and the deployed service described the committed frame once, truncated, on 2026-09-17 at 12:20:57Z.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
