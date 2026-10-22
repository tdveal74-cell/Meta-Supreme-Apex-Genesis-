"""Disposable network-namespace proof. Never edits host firewall or production.
Uses fixture-only owner/key/approvals and deletes its containers/networks/volumes.
"""

import asyncio
import ipaddress
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx

from app.services.devon_browser import DevonBrowserAdapter
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.devon.approval import ApprovalQueue

HERE = Path(__file__).resolve().parent
prefix = "devon-egress-proof-" + uuid4().hex[:10]
net = prefix + "-private"
proxy = prefix + "-proxy"
worker = prefix + "-worker"
ipc = prefix + "-ipc"
data = prefix + "-data"
owner = str(uuid4())
key = uuid4().hex + uuid4().hex
isolation = HERE / (prefix + "-isolation.json")
isolation.write_text("{}")
isolation.chmod(0o444)
env = HERE / (prefix + ".env")
env.write_text(
    "DEVON_BROWSER_PROXY_CANDIDATE_ENABLED=1\nDEVON_BROWSER_NETWORK_MODE=public-proxy-v1\nDEVON_BROWSER_SESSION_OWNER_ID="
    + owner
    + "\nDEVON_BROWSER_SESSION_KEY="
    + key
    + "\nDEVON_BROWSER_ALLOWED_HOSTS=example.org\n"
)
env.chmod(0o600)


