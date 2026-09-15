# TimesFM, evaluated against the estate and declined for now

Date: 2026-09-15. Supersedes nothing. First status doc on TimesFM.

Tee asked whether the TimesFM repository is worth it. The answer is no, not
yet, and the reason is not the model. The model is good. The estate has no
series to point it at, and the version that wins the benchmarks carries a
licence that forbids exactly the use Tee would have for it.

## What was read

`https://github.com/google-research/timesfm` cloned at HEAD `8cb0628`, dated
2026-09-09, version 3.0.2. The repository is alive: 145 commits in the twelve
months to today, led by Rajat Sen with 52 and Yichen Zhou with 25, both listed
as Google authors in `pyproject.toml`, with real outside contribution behind
them. This is not an abandoned research drop.

The code is Apache-2.0. The weights are where it turns.

## The licence finding, which decides it

`google/timesfm-3.0-pytorch` on Hugging Face carries `license: other`, 330.7M
parameters, a 1.32 GB safetensors file. Its `LICENSE` is the TimesFM
Non-Commercial License v1.0, read in full today. Its definition of
Non-Commercial Purpose:

> use for testing, evaluation, or research not tied to commercial gain,
> production deployment, or revenue generation. This includes internal
> benchmarking, academic research, and experimentation on private or public
> datasets, provided the results are not used in commercial decision-making,
> client deliverables, or paid products/services.

The restriction clause reaches further than the weights. It forbids use of
"the TimesFM Model (or any Derivative thereof, or any Outputs and data produced
by the TimesFM Model), in whole or in part for any commercial or production
purposes."

A studio with a stated revenue target cannot use a 3.0 forecast to decide
anything. Not a publishing schedule, not a spend, not a slate. The output is
covered, not just the file. So the top of the leaderboard is closed to this
estate unless Google grants a commercial licence, which the text says is at
their sole discretion and may carry a fee.

`google/timesfm-2.5-200m-pytorch` is Apache-2.0, 231.3M parameters, about
800 MB. That one is clean and usable commercially. It is univariate only in
native form, with covariates bolted on through XReg, which pulls in jax and
scikit-learn. It is also the version the repository's own agent skill is
written against, checked by grepping the skill for checkpoint names: it cites
2.5, 2.0 and 1.0, never 3.0.

The commercially clean alternative in the same class is
`amazon/chronos-bolt-base`, Apache-2.0, 205M parameters, 50.6M downloads.
`Salesforce/moirai-2.0-R-small` is CC-BY-NC, so it is closed for the same
reason 3.0 is.

## What could not be checked here

The container's network policy denies `huggingface.co`. The proxy logged
`connect_rejected`, "gateway answered 403 to CONNECT", for `huggingface.co:443`
at 2026-09-15T07:03:14Z. PyPI is reachable, so the package installs, but the
weights download from Hugging Face and that path is shut. No forecast was run
in this session and no accuracy number below is mine.

That means every performance claim here is the vendor's. The README states
rank 1 on fev-bench across 100 tasks, rank 1 on the TIME benchmark, and rank 1
among foundation models on GIFT-Eval, all for 3.0. Unverified. Tee can run it
on any machine with 4 GB of RAM and an unblocked network. It will not run on
the iPhone.

## Why the fit is wrong today, independent of the licence

TimesFM forecasts the continuation of a numeric series from its own history.
That is the whole shape of the tool. Held against what the estate actually
does:

Revenue against the $10K target is a monthly series. A full year of it is
twelve numbers. A 200M parameter foundation model reading twelve points is
theatre, and a trend line drawn by hand answers the same question with the
same honesty.

Whether a given video will perform is not a forecasting problem. Each video is
a new item, not the next point in a series, and TimesFM has nothing to say
about items it has no history for. This is the use most likely to be reached
for and it is the worst fit of the three.

Daily channel views and subscriber counts are the one real fit. That needs
roughly a year of daily points to be worth a foundation model rather than a
seasonal naive baseline, and it needs a decision that changes based on the
answer. A forecast that changes nothing Tee does is decoration.

Operational telemetry is the honest second candidate. `provider_usage`,
`workflow_runs` and `agent_runs` aggregate into daily counts, and the quantile
band gives anomaly detection without a separate model, which is the pattern the
repository's own example uses: treat anything outside q10 to q90 as unusual. At
this estate's volume a threshold alert does the same job for no new dependency.

The estate carries no forecasting code at all today. A case insensitive grep
for forecast, timesfm, time series, arima and prophet across the Python and web
source returns three files, and all three are coincidental: two are a weather
phrase list in `services/devon/commands.py` and its deploy copy, one is a
fixture string in `test_decisions_api.py`. There is nothing here to extend.

## What would flip it

