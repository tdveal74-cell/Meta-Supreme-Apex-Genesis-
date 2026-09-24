---
name: startup-reverse-engineering
description: Reverse-engineer a successful startup into a concrete independent business to build, ending in the steal, the wedge and an honest verdict. Never a company summary. Use when someone names a startup and asks how to copy it, compete with it, build a smaller version of it, or find the business hiding inside it; when they say "reverse engineer X", "what can I steal from X", "how would I build my own X", "is there a solo business in what X does", or "X is making money, how do I build a business off that". Also use when a founder brings a success story and wants to know whether any of it transfers to them. Never use it for buying shares in X or investing in X; that is a capital question and belongs to capital-guardrails.
---

# Reverse-engineering a startup

The request is never "tell me about Company X". The founder can read the About
page. What they want is the one mechanism that made X work, whether that
mechanism survives being moved into a business one person can run, the narrow
place to start, and a straight answer on whether to do it.

So the output of this skill is a build decision. A teardown that ends in a
summary has failed, however accurate it is.

## Rule zero: the teardown is only as good as its sources

Everything in `CLAUDE.md` under the first law applies. A reverse-engineering
job is unusually exposed to it, because the numbers people repeat about startups
are mostly estimates, press releases and founder podcasts, and a confident wrong
revenue figure bends every later step.

- **Every number carries a source and a date.** An illustrative shape: "ARR of $40M (founder
  interview on a named podcast, March 2025)" is a finding. "$40M ARR" is a guess wearing a
  number.
- **Sources rank, and the rank decides the label.** First party comes first:
  the company's own pricing page, a regulatory filing, a founder speaking on
  the record. Reputable press comes second. Aggregator blogs, SEO roundups and
  data vendor estimates come last, and a figure that only an aggregator carries
  is marked unverified even though it has a source and a date. If the first
  party page cannot be reached, say that in the line.
- **Private company revenue is unverified by default.** Say so in the line
  where it appears. An estimate from a data vendor is still an estimate, and it
  is labelled as one.
- **Search before asserting anything about the present.** Pricing, product
  lines, headcount and funding change. If a live search tool is loaded, use it
  and cite what it returned. If none is loaded, say the facts are from training
  data with a cutoff and mark every present-tense claim unverified.
- **Never fill a gap with a plausible figure.** "Unverified" beats a number that
  sounds right. Unit economics built on an invented input are invented.

## Step 1: pin the target and the founder

One company per run. If they name three, ask which one, or run the first and
say the others are separate runs.

Then establish the founder's constraints, because the same startup produces a
different steal for different people. Four things decide it:

- **Capital** they can put at risk, in dollars, and whether any of it is borrowed.
- **Hours** per week they can actually give it.
- **Unfair advantage**: access, credentials, a skill, a relationship, an
  existing audience.
- **Existing distribution**: a list, a channel, a customer base they already reach.
- **Floor hourly rate**: the least an hour of their time has to earn for the
  work to be worth doing. Step 5 prices against it.

Take what the conversation or the repository already answers, and ask only
for what is still missing, in one message. When the founder is Tee, his roster,
stack and constraints are read from DEVON (the Drive vault, or the
`devon-thread-log` skill when it is loaded) before anything is asked, and never
assumed.

## Step 2: tear it down to the mechanism

Answer five questions about the target. Each answer is one or two sentences,
carries its source, and is marked verified or unverified.

1. **Who pays, and for which job?** Name the buyer, who is sometimes a different
   person from the user.
   The job is the thing the buyer would otherwise hire a person or a spreadsheet
   to do.
2. **What is the price and how is it charged?** Per seat, per use, per outcome,
   one time, take rate. The billing shape often matters more than the product.
3. **How did the first customers arrive?** The channel that carried the first
   thousand customers. Today's paid acquisition is the wrong answer. A
   company at scale buys growth; a company at founding earned it somewhere specific, and that is the
   part a small operator can copy.
4. **What is the core loop?** The one repeated action that creates the value,
   and what makes a customer come back or stay.
5. **What was true at founding that made it possible?** The unlock: a new API,
   a platform shift, a regulation change, a cost that fell, an incumbent that got
   lazy. If that condition has closed, the path it opened may have closed with it.

Question 3 and question 5 are where most teardowns go wrong. They describe the
company as it is now and copy the features, when the copyable thing was the way
it got its first customers and the window it walked through.

## Step 3: split the portable from the non-portable

Write a table with one row per mechanism found in Step 2:

| mechanism | why it worked for them | portable to an independent business? | why |
|---|---|---|---|

Things that almost never port to one person: network effects that need scale,
anything capital intensive, regulatory licenses, a brand built over years, the
founder's own famous audience, venture-funded prices below cost.

Things that often port: a neglected customer segment, a pricing shape, an
acquisition channel that still has room, a manual service the company later
automated, a single feature the company bundles and an underserved buyer wants
alone.

If nothing in the table ports, say so now and skip to the verdict. That is a
legitimate result and often the right one, and the output then carries only
the verdict, the reason nothing ports and the teardown.

## Step 4: the steal

