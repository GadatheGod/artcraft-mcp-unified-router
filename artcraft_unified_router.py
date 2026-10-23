"""Unified MCP stdio router for ArtCraft apps (Python 3.10+, stdlib only)."""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

VERSION = "1.2.0"
PROTOCOL = "2025-03-26"

def read_message(stream):
    line = stream.readline()
    while line and not line.strip():
        line = stream.readline()
    if not line:
        return None
    if line.lstrip().startswith(b"{"):
        return json.loads(line)
    headers = {}
    while line and line.strip():
        if b":" in line:
            k, v = line.split(b":", 1)
            headers[k.strip().lower()] = v.strip()
        line = stream.readline()
    size = int(headers.get(b"content-length", b"0"))
    if not 0 < size <= 32 * 1024 * 1024:
        raise ValueError("Invalid Content-Length")
    data = stream.read(size)
    return json.loads(data) if len(data) == size else None

def send(stream, payload, lock):
    with lock:
        stream.write((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        stream.flush()

class Child:
    def __init__(self, name, config, logger):
        self.name, self.config, self.logger = name, config, logger
        self.proc = None
        self.lock = threading.Lock()
        self.start_lock = threading.Lock()
        self.pending = {}
        self.counter = 0
        self.tools = []
        self.ready = False
        self.error = None

    def start(self):
        cmd = [os.path.expandvars(str(p).replace("${HOME}", str(Path.home()))) for p in self.config["command"]]
        if not cmd:
            raise ValueError("Empty command")
        self.proc = subprocess.Popen(cmd, cwd=self.config.get("cwd") or None,
            env={**os.environ, **self.config.get("env", {})},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._log_stderr, daemon=True).start()
        result = self.request("initialize", {
            "protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "artcraft-unified-router", "version": VERSION}}, 15)
        if "error" in result:
            raise RuntimeError(result["error"])
        self.notify("notifications/initialized")
        self.ready = True
        self.refresh()

    def _read(self):
        try:
            while True:
                msg = read_message(self.proc.stdout)
                if msg is None:
                    break
                if "id" in msg and ("result" in msg or "error" in msg):
                    with self.lock:
                        waiter = self.pending.pop(msg["id"], None)
                    if waiter:
                        waiter.put(msg)
                elif "id" in msg and "method" in msg:
                    send(self.proc.stdin, {"jsonrpc":"2.0", "id":msg["id"],
                        "error":{"code":-32601, "message":"Child requests unsupported"}}, self.lock)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.ready = False
            with self.lock:
                waiters = list(self.pending.values())
                self.pending.clear()
            for waiter in waiters:
                waiter.put({"error":{"code":-32001, "message":"Connection closed"}})

    def _log_stderr(self):
        for line in self.proc.stderr:
            self.logger(f"{self.name}: {line.decode('utf-8','replace').rstrip()[:400]}")

    def request(self, method, params=None, timeout=60):
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError(f"{self.name} MCP server not running")
        waiter = queue.Queue(maxsize=1)
        with self.lock:
            self.counter += 1
            ident = self.counter
            self.pending[ident] = waiter
        try:
            send(self.proc.stdin, {"jsonrpc":"2.0", "id":ident, "method":method,
                "params":params or {}}, self.lock)
            return waiter.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"{method} timed out")
        finally:
            with self.lock:
                self.pending.pop(ident, None)

    def notify(self, method):
        send(self.proc.stdin, {"jsonrpc":"2.0", "method":method}, self.lock)

    def refresh(self):
        tools, cursor = [], None
        for _ in range(100):
            msg = self.request("tools/list", {"cursor":cursor} if cursor else {}, 20)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            data = msg.get("result", {})
            tools.extend(data.get("tools", []))
            cursor = data.get("nextCursor")
            if not cursor:
                break
        self.tools = tools

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

class Router:
    def __init__(self, config):
        self.config = config
        self.apps = {}
        self.mapping = {}
        self.out_lock = threading.Lock()

    def log(self, msg):
        print("[artcraft-router] " + str(msg), file=sys.stderr, flush=True)

    def load_apps(self):
        for name, spec in self.config.get("apps", {}).items():
            if not spec.get("enabled", False):
                continue
            child = Child(name, spec, self.log)
            self.apps[name] = child
            try:
                child.start()
                self.log(f"{name}: {len(child.tools)} tools")
            except Exception as exc:
                child.error = str(exc)
                child.ready = False
                child.close()
                self.log(f"{name}: unavailable: {exc}")
        self.rebuild()

    def rebuild(self):
        self.mapping = {}
        primary = str(self.config.get("primary_app", "SolidCraft")).casefold()
        for name, child in self.apps.items():
            if not child.ready:
                continue
            for tool in child.tools:
                original = tool.get("name")
                if not original:
                    continue
                self.mapping[name.lower() + "__" + original] = (child, original, tool)
                if name.casefold() == primary:
                    self.mapping.setdefault(original, (child, original, tool))

    def reconnect(self, child):
        with child.start_lock:
            if child.ready:
                child.refresh()
            else:
                child.close()
                child.start()
            child.error = None
        self.rebuild()

    def find_app(self, name):
        for key, child in self.apps.items():
            if key.casefold() == str(name).casefold():
                return child
        raise KeyError("Unknown app: " + str(name))

    def list_tools(self):
        schema = {"type":"object", "properties":{}}
        result = [
            {"name":"artcraft_status", "description":"Show app connection status and discovered tool counts", "inputSchema":schema},
            {"name":"artcraft_refresh", "description":"Reconnect and rediscover tools from every configured app", "inputSchema":schema},
            {"name":"artcraft_apps", "description":"List configured apps", "inputSchema":schema},
            {"name":"artcraft_tools", "description":"List live MCP tools for an app", "inputSchema":{"type":"object","properties":{"app":{"type":"string"},"reconnect":{"type":"boolean"}},"required":["app"]}},
            {"name":"artcraft_catalog", "description":"List the live tool catalog across apps", "inputSchema":{"type":"object","properties":{"app":{"type":"string"},"reconnect":{"type":"boolean"}}}},
            {"name":"artcraft_execute", "description":"Call any discovered MCP tool in an app", "inputSchema":{"type":"object","properties":{"app":{"type":"string"},"tool":{"type":"string"},"arguments":{"type":"object"}},"required":["app","tool"]}}
        ]
        for public, (child, original, tool) in self.mapping.items():
            item = dict(tool)
            item["name"] = public
            item["description"] = f"[{child.name}] " + item.get("description", original)
            result.append(item)
        return result

    @staticmethod
    def as_text(obj):
        return {"content":[{"type":"text", "text":json.dumps(obj, ensure_ascii=False)}]}

    def call_tool(self, name, args):
        args = args or {}
        if name in ("artcraft_status", "artcraft_apps"):
            return self.as_text({k:{"connected":v.ready,"tools":len(v.tools) if v.ready else 0,
                "error":v.error} for k,v in self.apps.items()})
        if name == "artcraft_refresh":
            for child in self.apps.values():
                try:
                    self.reconnect(child)
                except Exception as exc:
                    child.ready = False
                    child.error = str(exc)
                    child.close()
            self.rebuild()
            return self.call_tool("artcraft_status", {})
        if name == "artcraft_tools":
            child = self.find_app(args.get("app"))
            if args.get("reconnect") or not child.ready:
                try:
                    self.reconnect(child)
                except Exception as exc:
                    child.ready = False
                    child.error = str(exc)
                    child.close()
            return self.as_text({"app":child.name, "connected":child.ready,
                "error":child.error, "tools":child.tools if child.ready else []})
        if name == "artcraft_catalog":
            if args.get("reconnect"):
                self.call_tool("artcraft_refresh", {})
            wanted = args.get("app")
            return self.as_text({k:{"connected":v.ready,"error":v.error,
                "tools":v.tools if v.ready else []} for k,v in self.apps.items()
                if not wanted or k.casefold() == str(wanted).casefold()})
        if name == "artcraft_execute":
            child = self.find_app(args.get("app"))
            if not child.ready:
                self.reconnect(child)
            original = args.get("tool")
            if original not in {t.get("name") for t in child.tools}:
                raise KeyError("Unknown app tool: " + str(original))
            response = child.request("tools/call", {"name":original,
                "arguments":args.get("arguments") or {}}, child.config.get("timeout",120))
            if "error" in response:
                raise RuntimeError(response["error"])
            return response.get("result", {})
        if name not in self.mapping:
            raise KeyError("Unknown tool: " + str(name))
        child, original, _ = self.mapping[name]
        response = child.request("tools/call", {"name":original,"arguments":args},
            child.config.get("timeout",120))
        if "error" in response:
            raise RuntimeError(response["error"])
        return response.get("result", {})

    def reply(self, msg):
        send(sys.stdout.buffer, msg, self.out_lock)

    def handle(self, msg):
        method, ident = msg.get("method"), msg.get("id")
        if ident is None:
            return
        try:
            if method == "initialize":
                result = {"protocolVersion":PROTOCOL, "capabilities":{"tools":{"listChanged":False}},
                    "serverInfo":{"name":"artcraft-unified-router","version":VERSION}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools":self.list_tools()}
            elif method == "tools/call":
                params = msg.get("params") or {}
                result = self.call_tool(params.get("name"), params.get("arguments"))
            else:
                self.reply({"jsonrpc":"2.0","id":ident,"error":{"code":-32601,"message":"Method not found"}})
                return
            self.reply({"jsonrpc":"2.0","id":ident,"result":result})
        except Exception as exc:
            self.reply({"jsonrpc":"2.0","id":ident,"error":{"code":-32000,"message":str(exc)}})

    def run(self):
        self.load_apps()
        try:
            while True:
                msg = read_message(sys.stdin.buffer)
                if msg is None:
                    break
                if "method" in msg:
                    threading.Thread(target=self.handle,args=(msg,),daemon=True).start()
        finally:
            for child in self.apps.values():
                child.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).with_name("artcraft_router.json")))
    args = parser.parse_args()
    Router(json.loads(Path(args.config).read_text(encoding="utf-8"))).run()