One daily series with about 300 points and a decision hanging on the forecast.
Channel analytics is the likely first. When that exists, the path is TimesFM
2.5 or Chronos Bolt, both Apache-2.0, both about 800 MB, both CPU runnable at
roughly 1.5 GB of RAM, and the first run should be a backtest against seasonal
naive rather than a forecast. If the foundation model does not beat the naive
baseline on held out weeks, the answer stays no and the baseline ships.

The repository's agent skill, `timesfm-forecasting`, is 2,313 lines across the
skill, three reference documents and two scripts, Apache-2.0, contributed by
Clayton Young. It carries a preflight system checker that refuses below 2 GB of
RAM. It is well built and it is worth copying on the day there is data, not
before. Vendoring it now would add a fourth skill directory, a manifest and an
upstream note under this repository's vendored skill rules, all guarding code
with nothing to run against.

## Rating, uninflated

The repository as engineering is strong. Maintained by the authors, tested,
documented, with a working agent skill and two inference backends. Fit to this
estate on 2026-09-15 is poor, and the licence on the good weights is a hard
stop rather than a friction.

Recommendation: decline, revisit when a daily series exists. No code, no
dependency, no skill added.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-timesfm-evaluation_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: none ruled by Tee. The recommendation put to him is to decline TimesFM for now and add nothing: no dependency, no vendored skill, no forecasting lane. The decision taken inside this arc was mine and it was a refusal to recommend TimesFM 3.0 at any point, because its weights licence forbids the outputs being used in commercial decision making and this estate has a revenue target, which makes the benchmark leading version unusable here regardless of how good it is. If Tee overrules and wants a forecasting lane now, the clean path is TimesFM 2.5 or Chronos Bolt, both Apache-2.0, and the first run should be a backtest against seasonal naive rather than a forecast anyone acts on.
FINDINGS: google-research/timesfm cloned at HEAD 8cb0628 dated 2026-09-09, version 3.0.2, alive with 145 commits in the twelve months to 2026-09-15 led by Google authors Rajat Sen at 52 and Yichen Zhou at 25; the repository code is Apache-2.0 but the weights split, google/timesfm-3.0-pytorch carrying license other at 330.7M parameters and 1.32 GB under the TimesFM Non-Commercial License v1.0 read in full today, whose Non-Commercial Purpose definition excludes revenue generation, production deployment, commercial decision making, client deliverables and paid products, and whose restriction clause covers any Outputs and data produced by the model rather than only the weights, so a 3.0 forecast cannot inform a decision in a revenue seeking studio; google/timesfm-2.5-200m-pytorch is Apache-2.0 at 231.3M parameters and about 800 MB and is commercially clean, univariate natively with covariates through XReg needing jax and scikit-learn, and is the version the repository's own agent skill targets, the skill citing checkpoints 2.5, 2.0 and 1.0 and never 3.0; amazon/chronos-bolt-base is the Apache-2.0 alternative in the same class at 205M parameters and 50.6M downloads while Salesforce/moirai-2.0-R-small is CC-BY-NC and closed for the same reason 3.0 is; the estate carries no forecasting code, a case insensitive grep for forecast, timesfm, time series, arima and prophet across Python and web source returning only a weather phrase list in services/devon/commands.py with its deploy copy and a fixture string in test_decisions_api.py; the estate's tables are operational rather than metric, with no revenue or daily views series anywhere, so the only real candidates are aggregated counts from provider_usage, workflow_runs and agent_runs, where a threshold alert does the same job as a quantile band at this volume; and the fit failure is structural rather than about quality, because a monthly revenue series is twelve points, per video performance is not a series continuation problem at all, and the one genuine fit, daily channel analytics, needs about a year of points that do not yet exist.
OPEN: no forecasting lane exists and none is proposed; whether Tee wants a daily channel analytics series captured now so the option opens in a year is his call and not taken here; the vendor benchmark claims for 3.0, rank 1 on fev-bench across 100 tasks, rank 1 on the TIME benchmark and rank 1 among foundation models on GIFT-Eval, are unverified and stay unverified until someone runs them; the shipped agent skill timesfm-forecasting at 2,313 lines Apache-2.0 is not vendored and should not be until there is data to point it at, at which point it needs a manifest and an upstream note under this repository's vendored skill rules.
STATUS: filed, nothing shipped and nothing changed. This document is the only artifact in the arc. No dependency was added to requirements.txt or pyproject.toml, no skill was vendored under .claude/skills, and no estate code was touched. The clone was made under the session scratchpad and not into the repository. No forecast was run and no accuracy number here is measured: the container's network policy denies huggingface.co, the proxy logging connect_rejected with gateway answered 403 to CONNECT for huggingface.co:443 at 2026-09-15T07:03:14Z, so the weights cannot be fetched in this environment even though PyPI is reachable. Tee or any machine with 4 GB of RAM and an unblocked network can run it; the iPhone cannot.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
