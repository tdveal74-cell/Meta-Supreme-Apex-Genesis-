/**
 * Proof for the projects panel: its parser, its verdict ladder, and the two
 * properties of the component that decide whether either one is reachable. No
 * test framework, node:assert and a plain process exit code, the same shape as
 * scripts/learning-check.ts and scripts/control-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/projects-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * `pnpm typecheck` and `pnpm build` both exit 0 over a reversed safeguard: that
 * was measured on this estate on 2026-09-09 when a critic inverted a control
 * plane guard and neither command noticed. So neither of those is a guard on the
 * one claim this panel exists to make, which is whether the caller owns any
 * projects. `parseProjectsPayload` and `readProjectsVerdict` are pure, with no
 * DOM and no network, so there is no reason for them to be unguarded.
 *
 * The load bearing law, and the reason it is first in this file: a read that
 * FAILED must never render as a list that is EMPTY. On this door those are
 * opposite instructions. Empty says create a project. Failed says fix the route,
 * because writing into it would be writing where nobody can see the result.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseProjectsPayload,
  readProjectsVerdict,
  type ProjectsRead,
  type ProjectsVerdict,
} from "../components/projects/projects-honesty.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

const PANEL = readFileSync(
  join(HERE, "..", "components/projects/ProjectsPanel.tsx"),
  "utf8",
);
const LADDER = readFileSync(
  join(HERE, "..", "components/projects/projects-honesty.ts"),
  "utf8",
);
const PAGE = readFileSync(join(HERE, "..", "app/control/projects/page.tsx"), "utf8");

const LOCKED: ProjectsRead = { state: "locked" };
const FAILED: ProjectsRead = { state: "failed", detail: "the projects route answered 500" };
const OK_EMPTY: ProjectsRead = { state: "ok", count: 0, malformed: 0, duplicates: 0 };
const OK_FULL: ProjectsRead = { state: "ok", count: 3, malformed: 0, duplicates: 0 };

/* ------------------------------------------------------------------ */
/* The load bearing law                                                */
/* ------------------------------------------------------------------ */

function refuseEmptyAndGood(verdict: ProjectsVerdict, why: string): void {
  assert.equal(verdict.code, "unreadable", why);
  assert.notEqual(verdict.code, "empty", "a failed read must never read as an empty list");
  assert.notEqual(verdict.tone, "good", "a failed read must never take a good tone");
  assert.match(verdict.sentence, /failed read, not an empty list/);
}

check("a failed read is never reported as an empty list", () => {
  refuseEmptyAndGood(
    readProjectsVerdict(FAILED),
    "the list was not read, so no claim about emptiness is available",
  );
});

check("the failing detail reaches the operator", () => {
  const verdict = readProjectsVerdict(FAILED);
  assert.match(verdict.sentence, /answered 500/, "the operator needs the actual failure");
});

check("a non-array body is a failed read rather than an empty list", () => {
  // GET /projects is declared response_model=List[ProjectResponse]. Every one
  // of these is a real degraded body, and every one of them would render as
  // "you own no projects" if the parser answered with an empty array.
  for (const body of [null, undefined, {}, { detail: "Not authenticated" }, "", 0, false]) {
    assert.equal(
      parseProjectsPayload(body),
      null,
      `parseProjectsPayload(${JSON.stringify(body) ?? "undefined"}) must refuse, not return an empty list`,
    );
  }
});

