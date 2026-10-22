import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

// Execute the shipped component handlers, not a parallel implementation of
// their recovery logic. This small hook host omits DOM/layout and is not a
// browser smoke test. Every request is intercepted by the in-memory fixture.
type Element = { type: unknown; props: { children?: unknown; [key: string]: any } };
const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
function harness(commitFirstRuling: boolean) {
  const hooks: any[] = [];
  let cursor = 0;
  const effects: (() => void)[] = [];
  let token = "isolated-test-session";
  let approved = false;
  let lostResponse = true;
  let firstRun = true;
  const requests: { path: string; method: string; body: any }[] = [];
  const task = {
    task_id: "owned-task", goal: "Review one task", state: "planned", current_step: 0,
    plan: { steps: [{ title: "Write one file", approval_request_id: "owned-ruling", tool_call: { name: "github.write_file", arguments: { path: "fixture" } } }] },
    context: { max_steps: 1 },
  };
  const other = { ...task, task_id: "other-task", goal: "Another task" };
  const react = {
    useState(initial: any) {
      const k = cursor++;
      if (!(k in hooks)) hooks[k] = initial;
      return [hooks[k], (value: any) => { hooks[k] = typeof value === "function" ? value(hooks[k]) : value; }];
    },
    useRef(initial: any) { const k = cursor++; if (!(k in hooks)) hooks[k] = { current: initial }; return hooks[k]; },
    useCallback(fn: any) { cursor++; return fn; },
    useEffect(fn: () => void) { const k = cursor++; if (!(k in hooks)) { hooks[k] = true; effects.push(fn); } },
  };
  const jsx = { jsx: (type: unknown, props: Element["props"]) => ({ type, props }), jsxs: (type: unknown, props: Element["props"]) => ({ type, props }) };
  const fetcher = async (url: string, init: RequestInit) => {
    const path = new URL(url).pathname;
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    requests.push({ path, method: String(init.method), body });
    if (path.endsWith("/run")) {
      assert.equal(path, "/api/v1/agent-tasks/owned-task/run");
      const result = { task: { ...task, state: approved ? "completed" : "waiting_approval" }, ...(firstRun ? { approval_token: "one-time-fixture-token" } : {}) };
      firstRun = false;
      return new Response(JSON.stringify(result));
    }
    if (path.endsWith("/approvals/decide")) {
      assert.equal(body.request_id, "owned-ruling");
      assert.equal(body.token, "one-time-fixture-token");
      if (lostResponse) {
        lostResponse = false; approved = commitFirstRuling;
        throw new Error("Ruling response lost");
      }
      approved = true;
      return new Response(JSON.stringify({ ok: true, approved: true, state: "approved" }));
    }
    assert.equal(init.method, "GET");
    return new Response(JSON.stringify([{ ...task, state: firstRun ? "planned" : "waiting_approval" }, other]));
  };
  function load(path: string): any {
    const exports = {};
    const code = ts.transpileModule(readFileSync(resolve(WEB, path), "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    runInNewContext(code, {
      exports,
      require(name: string) {
        if (name === "react") return react;
        if (name === "react/jsx-runtime") return jsx;
        if (name === "next/link") return { default: "Link" };
        if (name === "@/lib/api-base") return { API_BASE: "https://fixture.invalid/api/v1" };
        if (name === "@/lib/agent-dispatch") return load("lib/agent-dispatch.ts");
        throw new Error(`Unexpected import: ${name}`);
      },
      localStorage: { getItem: () => token }, sessionStorage: { getItem: () => null },
      fetch: fetcher, Response, crypto: { randomUUID },
    });
    return exports;
  }
  const { AgentDispatchPanel } = load("components/command-center/AgentDispatchPanel.tsx");
  const render = () => { cursor = 0; return AgentDispatchPanel() as Element; };
  function find(tree: unknown, predicate: (element: Element) => boolean): Element[] {
    if (Array.isArray(tree)) return tree.flatMap(child => find(child, predicate));
    if (!tree || typeof tree !== "object") return [];
    const node = tree as Element;
    return [...(predicate(node) ? [node] : []), ...find(node.props?.children, predicate)];
  }
  const buttons = (label: string) => find(render(), node => node.type === "button" && node.props.children === label);
  const pending = () => find(render(), node => node.props?.["aria-label"] === "Agent approval").length;
  const settle = () => new Promise<void>(done => setImmediate(done));
  async function click(label: string, index = 0) { buttons(label)[index].props.onClick(); await settle(); }
  async function open() { render(); effects.splice(0).forEach(effect => effect()); await settle(); }
  return { requests, buttons, pending, click, open, setToken: (value: string) => { token = value; } };
}

test("lost committed ruling can recover only through an explicit Run", async () => {
  const page = harness(true); await page.open();
  await page.click("Run / continue task");
  assert.equal(page.pending(), 1);
  assert.equal(page.buttons("Run / continue task")[1].props.disabled, true, "another task must stay blocked by the pending ruling");
  await page.click("Approve this step");
  const runsBeforeRefresh = page.requests.filter(r => r.path.endsWith("/run")).length;
  await page.click("Refresh tasks");
  assert.equal(page.requests.filter(r => r.path.endsWith("/run")).length, runsBeforeRefresh, "refresh must not start or retry a task");
  assert.equal(page.buttons("Run / continue task")[0].props.disabled, false);
  await page.click("Run / continue task");
  assert.equal(page.pending(), 0);
  assert.equal(page.requests.filter(r => r.path.endsWith("/approvals/decide")).length, 1, "recovery must not resubmit a ruling");
  assert.equal(page.buttons("Run / continue task")[0].props.disabled, true, "completed tasks must not be offered another Run");
});

test("still-pending recovery keeps the original one-time token", async () => {
  const page = harness(false); await page.open();
  await page.click("Run / continue task");
  await page.click("Approve this step");
  await page.click("Refresh tasks");
  await page.click("Run / continue task");
  assert.equal(page.pending(), 1);
  // The fixture withholds the token on this later Run. A lost token or an
  // auto-ruling cannot pass the original token assertions in its next decide.
  assert.equal(page.requests.filter(r => r.path.endsWith("/approvals/decide")).length, 1);
  await page.click("Approve this step");
  assert.equal(page.pending(), 0);
  await page.click("Run / continue task");
  assert.equal(page.requests.filter(r => r.path.endsWith("/run")).length, 3);
});

test("a changed session cannot use a retained approval token", async () => {
  const page = harness(false); await page.open();
  await page.click("Run / continue task");
  page.setToken("different-session");
  const before = page.requests.length;
  await page.click("Approve this step");
  assert.equal(page.requests.length, before);
  assert.equal(page.pending(), 1);
});
