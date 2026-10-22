import assert from "node:assert/strict";
import test from "node:test";
import { dispatchGoal, dispatchRequest, parseDispatchTask, taskRunLimit } from "../lib/agent-dispatch.ts";

test("child agents inherit no unselected parent context", () => {
  assert.deepEqual(dispatchGoal(" audit code ", "owned-parent", 3), {
    path: "/agent-expansion/subagents", body: { goal: "audit code", parent_task_id: "owned-parent", max_steps: 3, inherit_context_keys: [] },
  });
  assert.equal(dispatchGoal("audit", "", 2).path, "/agent-tasks");
  for (const n of [0, 13, 1.5, NaN]) assert.throws(() => dispatchGoal("audit", "", n));
  assert.throws(() => dispatchGoal(" ", "", 1));
});

test("unreadable tasks and unsupported step limits are refused or bounded", () => {
  for (const value of [null, {}, { task_id: "x", goal: "g", state: "planned", current_step: 0 }]) assert.throws(() => parseDispatchTask(value));
  const task = parseDispatchTask({ task_id: "x", goal: "g", state: "planned", current_step: 0, plan: { steps: [] }, context: { max_steps: 3 } });
  assert.equal(taskRunLimit(task), 3);
  assert.equal(taskRunLimit({ ...task, context: { max_steps: 1000 } }), 8);
});

test("a locked session cannot send a request", async () => {
  let calls = 0;
  const fetcher = (async () => { calls++; return new Response("{}"); }) as typeof fetch;
  await assert.rejects(dispatchRequest("https://api.example", "", "/agent-tasks", { goal: "g" }, undefined, fetcher), /Sign in/);
  assert.equal(calls, 0);
});

test("explicit run sends one authenticated request with its idempotency key", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fetcher = (async (url, init) => { calls.push({ url: String(url), init }); return new Response('{"task":{}}'); }) as typeof fetch;
  await dispatchRequest("https://api.example", "test-session", "/agent-tasks/child/run", { max_steps: 3 }, "attempt-1", fetcher);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init?.method, "POST");
  assert.equal((calls[0].init?.headers as Record<string, string>).Authorization, "Bearer test-session");
  assert.equal((calls[0].init?.headers as Record<string, string>)["Idempotency-Key"], "attempt-1");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { max_steps: 3 });
});

test("ambiguous transport failure never retries a write", async () => {
  let calls = 0;
  const fetcher = (async () => { calls++; throw new Error("connection lost after send"); }) as typeof fetch;
  await assert.rejects(dispatchRequest("https://api.example", "test-session", "/agent-tasks", { goal: "g" }, undefined, fetcher), /connection lost/);
  assert.equal(calls, 1);
});

test("authentication refusal stays distinct from an empty task list", async () => {
  for (const [status, message] of [[401, /session expired/], [403, /not permitted/]] as const) {
    await assert.rejects(dispatchRequest("https://api.example", "test-session", "/agent-tasks", undefined, undefined,
      (async () => new Response("{}", { status })) as typeof fetch), message);
  }
});