check("the panel reports a null parse as a failed read", () => {
  // The parser refusing is only worth something if the component acts on it.
  // A `?? []` or a `|| []` on that line is the whole inversion in two chars.
  //
  // THE FIRST VERSION OF THIS CHECK WAS GREEN OVER THE INVERSION. It read
  // /if\s*\(parsed === null\)\s*\{[\s\S]{0,320}?state:\s*"failed"/, which does
  // not require the failed state to be INSIDE the branch: the 320 character
  // window reached the `state: "failed"` in the catch block about 239
  // characters below. An adversary on 2026-09-10 kept the branch, replaced its
  // body with an ok read of zero rows, and this file still printed 23 ok lines
  // and exited 0 while a 200 carrying {"detail":"Not authenticated"} rendered
  // "NO PROJECTS / You own no projects... Create one below."
  //
  // So the branch body is captured and asserted on by itself, and the ok state
  // is banned from it outright rather than the failed state merely being
  // present somewhere nearby.
  const branch = /if\s*\(parsed === null\)\s*\{([\s\S]*?)\n      \}/.exec(PANEL);
  assert.ok(
    branch,
    "ProjectsPanel no longer has a `parsed === null` branch, so an unreadable body falls straight into the render",
  );
  assert.match(
    branch[1],
    /setLoad\(\{ state: "failed"/,
    `the null parse branch is {${branch[1]}}, which does not set a failed read. That renders a broken route as an account with no projects`,
  );
  assert.ok(
    !/state: "ok"/.test(branch[1]),
    `the null parse branch carries an ok state: {${branch[1]}}`,
  );
  assert.match(branch[1], /return;/, "the null parse branch does not return, so it falls through into the ok path below it");
  assert.ok(
    !/parseProjectsPayload\([\s\S]{0,80}?\)\s*\?\?\s*\[/.test(PANEL) &&
      !/parseProjectsPayload\([\s\S]{0,80}?\)\s*\|\|\s*\[/.test(PANEL),
    "ProjectsPanel defaults a refused parse to an empty array, which renders a failed read as an empty list",
  );
});

check("the panel's read adapter never carries a count off a failed read", () => {
  // A count is a claim about the list. A read that failed supports no such
  // claim, in either direction.
  const adapter = /function asRead\(load: Load\): ProjectsRead \{[\s\S]*?\n\}/.exec(PANEL);
  assert.ok(adapter, "asRead is gone from ProjectsPanel; the ladder is being fed something else");
  const failedBranch = /load\.state === "failed"\) return \{ state: "failed", detail: load\.detail \};/;
  assert.match(
    adapter[0],
    failedBranch,
    "asRead's failed branch no longer forwards only the detail, so it may be carrying a count",
  );
  assert.match(
    adapter[0],
    /count:\s*load\.parsed\.rows\.length/,
    "asRead's ok branch does not report the actual row count, so the number on the panel is not the number the route returned",
  );
  assert.match(
    PANEL,
    /readProjectsVerdict\(asRead\(/,
    "ProjectsPanel no longer feeds asRead into readProjectsVerdict, so the ladder this file guards is not the one it renders",
  );
});

/* ------------------------------------------------------------------ */
/* Locked outranks unreadable                                          */
/* ------------------------------------------------------------------ */

check("no session token is locked, not a failed read", () => {
  // No request was sent, so calling this a failure would invent one.
  const verdict = readProjectsVerdict(LOCKED);
  assert.equal(verdict.code, "locked");
  assert.notEqual(verdict.code, "unreadable");
  assert.notEqual(verdict.code, "empty");
  assert.match(verdict.sentence, /no request was sent/);
});

/* ------------------------------------------------------------------ */
/* Rows that arrived but cannot be used are their own rung             */
/* ------------------------------------------------------------------ */

check("a 200 whose every row is unusable is not an empty list", () => {
  const verdict = readProjectsVerdict({ state: "ok", count: 0, malformed: 4, duplicates: 0 });
  assert.equal(verdict.code, "unusable");
  assert.notEqual(verdict.code, "empty", "rows arrived, so the list is not empty");
  assert.notEqual(verdict.tone, "good");
  assert.match(verdict.sentence, /4 rows/, "the operator needs to know how many were refused");
});

check("a partly usable list says how much it is not showing", () => {
  const verdict = readProjectsVerdict({ state: "ok", count: 2, malformed: 1, duplicates: 0 });
  assert.equal(verdict.code, "populated");
  assert.match(verdict.sentence, /1 further row was refused/);
  assert.match(verdict.sentence, /shorter than what the route sent/);
});

/* ------------------------------------------------------------------ */
/* The honest ends of the ladder                                       */
/* ------------------------------------------------------------------ */

check("a successful read with no rows is an empty list, and says so", () => {
  const verdict = readProjectsVerdict(OK_EMPTY);
  assert.equal(verdict.code, "empty");
  assert.notEqual(verdict.tone, "good", "no projects is a finding, not a pass");
  assert.match(verdict.sentence, /returned no rows/);
  assert.match(verdict.sentence, /can only be null/);
});

check("rows that came back are counted, not estimated", () => {
  const verdict = readProjectsVerdict(OK_FULL);
  assert.equal(verdict.code, "populated");
  assert.equal(verdict.tone, "good");
  assert.match(verdict.sentence, /3 projects/);
  assert.ok(!/further row/.test(verdict.sentence), "nothing was refused, so nothing is claimed to be");
});

check("one project reads as one project", () => {
  assert.match(readProjectsVerdict({ state: "ok", count: 1, malformed: 0, duplicates: 0 }).sentence, /1 project\b/);
});

/* ------------------------------------------------------------------ */
/* The parser invents nothing                                          */
/* ------------------------------------------------------------------ */

check("a field the route did not send stays null", () => {
  const parsed = parseProjectsPayload([{ id: "p1" }]);
  assert.ok(parsed);
  assert.equal(parsed.rows.length, 1);
  const row = parsed.rows[0];
  assert.equal(row.name, null, "a name defaulted to the id is a name this panel made up");
  assert.equal(row.description, null);
  assert.equal(row.status, null, 'a status defaulted to "active" is a claim the route did not make');
  assert.equal(row.organizationId, null);
  assert.equal(row.createdAt, null);
  assert.equal(row.updatedAt, null);
  assert.equal(parsed.rowsWithoutName, 1);
  assert.equal(parsed.malformedRows, 0);
});

check("a full row is read exactly as sent", () => {
  const parsed = parseProjectsPayload([
    {
      id: "p1",
      name: "Node 01",
      description: "The opening arc",
      status: "archived",
      organization_id: "org1",
      owner_id: "u1",
      created_at: "2026-09-10T00:00:00+00:00",
      updated_at: "2026-09-10T01:00:00+00:00",
    },
  ]);
  assert.ok(parsed);
  assert.deepEqual(parsed.rows[0], {
    id: "p1",
    name: "Node 01",
    description: "The opening arc",
    status: "archived",
    organizationId: "org1",
    createdAt: "2026-09-10T00:00:00+00:00",
    updatedAt: "2026-09-10T01:00:00+00:00",
  });
  assert.equal(parsed.malformedRows, 0);
  assert.equal(parsed.rowsWithoutName, 0);
});

check("a row with no usable id is refused and counted", () => {
  // Every one of these would break rename: the PATCH path is built from the id.
  const parsed = parseProjectsPayload([
    { id: "p1", name: "kept" },
    { name: "no id" },
    { id: "", name: "blank id" },
    { id: "   ", name: "whitespace id" },
    { id: 7, name: "numeric id" },
    null,
    "not a row",
    ["also not a row"],
  ]);
  assert.ok(parsed);
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.malformedRows, 7);
});

check("a duplicate id is refused rather than drawn twice, and named as a duplicate", () => {
  const parsed = parseProjectsPayload([
    { id: "p1", name: "first" },
    { id: "p1", name: "second" },
  ]);
  assert.ok(parsed);
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.rows[0].name, "first", "the first row wins, and only one row is drawn");
  // Counted APART from malformedRows since 2026-09-10. It used to land there,
  // and the sentence for that bucket says "refused for carrying no usable id",
  // which is false of a duplicate: its id is perfectly usable. An operator sent
  // looking for a null id in the payload would not have found one. The check
  // that existed asserted the count and never read the sentence, which is why
  // nothing caught it.
  assert.equal(parsed.duplicateRows, 1, "a duplicate id is not counted as a duplicate");
  assert.equal(parsed.malformedRows, 0, "a duplicate id is being counted as a malformed row again");
});

check("the sentence names the real reason each refused row was refused", () => {
  const dup = readProjectsVerdict({ state: "ok", count: 1, malformed: 0, duplicates: 1 });
  assert.equal(dup.code, "populated");
  assert.ok(
    /repeated an id already sent/.test(dup.sentence),
    `a duplicate was not named as one: "${dup.sentence}"`,
  );
  assert.ok(
    !/no usable id/.test(dup.sentence),
    `a duplicate is described as carrying no usable id: "${dup.sentence}"`,
  );

  const bad = readProjectsVerdict({ state: "ok", count: 1, malformed: 2, duplicates: 0 });
  assert.ok(/no usable id/.test(bad.sentence), `an unreadable row was not named as one: "${bad.sentence}"`);
  assert.ok(
    !/repeated an id/.test(bad.sentence),
    `an unreadable row is described as a duplicate: "${bad.sentence}"`,
  );

  const both = readProjectsVerdict({ state: "ok", count: 1, malformed: 1, duplicates: 2 });
  assert.ok(/no usable id/.test(both.sentence) && /repeated an id/.test(both.sentence), both.sentence);
  assert.ok(/3 further rows were refused/.test(both.sentence), `the total refused is wrong: "${both.sentence}"`);

  // and a clean read claims no refusals at all
  const clean = readProjectsVerdict({ state: "ok", count: 2, malformed: 0, duplicates: 0 });
  assert.ok(!/refused/.test(clean.sentence), `a clean read mentions a refusal: "${clean.sentence}"`);

  // the unusable rung: rows arrived, none survived, and the reason is named
  const unusable = readProjectsVerdict({ state: "ok", count: 0, malformed: 3, duplicates: 0 });
  assert.equal(unusable.code, "unusable");
  assert.ok(/no usable id/.test(unusable.sentence), unusable.sentence);
});

check("an empty array is an empty list, not a refusal", () => {
  const parsed = parseProjectsPayload([]);
  assert.ok(parsed, "an empty array is a real, successful answer");
  assert.equal(parsed.rows.length, 0);
  assert.equal(parsed.malformedRows, 0);
  assert.equal(parsed.duplicateRows, 0);
});

check("creating is refused while the list could not be read", () => {
  // projects-honesty.ts states that a failed read means the route is down and
  // that creating against it would be writing into something whose state nobody
  // can see. The panel drew the amber UNREADABLE block and left the Create
  // button live, so the module's doctrine and the panel disagreed and the panel
  // won. Found by an adversary on 2026-09-10.
  const at = PANEL.indexOf("Create project");
  assert.ok(at > 0, "the create button could not be found on the panel");
  const before = PANEL.slice(0, at);
  const last = before.lastIndexOf("disabled={");
  assert.ok(last > 0, "the create button no longer has a disabled expression");
  const expression = /disabled=\{([\s\S]*?)\n\s*\}/.exec(before.slice(last));
  assert.ok(expression, "the create button's disabled expression could not be read");
  for (const required of [/load\.state === "locked"/, /load\.state === "failed"/, /!name\.trim\(\)/]) {
    assert.match(
      expression[1],
      required,
      `the create button is enabled where ${required} should refuse it: {${expression[1]}}`,
    );
  }
});

/* ------------------------------------------------------------------ */
/* What the panel does not do                                          */
/* ------------------------------------------------------------------ */

check("nothing is written without a person pressing the button that writes it", () => {
  // Every write must sit inside a handler, never inside the effect that runs on
  // mount. An auto-created project would be an effect nobody ruled on.
  const effect = /useEffect\(\(\) => \{[\s\S]*?\}, \[read\]\);/.exec(PANEL);
  assert.ok(effect, "the mount effect is gone from ProjectsPanel");
  assert.ok(
    !/method:\s*"(?:POST|PATCH|PUT|DELETE)"/.test(effect[0]),
    "ProjectsPanel's mount effect now sends a mutating request, so the surface writes without a person ruling on it",
  );
  assert.ok(
    !/\bcreate\(|\bsaveRename\(/.test(effect[0]),
    "ProjectsPanel's mount effect now calls a writer",
  );
});

check("the patch request carries only the name", () => {
  // ProjectUpdate accepts status with the pattern ^(active|archived)$. Sending
  // it from the rename row would archive a scope as a side effect of renaming
  // it, and archiving changes what the graph route filters on.
  // Read the body expression itself rather than a window around it: a window
  // wide enough to hold the whole call also holds the response.status handling
  // below it, and would fail on the word rather than on the request.
  const patch = /method: "PATCH",[\s\S]{0,600}?\n\s*body: (.+),\n/.exec(PANEL);
  assert.ok(patch, "the PATCH request, or its body, is gone from ProjectsPanel");
  assert.equal(
    patch[1],
    "JSON.stringify({ name: trimmed })",
    `the rename request body is no longer name-only (it is now ${patch[1]}), so a rename may change more than the name`,
  );
  assert.ok(
    !/status/.test(patch[1]),
    "the rename request body now carries status; archiving is a separate ruling and is not offered here",
  );
});

check("an untouched description box is sent as absent, not as an empty string", () => {
  assert.match(
    PANEL,
    /if \(note\) body\.description = note;/,
    'ProjectsPanel no longer omits a blank description, so a person who typed nothing has "" written for them',
  );
});

/* ------------------------------------------------------------------ */
/* Reachability: the whole point of the door                           */
/* ------------------------------------------------------------------ */

check("the projects panel is mounted where a person can reach it", () => {
  // A component nobody renders is the unreachable route this arc closed, moved
  // one directory over.
  assert.match(
    PAGE,
    /import \{ ProjectsPanel \} from "@\/components\/projects\/ProjectsPanel";/,
    "/control/projects no longer imports ProjectsPanel",
  );
  assert.match(
    PAGE,
    /<ProjectsPanel \/>/,
    "/control/projects imports ProjectsPanel and never renders it, so the routes have a caller that never runs",
  );
  const gates = PAGE.match(/\{[^{}]*&&[^{}]*<ProjectsPanel/g) ?? [];
  assert.equal(
    gates.length,
    0,
    "<ProjectsPanel /> is mounted behind a condition, so whether a person can see it depends on a test this check cannot evaluate",
  );
});

check("the panel actually calls all three project routes", () => {
  assert.match(PANEL, /fetch\(`\$\{API_BASE\}\/projects`, \{\s*cache: "no-store",/, "the list read is gone");
  assert.match(PANEL, /method: "POST"/, "the create request is gone");
  assert.match(PANEL, /\/projects\/\$\{encodeURIComponent\(row\.id\)\}/, "the patch request no longer encodes the id into the path");
});

/* ------------------------------------------------------------------ */
/* The legibility floor, on this door's own files                      */
/*                                                                    */
/* control-check.ts holds this line for the files listed in its own    */
/* CONTROL_TREE, and these three are not in it until the parent adds   */
/* them. The thresholds are that file's, computed against #04070d:     */
/* white at 45% is 4.48:1 and fails AA, white at 50% is 5.35:1.        */
/* ------------------------------------------------------------------ */

const BELOW_AA: Array<{ pattern: RegExp; why: string }> = [
  { pattern: /text-\[(?:[0-9]|10)px\]/g, why: "under 11px is unreadable on a phone" },
  {
    pattern: /text-white\/(?:[0-9]|[1-3][0-9]|4[0-5])\b/g,
    why: "white at 45% or less is below 4.5:1 on the ACX void",
  },
  { pattern: /text-\[#526979\]/g, why: "#526979 is 3.49:1 on the ACX void" },
];

check("no text in this door renders below the AA floor", () => {
  const offences: string[] = [];
  for (const [relative, source] of [
    ["components/projects/ProjectsPanel.tsx", PANEL],
    ["components/projects/projects-honesty.ts", LADDER],
    ["app/control/projects/page.tsx", PAGE],
  ] as const) {
    source.split("\n").forEach((line, index) => {
      for (const { pattern, why } of BELOW_AA) {
        for (const hit of line.matchAll(pattern)) {
          offences.push(`${relative}:${index + 1} ${hit[0]} (${why})`);
        }
      }
    });
  }
  assert.deepEqual(offences, [], `\n${offences.join("\n")}`);
});

check("every text input in this door carries a label", () => {
  // A placeholder is not a label: it disappears the moment anything is typed,
  // and a screen reader is not required to announce it. Same rule and same
  // reading as control-check.ts.
  const ids = new Set([...PANEL.matchAll(/htmlFor="([^"]+)"/g)].map((m) => m[1]));
  let inputs = 0;
  for (const tag of PANEL.matchAll(/<input\b[\s\S]*?\/>/g)) {
    inputs += 1;
    const element = tag[0];
    const id = /\bid="([^"]+)"/.exec(element)?.[1];
    const labelled = (id !== undefined && ids.has(id)) || /\baria-label(?:ledby)?=/.test(element);
    assert.ok(labelled, `ProjectsPanel has an input with no label: ${element.slice(0, 90)}`);
  }
  assert.equal(inputs, 3, "the input count moved; re-check that each one is labelled");
});

console.log(`\n${checks} projects honesty checks passed`);
