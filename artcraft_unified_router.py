"""ArtCraft unified MCP stdio router. Python 3.10+, standard library only.
Run: python artcraft_unified_router.py --config artcraft_router.json
One MCP stdio endpoint; fans out to local stdio MCP CLI processes.
"""
import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

PROTOCOL = '2025-03-26'
VERSION = '1.2.0'

def write_packet(stream, obj):
    payload = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    stream.write(b'Content-Length: ' + str(len(payload)).encode() + b'\r\n\r\n' + payload)
    stream.flush()

def read_packet(stream):
    # Supports standard MCP newline-delimited JSON and Content-Length framing.
    line = stream.readline()
    while line and not line.strip():
        line = stream.readline()
    if not line:
        return None
    if line.lstrip().startswith(b'{'):
        return json.loads(line)
    headers = {}
    while line and line.strip():
        if b':' in line:
            k, v = line.split(b':', 1)
            headers[k.strip().lower()] = v.strip()
        line = stream.readline()
    length = int(headers.get(b'content-length', b'0'))
    if length <= 0 or length > 32 * 1024 * 1024:
        raise ValueError('Invalid MCP message length')
    data = stream.read(length)
    if len(data) != length:
        return None
    return json.loads(data)

def send(stream, obj, lock):
    with lock:
        # JSONL is MCP stdio framing; do not print diagnostic output to stdout.
        stream.write((json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8'))
        stream.flush()

class Child:
    def __init__(self, name, spec, logger):
        self.name, self.spec, self.log = name, spec, logger
        self.proc = None
        self.lock = threading.Lock()
        self.pending = {}
        self.next_id = 1
        self.tools = []
        self.ready = False
        self.last_error = None
        self.start_lock = threading.Lock()

    def start(self):
        cmd = [os.path.expandvars(part.replace('${HOME}', str(Path.home()))) for part in self.spec['command']]
        if isinstance(cmd, str):
            raise ValueError('command must be a JSON array, not a shell string')
        if not cmd:
            raise ValueError('empty command')
        env = os.environ.copy()
        env.update(self.spec.get('env', {}))
        self.proc = subprocess.Popen(cmd, cwd=self.spec.get('cwd') or None,
                                     env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()
        response = self.request('initialize', {'protocolVersion': PROTOCOL,
             'capabilities': {}, 'clientInfo': {'name': 'artcraft-unified-router', 'version': VERSION}}, timeout=12)
        if 'error' in response:
            raise RuntimeError(str(response['error']))
        self.notify('notifications/initialized')
        self.ready = True
        self.refresh()

    def _reader(self):
        try:
            while True:
                msg = read_packet(self.proc.stdout)
                if msg is None:
                    break
                if 'id' in msg and ('result' in msg or 'error' in msg):
                    with self.lock:
                        dest = self.pending.pop(msg['id'], None)
                    if dest:
                        dest.put(msg)
                elif 'id' in msg and 'method' in msg:
                    # Child-to-client requests unsupported; respond explicitly.
                    send(self.proc.stdin, {'jsonrpc':'2.0','id':msg['id'],
                          'error':{'code':-32601,'message':'Router does not support child-initiated requests'}}, self.lock)
        except Exception as exc:
            self.last_error = str(exc)
        finally:
            self.ready = False
            with self.lock:
                waiters = list(self.pending.values())
                self.pending.clear()
            for waiter in waiters:
                waiter.put({'error': {'code': -32001, 'message': 'App connection closed'}})

    def _stderr(self):
        for line in self.proc.stderr:
            self.log(self.name + ': ' + line.decode('utf-8', 'replace').rstrip()[:400])

    def request(self, method, params=None, timeout=45):
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError('App MCP process is not running')
        waiter = queue.Queue(maxsize=1)
        with self.lock:
            ident = self.next_id
            self.next_id += 1
            self.pending[ident] = waiter
        try:
            send(self.proc.stdin, {'jsonrpc':'2.0', 'id':ident, 'method':method,
                                   'params':params or {}}, self.lock)
            return waiter.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError('%s timed out after %ss' % (method, timeout))
        finally:
            with self.lock:
                self.pending.pop(ident, None)

    def notify(self, method, params=None):
        send(self.proc.stdin, {'jsonrpc':'2.0','method':method,
                               **({'params':params} if params else {})}, self.lock)

    def refresh(self):
        all_tools = []
        cursor = None
        for _ in range(100):
            params = {'cursor':cursor} if cursor else {}
            response = self.request('tools/list', params, timeout=15)
            if 'error' in response:
                raise RuntimeError(str(response['error']))
            result = response.get('result', {})
            all_tools.extend(result.get('tools', []))
            cursor = result.get('nextCursor')
            if not cursor:
                break
        self.tools = all_tools

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

class Router:
    def __init__(self, config):
        self.config = config
        self.apps = {}
        self.mapping = {}
        self.out_lock = threading.Lock()
        self.log_lock = threading.Lock()

    def log(self, message):
        with self.log_lock:
            sys.stderr.write('[artcraft-router] ' + str(message) + '\n')
            sys.stderr.flush()

    def load_apps(self):
        for name, spec in self.config['apps'].items():
            if not spec.get('enabled', False):
                continue
            child = Child(name, spec, self.log)
            self.apps[name] = child
            try:
                child.start()
                self.log('%s: connected (%d tools)' % (name, len(child.tools)))
            except Exception as exc:
                child.last_error = str(exc)
                child.ready = False
                child.close()
                self.log('%s: unavailable: %s' % (name, exc))
        self.rebuild()

    def rebuild(self):
        self.mapping = {}
        primary = self.config.get('primary_app', 'SolidCraft')
        for name, child in self.apps.items():
            if not child.ready:
                continue
            for tool in child.tools:
                original = tool.get('name')
                if not original:
                    continue
                public = name.lower() + '__' + original
                self.mapping[public] = (child, original, tool)
                # Compatibility: existing Craftapps clients use unprefixed names.
                # Only alias the designated primary app; other apps remain namespaced.
                if name.casefold() == str(primary).casefold():
                    self.mapping.setdefault(original, (child, original, tool))

    def reconnect(self, child):
        with child.start_lock:
            if not child.ready:
                child.close()
                child.start()
            else:
                child.refresh()
            child.last_error = None
        self.rebuild()

    def list_tools(self):
        result = [{'name':'artcraft_status', 'description':'List configured ArtCraft apps, their MCP connection status and discovered tool counts.',
                   'inputSchema':{'type':'object','properties':{}}},
                  {'name':'artcraft_refresh', 'description':'Reconnect unavailable apps and refresh MCP tool discovery. Reconnect ChatGPT if newly discovered tools are not visible.',
                   'inputSchema':{'type':'object','properties':{}}}]
        result.extend([
          {'name':'artcraft_apps','description':'List all configured ArtCraft applications and their connection status.',
           'inputSchema':{'type':'object','properties':{}}},
          {'name':'artcraft_tools','description':'Discover live MCP commands for one ArtCraft application. Optional reconnect.',
           'inputSchema':{'type':'object','properties':{'app':{'type':'string'},'reconnect':{'type':'boolean'}},'required':['app']}},
          {'name':'artcraft_catalog','description':'Return the complete live MCP tool catalog across all connected ArtCraft applications, including schemas and aliases.',
           'inputSchema':{'type':'object','properties':{'app':{'type':'string'},'reconnect':{'type':'boolean'}}}},
          {'name':'artcraft_execute','description':'Execute a discovered MCP tool in the named ArtCraft application. Use artcraft_tools first to inspect its argument schema.',
           'inputSchema':{'type':'object','properties':{'app':{'type':'string'},'tool':{'type':'string'},'arguments':{'type':'object'}},'required':['app','tool']}}
        ])
        for public, (child, original, tool) in self.mapping.items():
            t = dict(tool)
            t['name'] = public
            t['description'] = '[' + child.name + '] ' + t.get('description', original)
            result.append(t)
        return result

    def find_app(self, name):
        for key, child in self.apps.items():
            if key.casefold() == str(name).casefold():
                return child
        raise KeyError('Unknown app: ' + str(name))

    def call_tool(self, name, args):
        if name == 'artcraft_apps':
            return self.call_tool('artcraft_status', {})
        if name == 'artcraft_tools':
            child = self.find_app(args.get('app'))
            if args.get('reconnect') or not child.ready:
                try:
                    self.reconnect(child)
                except Exception as exc:
                    child.last_error = str(exc)
                    child.ready = False
                    child.close()
            return {'content':[{'type':'text','text':json.dumps({
                'app':child.name,'connected':child.ready,'error':child.last_error,
                'tools':child.tools if child.ready else []},ensure_ascii=False)}]}
        if name == 'artcraft_catalog':
            if args.get('reconnect'):
                for child in self.apps.values():
                    try: self.reconnect(child)
                    except Exception as exc:
                        child.ready = False; child.last_error = str(exc); child.close()
                self.rebuild()
            wanted = args.get('app')
            apps = {k:v for k,v in self.apps.items() if not wanted or k.casefold() == str(wanted).casefold()}
            if wanted and not apps: raise KeyError('Unknown app: ' + str(wanted))
            catalog = {k:{'connected':v.ready,'error':v.last_error,
                'tools':v.tools if v.ready else []} for k,v in apps.items()}
            return {'content':[{'type':'text','text':json.dumps(catalog,ensure_ascii=False)}]}
        if name == 'artcraft_execute':
            child = self.find_app(args.get('app'))
            if not child.ready:
                self.reconnect(child)
            original = args.get('tool')
            if original not in {t.get('name') for t in child.tools}:
                raise KeyError('Unknown app tool: ' + str(original) + '. Call artcraft_tools first.')
            response = child.request('tools/call',{'name':original,'arguments':args.get('arguments') or {}},
                                     timeout=float(child.spec.get('timeout',120)))
            if 'error' in response:
                raise RuntimeError(str(response['error']))
            return response.get('result',{})
        if name == 'artcraft_status':
            info = {name: {'connected': child.ready,
                           'tools':len(child.tools) if child.ready else 0,
                           'error':child.last_error} for name, child in self.apps.items()}
            return {'content':[{'type':'text','text':json.dumps(info, indent=2)}]}
        if name == 'artcraft_refresh':
            for child in self.apps.values():
                try:
                    self.reconnect(child)
                except Exception as exc:
                    child.ready = False
                    child.last_error = str(exc)
                    child.close()
            self.rebuild()
            return self.call_tool('artcraft_status', {})
        if name not in self.mapping:
            raise KeyError('Unknown tool: ' + str(name))
        child, original, _ = self.mapping[name]
        response = child.request('tools/call', {'name':original, 'arguments':args or {}},
                                 timeout=float(child.spec.get('timeout', 120)))
        if 'error' in response:
            raise RuntimeError(str(response['error']))
        return response.get('result', {})

    def handle(self, msg):
        method, ident = msg.get('method'), msg.get('id')
        if method == 'notifications/initialized':
            return
        if ident is None:
            return
        try:
            if method == 'initialize':
                result = {'protocolVersion':msg.get('params', {}).get('protocolVersion', PROTOCOL),
                          'capabilities':{'tools':{'listChanged':False}},
                          'serverInfo':{'name':'artcraft-unified-router','version':VERSION}}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools':self.list_tools()}
            elif method == 'tools/call':
                params = msg.get('params') or {}
                result = self.call_tool(params.get('name'), params.get('arguments', {}))
            else:
                self.reply({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}})
                return
            self.reply({'jsonrpc':'2.0','id':ident,'result':result})
        except Exception as exc:
            self.reply({'jsonrpc':'2.0','id':ident,'error':{'code':-32000,'message':str(exc)}})

    def reply(self, obj):
        send(sys.stdout.buffer, obj, self.out_lock)

    def run(self):
        self.load_apps()
        try:
            while True:
                msg = read_packet(sys.stdin.buffer)
                if msg is None:
                    break
                if 'method' in msg:
                    threading.Thread(target=self.handle,args=(msg,),daemon=True).start()
        finally:
            for child in self.apps.values():
                child.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(Path(__file__).with_name('artcraft_router.json')))
    args = parser.parse_args()
    Router(json.loads(Path(args.config).read_text(encoding='utf-8'))).run()