The steal is ONE mechanism from the portable column, stated in one sentence.
Pick the one that best fits the founder's constraints from Step 1. Name which
kind it is, because the kind decides what gets built:

- **Steal the customer**: serve a segment the startup ignores or prices out.
- **Steal the channel**: use the acquisition route that worked for them, in a
  market it has not reached yet.
- **Steal the mechanism**: move the core loop into a vertical they do not serve.
- **Steal the unbundle**: sell one feature of theirs as the whole product.
- **Steal the service version**: do by hand, for fewer customers at a higher
  price, what they do with software. Many software companies started exactly
  here, which is why it is usually the cheapest test.

The steal names which Step 2 answer it inherits, by number. A steal that
inherits none of the five has dropped what made the target work: "do
scheduling by hand for a niche" can be carved out of any scheduling tool, and
it is generic freelancing wearing the startup's name. When the only steal left
inherits nothing, the verdict is DON'T BUILD unless the founder's own advantage
carries the case on its own, and the verdict says so.

Two steals in one answer means neither has been chosen. Pick one.

## Step 5: the wedge

The wedge is the narrow first place to start, where the startup is weak and the
founder is strong. It is specific enough to act on this week. It must name:

- **The first ten customers**: who they are by type, and where the founder
  finds them. "Small businesses" fails. "Independent physical therapy clinics
  with two to five practitioners, found through the state association's member
  directory" passes.
- **Why the startup will not come after them**: an economic reason, such as the
  contract is too small for their sales team or the segment needs a compliance
  step they will not build. "They are busy" is not a reason.
- **Who already serves them, and why they would switch.** Search for the
  niche tools, agencies and freelancers already selling to this segment, and
  name each with its source. A gap the startup ignores is often a gap somebody
  else already fills. If nobody serves them, ask whether that is because they
  will not pay.
- **The price**, and the arithmetic showing it clears the founder's floor
  hourly rate from Step 1.
- **What the customer receives in week one.**
- **Any rule that governs the work**: licensing, fee limits, privacy or
  accreditation rules in the segment. Name them, or mark the check as not yet
  done. An unchecked rule is a condition on the verdict.

Run the "why they won't bother" test out loud. If the honest answer is that the
startup would take this segment the moment it noticed, the wedge is a gap in
their roadmap and it closes when they get to it.

## Step 6: the business on one page

- **Offer**: what is sold, to whom, in one sentence.
- **Price and billing shape.**
- **First channel**: the one route to the first ten customers.
- **Unit economics with the arithmetic shown**: price, cost to deliver, cost to
  acquire, hours per customer. Every input either comes from the founder, is
  sourced, or is marked as an assumption to test.
- **The 30-day test**: one experiment, what it costs, and the number that
  counts as a pass. Its cost sits at or below the capital at risk from Step 1. "Get feedback" is not a test. "Ten paid pilots at $300 from
  forty direct asks, or stop" is.

## Step 7: the verdict

One of three, stated first:

- **BUILD**: the steal ports, the wedge holds, the arithmetic works on the
  founder's constraints.
- **BUILD WITH CONDITIONS**: it works only if named assumptions hold. List
  each one and the cheapest way to test it before spending more.
- **DON'T BUILD**: say why in one sentence. The most common reason is that the
  startup's success came from something in the non-portable column.

Then give the single assumption that kills it if wrong, and the kill criteria:
the result by a named date that means stop. If any of the capital is
borrowed, the verdict line says so and states the downside in dollars. State
the verdict without inflation. A
don't-build delivered now saves the founder months, and it is a complete answer.

The verdict is a recommendation. The founder decides. Hand it back to them.

## Output shape

Deliver in this order, and keep the teardown short relative to the build:

1. The verdict line, first.
2. The steal, one sentence, with its kind.
3. The wedge, with every item from Step 5.
4. The one-page business from Step 6.
5. The kill assumption and kill criteria.
6. The teardown from Steps 2 and 3, last, as the evidence, with sources and
   verified or unverified on each line.

Prose for the argument. Lists and tables only for the one-page business, the
portability table and checklists.

## Failure modes this skill exists to prevent

- **The company summary.** History, funding rounds and product tour, ending in
  "there are opportunities in this space". No steal, no wedge, no verdict.
- **Feature copying.** Rebuilding what the company sells today. The copyable
  thing is what it did at founding.
- **Top-down market sizing.** "The market is $50B, so 1% is $500M" says nothing
  about whether ten people will pay. Size from the first ten customers up.
- **The "X for Y" pitch.** Naming a mash-up is not a mechanism.
- **Invented figures.** See rule zero.
- **Capital instructions.** This skill never tells anyone to spend, borrow or
  allocate money. Where money is at risk, it states the downside and hands the
  decision back. If a `capital-guardrails` skill is loaded, its rules apply.

## Neighbours

Other skills may be loaded in the session; use them when they are, and do not
assume they are. `venture-thesis` generates and screens ideas from the
founder's constraints, where this skill starts from one named company.
`go-to-market-plan` takes a BUILD verdict into a launch plan. `critique-panel`
stress-tests a verdict before money moves.

If the run produced a decision worth keeping, offer to file it to DEVON.