def run(args, check=True):
    r = subprocess.run(args, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError("fixture command failed: " + args[0] + " " + r.stderr[-1500:])
    return r


async def proof(socket):
    approvals = ApprovalQueue()
    a = DevonBrowserAdapter(
        approvals=approvals,
        owner_id=owner,
        key=key,
        allowed_hosts=("example.org",),
        network_policy="public-proxy-v1",
        enabled=True,
    )
    transport = httpx.AsyncHTTPTransport
    httpx.AsyncHTTPTransport = lambda **kw: transport(uds=socket, retries=0)
    session = str(uuid4())

    async def execute(action, **extra):
        clean = {"session_id": session, "allowed_hosts": ["example.org"], **extra}
        tool = "browser.session." + action
        binding = approval_binding(
            task_id="fixture-task", step_id=uuid4().hex, tool_name=tool, arguments=clean
        )
        step_id = "fixture-" + uuid4().hex
        binding = approval_binding(
            task_id="fixture-task", step_id=step_id, tool_name=tool, arguments=clean
        )
        record, token = approvals.request(
            title="fixture only",
            what_happens="fixture " + approval_marker(binding),
            requested_by=RUNTIME_REQUESTED_BY,
            owner_id=owner,
        )
        assert approvals.decide(record.request_id, token, "approve").ok
        args = {
            **clean,
            APPROVAL_METADATA_KEY: {
                "request_id": record.request_id,
                "binding": binding,
                "task_id": "fixture-task",
                "step_id": step_id,
                "tool_name": tool,
            },
        }
        result = await a.execute(action, args)
        return result

    try:
        opened = await execute("open")
        assert opened.ok, opened
        navigated = await execute("navigate", url="https://example.org/")
        assert navigated.ok, navigated
        snapshot = await execute("snapshot")
        assert snapshot.ok, snapshot
        page = snapshot.metadata["browser_receipt"]["page"]
        assert "documentation examples" in page["text"], page
        for url in ("https://127.0.0.1/", "http://169.254.169.254/", "https://example.net/"):
            refused = await execute("navigate", url=url)
            assert not refused.ok
        closed = await execute("close")
        assert closed.ok, closed
        print(
            json.dumps(
                {
                    "adapter": "owner-bound-runtime-approval",
                    "navigation": "https://example.org/",
                    "page_text_contains": "documentation examples",
                    "scripts_disabled": page["scripts_disabled"],
                    "snapshot_receipt": bool(snapshot.metadata["provider_receipt_id"]),
                    "nonallowed_targets_refused": 3,
                    "closed": True,
                }
            ),
            flush=True,
        )
    finally:
        httpx.AsyncHTTPTransport = transport


try:
    run(["docker", "network", "create", "--internal", net])
    subnet = json.loads(run(["docker", "network", "inspect", net]).stdout)[0]["IPAM"]["Config"][0][
        "Subnet"
    ]
    network = ipaddress.ip_network(subnet)
    proxyip = str(network.network_address + 2)
    workerip = str(network.network_address + 3)
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            proxy,
            "--network",
            net,
            "--ip",
            proxyip,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "10001:10001",
            "--memory",
            "128m",
            "--pids-limit",
            "64",
            "--cpus",
            "0.5",
            "--env",
            "DEVON_EGRESS_PROXY_ENABLED=1",
            "--env",
            "DEVON_EGRESS_BIND=" + proxyip,
            "--env",
            "DEVON_BROWSER_ALLOWED_HOSTS=example.org",
            "--mount",
            "type=bind,src=" + str(HERE / "egress_proxy.py") + ",dst=/proxy.py,readonly",
            "python:3.12-slim",
            "python",
            "-B",
            "/proxy.py",
        ]
    )
    run(["docker", "network", "connect", "bridge", proxy])
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            worker,
            "--init",
            "--network",
            net,
            "--ip",
            workerip,
            "--user",
            "10001:10001",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--security-opt",
            "seccomp=" + str(HERE / "seccomp-browser.json"),
            "--pids-limit",
            "128",
            "--memory",
            "768m",
            "--cpus",
            "1",
            "--shm-size",
            "128m",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m,uid=10001,gid=10001,mode=700",
            "--mount",
            "type=bind,src=" + str(isolation) + ",dst=/run/devon-network/isolation.json,readonly",
            "--env-file",
            str(env),
            "--env",
            "DEVON_BROWSER_PROXY=http://" + proxyip + ":3128",
            "--mount",
            "type=volume,src=" + ipc + ",dst=/run/devon-browser",
            "--mount",
            "type=volume,src=" + data + ",dst=/var/lib/devon-browser",
            "devon-worker-egress-candidate:20261022",
            "sleep",
            "infinity",
        ]
    )
    pid = run(["docker", "inspect", "-f", "{{.State.Pid}}", worker]).stdout.strip()
    # These rules modify ONLY the disposable worker network namespace.
    run(
        [
            "nsenter",
            "-t",
            pid,
            "-n",
            "iptables",
            "-A",
            "OUTPUT",
            "-d",
            proxyip,
            "-p",
            "tcp",
            "--dport",
            "3128",
            "-j",
            "ACCEPT",
        ]
    )
    run(["nsenter", "-t", pid, "-n", "iptables", "-P", "OUTPUT", "DROP"])
    run(["nsenter", "-t", pid, "-n", "ip6tables", "-P", "OUTPUT", "DROP"])
    rules = run(["nsenter", "-t", pid, "-n", "iptables", "-S", "OUTPUT"]).stdout
    assert "-P OUTPUT DROP" in rules and "--dport 3128 -j ACCEPT" in rules
    bypass = "import net from'node:net';const targets=['169.254.169.254','172.17.0.1','1.1.1.1'];for(const host of targets){await new Promise((resolve,reject)=>{const s=net.connect({host,port:443});s.setTimeout(500,()=>{s.destroy();resolve()});s.on('connect',()=>{s.destroy();reject(Error('direct path reachable'))});s.on('error',()=>resolve());});}console.log('DIRECT IP BYPASS REFUSED 3');"
    netns = run(["docker", "exec", worker, "readlink", "/proc/self/ns/net"]).stdout.strip()
    isolation.write_text(
        json.dumps(
            {
                "policy": "public-proxy-v1",
                "netns": netns,
                "proxy": "http://" + proxyip + ":3128",
                "allowed_hosts": ["example.org"],
                "output_rules": "proxy-tcp3128-only-ipv6-drop",
                "verified_at": int(time.time() * 1000),
            }
        )
    )
    bypassout = run(["docker", "exec", worker, "node", "--input-type=module", "-e", bypass]).stdout
    print(bypassout.strip(), flush=True)
    proxyping = run(
        [
            "docker",
            "exec",
            worker,
            "node",
            "--input-type=module",
            "-e",
            "import net from'node:net';const u=new URL(process.env.DEVON_BROWSER_PROXY);const s=net.connect({host:u.hostname,port:Number(u.port)},()=>s.write('CONNECT example.org:443 HTTP/1.1\\r\\nHost: example.org:443\\r\\n\\r\\n'));s.on('data',x=>{console.log(x.toString());s.destroy()});s.on('error',e=>{console.log(e.code);process.exitCode=1});s.setTimeout(3000,()=>{console.log('proxy timedout');s.destroy();process.exitCode=1});",
        ]
    )
    print(proxyping.stdout, flush=True)
    run(["docker", "exec", "-d", worker, "node", "/app/proxy-launcher.mjs"])
    socketdir = run(["docker", "volume", "inspect", "-f", "{{.Mountpoint}}", ipc]).stdout.strip()
    socket = socketdir + "/worker.sock"
    for _ in range(30):
        if Path(socket).exists():
            break
        time.sleep(0.1)
    assert Path(socket).is_socket(), "worker socket missing"
    asyncio.run(proof(socket))
    print("ADAPTER UDS CHROMIUM PUBLIC EGRESS PROOF PASS", flush=True)
finally:
    for label, container in (("worker", worker), ("proxy", proxy)):
        logs = run(["docker", "logs", container], check=False)
        (HERE / (label + "-fixture.log")).write_text(logs.stdout + logs.stderr)
    for container in (worker, proxy):
        run(["docker", "rm", "-f", container], check=False)
    for volume in (ipc, data):
        run(["docker", "volume", "rm", volume], check=False)
    run(["docker", "network", "rm", net], check=False)
    env.unlink(missing_ok=True)
    isolation.unlink(missing_ok=True)
