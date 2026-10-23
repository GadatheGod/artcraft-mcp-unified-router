import os, re, socket, subprocess, threading, queue, time, webbrowser, urllib.request, json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

HOME=Path.home()
BASE=Path(os.getenv('APPDATA',str(HOME/'AppData/Roaming')))/'tunnel-client'/'solidcraft.yaml'
TUNNEL=HOME/'Downloads/tunnel-client-v0.0.16-windows-amd64/tunnel-client.exe'
SOLID=HOME/'Downloads/solidcraft-0.18.2-windows-x64-portable'
# App-specific flags are based on published docs and earlier CLI output.
APPS={
 'SolidCraft': (SOLID, 'solidcraft',7878,'--connect','127.0.0.1:7878'),
 'GridCraft': (Path('C:/Program Files/GridCraft'),'gridcraft',7979,'--connect','7979'),
 'DeckCraft': (Path('C:/Program Files/DeckCraft'),'deckcraft',7990,'--connect','7990'),
 'CADCraft': (Path('C:/Program Files/CADCraft'),'cadcraft',7980,'--connect','127.0.0.1:7980'),
 'DesignCraft': (Path('C:/Program Files/DesignCraft'),'designcraft',7991,'--connect','7991'),
 'LightCraft': (Path('C:/Program Files/LightCraft'),'lightcraft',7992,'--connect','127.0.0.1:7992'),
 'PdfCraft': (Path('C:/Program Files/PdfCraft'),'pdfcraft',None,None,None),
 'PhotoCraft': (Path('C:/Program Files/PhotoCraft'),'photocraft',7994,'--bridge','127.0.0.1:7994'),
 'WordCraft': (Path('C:/Program Files/WordCraft'),'wordcraft',7981,'--connect','127.0.0.1:7981'),
 'VectorCraft': (Path('C:/Program Files/VectorCraft'),'vectorcraft',None,None,None),
 'FilmCraft': (Path('C:/Program Files/FilmCraft'),'filmcraft',None,None,None),
 'EffectCraft': (Path('C:/Program Files/EffectCraft'),'effectcraft',None,None,None),
 'FigCraft': (Path('C:/Program Files/FigCraft'),'figcraft',None,None,None),
 'SoundCraft': (Path('C:/Program Files/SoundCraft'),'soundcraft',None,None,None),
}

def listening(port):
 if port is None: return False
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=.3): return True
 except OSError: return False

class UI(tk.Tk):
 def __init__(self):
  super().__init__(); self.title('ArtCraft MCP — Unified Launcher v9'); self.geometry('1200x830')
  self.vars={}; self.status={}; self.events=queue.Queue(); self.tunnel=None; self.children={}
  self.base=tk.StringVar(value=str(BASE)); self.exe=tk.StringVar(value=str(TUNNEL)); self.dashboard=tk.StringVar(value='8081')
  self.verbose=tk.BooleanVar(value=False); self.auto_launch=tk.BooleanVar(value=True); self.log_history=[]; self.suppressed=0
  ttk.Label(self,text='ArtCraft + SolidCraft | Select → Launch GUIs → Start tunnel',font=('Segoe UI',15,'bold')).pack(anchor='w',padx=14,pady=10)
  frame=ttk.LabelFrame(self,text='Only checked apps are included in the generated tunnel YAML',padding=10);frame.pack(fill='x',padx=12)
  for i,(name,(folder,stem,port,flag,arg)) in enumerate(APPS.items()):
   var=tk.BooleanVar(value=name in ('SolidCraft','GridCraft'));self.vars[name]=var
   ttk.Checkbutton(frame,text=name,width=17,variable=var).grid(row=i//2,column=(i%2)*3,sticky='w',pady=3)
   ttk.Label(frame,text=('Headless MCP' if port is None else 'Port '+str(port)),width=17).grid(row=i//2,column=(i%2)*3+1,sticky='w')
   st=tk.StringVar(value='Not checked');self.status[name]=st
   ttk.Label(frame,textvariable=st,width=18).grid(row=i//2,column=(i%2)*3+2,sticky='w')
  ttk.Label(frame,text='Apps without a verified control port use CLI MCP mode; configure their CLI arguments if required.').grid(row=7,column=0,columnspan=6,sticky='w',pady=5)
  cfg=ttk.LabelFrame(self,text='Tunnel settings',padding=9);cfg.pack(fill='x',padx=12,pady=8)
  for i,(label,var) in enumerate([('Original YAML',self.base),('tunnel-client.exe',self.exe),('Dashboard port',self.dashboard)]):
   ttk.Label(cfg,text=label).grid(row=i,column=0,sticky='w');ttk.Entry(cfg,textvariable=var,width=95).grid(row=i,column=1,sticky='ew',padx=7,pady=3)
  cfg.columnconfigure(1,weight=1)
  ttk.Button(cfg,text='Browse YAML',command=lambda:self.browse(self.base,[('YAML','*.yaml *.yml')])).grid(row=0,column=2)
  ttk.Button(cfg,text='Browse EXE',command=lambda:self.browse(self.exe,[('Executable','*.exe')])).grid(row=1,column=2)
  ttk.Checkbutton(cfg,text='Launch selected GUIs automatically when starting',variable=self.auto_launch).grid(row=3,column=0,columnspan=3,sticky='w')
  ttk.Checkbutton(cfg,text='Verbose tunnel logs (include routine startup messages)',variable=self.verbose).grid(row=4,column=0,columnspan=3,sticky='w')
  bar=ttk.Frame(self);bar.pack(fill='x',padx=12,pady=4)
  for text,fn in [('Launch checked GUIs',self.launch),('Check ports',self.check),('Start tunnel',self.start),('Stop tunnel',self.stop),('Open dashboard',self.open_dashboard),('Show generated YAML',self.show_yaml),('Save logs',self.save_logs),('Clear logs',self.clear_logs),('Check key',self.check_key),('Scan installations',self.scan_installations)]:
   ttk.Button(bar,text=text,command=fn).pack(side='left',padx=3)
  self.health=tk.StringVar(value='Tunnel: not checked');ttk.Label(self,textvariable=self.health,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=14,pady=4)
  self.logbox=tk.Text(self,height=17,state='disabled',wrap='word');self.logbox.pack(fill='both',expand=True,padx=12,pady=9)
  self.after(150,self.drain);self.after(2500,self.tick)
  self.log('Ready. Only selected apps enter generated YAML. Routine tunnel logs hidden by default.')
 def browse(self,var,types):
  value=filedialog.askopenfilename(filetypes=types)
  if value:var.set(value)
 def save_logs(self):
  path=filedialog.asksaveasfilename(defaultextension='.txt',filetypes=[('Text','*.txt')])
  if path:Path(path).write_text('\n'.join(self.log_history)+'\n',encoding='utf-8')
 def clear_logs(self):
  self.log_history.clear();self.logbox.config(state='normal');self.logbox.delete('1.0','end');self.logbox.config(state='disabled')
 def check_key(self):
  try:
   raw=Path(self.base.get()).read_text(encoding='utf-8-sig')
   m=re.search(r'(?m)^\s*api_key:\s*[\"\']?([^\"\'\r\n#]+)',raw)
   if not m:self.log('KEY CHECK: no control_plane.api_key found in source YAML');return
   val=m.group(1).strip()
   if val.startswith('env:'):
    name=val[4:];self.log('KEY CHECK: '+name+' is '+('SET' if os.environ.get(name) else 'NOT SET')+' in launcher environment (value hidden)')
   else:self.log('KEY CHECK: API key configured directly in YAML (value hidden)')
  except Exception as e:self.log('KEY CHECK failed: '+str(e))
 def log(self,msg):
  msg=re.sub(r'(?i)(api[_-]?key|authorization|bearer)([\s:=]+)([^\s,}]+)',r'\1\2[REDACTED]',str(msg))
  line=time.strftime('%H:%M:%S')+'  '+msg;self.log_history.append(line)
  if len(self.log_history)>5000:self.log_history=self.log_history[-5000:]
  self.logbox.config(state='normal');self.logbox.insert('end',line+'\n');self.logbox.see('end');self.logbox.config(state='disabled')
 def drain(self):
  while not self.events.empty():
   k,*a=self.events.get_nowait()
   if k=='log':self.log(a[0])
   elif k=='status':self.status[a[0]].set(a[1])
   elif k=='health':self.health.set(a[0])
  self.after(150,self.drain)
 def scan_installations(self):
  for name,(folder,stem,port,flag,arg) in APPS.items():
   cli=folder/(stem+'-cli.exe')
   gui=folder/(stem+'.exe')
   state='CLI READY' if cli.is_file() else ('GUI ONLY' if gui.is_file() else 'NOT INSTALLED')
   self.status[name].set(state)
   self.log(name+': '+state)
 def selected(self):return [n for n,v in self.vars.items() if v.get()]
 def launch(self):
  for name in self.selected():
   folder,stem,port,flag,arg=APPS[name]
   if port is None:self.log(name+': headless MCP only; no GUI-control launch');continue
   if listening(port):self.log(name+': GUI port already listening');continue
   exe=folder/(stem+'.exe')
   if not exe.exists():self.log(name+': missing '+str(exe));continue
   try:
    p=subprocess.Popen([str(exe),'--control',str(port)],cwd=str(folder));self.children[name]=p
    self.log(name+': launched GUI PID '+str(p.pid)+' with --control '+str(port))
   except Exception as e:self.log(name+': launch failed '+str(e))
  self.after(1400,self.check)
 def check(self):
  def worker():
   for name in APPS:
    port=APPS[name][2];self.events.put(('status',name,'CLI MODE' if port is None else ('LISTENING' if listening(port) else 'Not listening')))
   self.events.put(('log','GUI port check completed'))
  threading.Thread(target=worker,daemon=True).start()
 def generated_path(self):return Path(self.base.get()).with_name('artcraft_selected.generated.yaml')
 def build_yaml(self):
  source=Path(self.base.get());raw=source.read_text(encoding='utf-8-sig')
  m=re.search(r'(?m)^mcp:\s*$',raw)
  if not m:raise ValueError('Original YAML has no top-level mcp: section')
  prefix=raw[:m.start()].rstrip()
  if not re.search(r'(?m)^\s+tunnel_id:',prefix):raise ValueError('Missing tunnel_id in original YAML')
  selected=self.selected()
  if not selected:raise ValueError('Tick at least one app')
  router=Path(__file__).with_name('artcraft_unified_router.py')
  config_path=Path(__file__).with_name('artcraft_router.json')
  if not router.is_file() or not config_path.is_file():raise FileNotFoundError('Router and JSON config must be next to launcher')
  config=json.loads(config_path.read_text(encoding='utf-8'))
  for name,spec in config['apps'].items():spec['enabled']=name in selected
  config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
  import sys
  cmd='"'+sys.executable.replace('\\','/')+'" "'+str(router).replace('\\','/')+'" --config "'+str(config_path).replace('\\','/')+'"'
  lines=['mcp:','  commands:','    - channel: main',"      command: '"+cmd.replace("'","''")+"'"]
  dest=self.generated_path();dest.write_text(prefix+'\n'+'\n'.join(lines)+'\n',encoding='utf-8')
  return dest
 def show_yaml(self):
  try:
   p=self.build_yaml();self.log('Generated '+str(p));os.startfile(str(p))
  except Exception as e:messagebox.showerror('YAML generation',str(e))
 def start(self):
  if self.tunnel and self.tunnel.poll() is None:self.log('Tunnel already running');return
  try:
   p=self.build_yaml();exe=Path(self.exe.get());assert exe.is_file(), 'tunnel-client.exe not found'
   if self.auto_launch.get():self.launch()
   missing=[name for name in self.selected() if APPS[name][2] is not None and not listening(APPS[name][2])]
   if missing and self.auto_launch.get():
    self.log('Waiting up to 12 seconds for GUI ports: '+', '.join(missing))
    for _ in range(24):
     if all(listening(APPS[n][2]) for n in missing):break
     self.update();time.sleep(.5)
    missing=[n for n in missing if not listening(APPS[n][2])]
   if missing:
    messagebox.showwarning('GUI ports unavailable','Launch these GUIs first: '+', '.join(missing)+'\nTunnel not started to avoid MCP channel failures.');return
   port=int(self.dashboard.get())
   if listening(port):messagebox.showwarning('Existing tunnel','Dashboard port already listening. Stop existing tunnel before starting another.');return
   self.tunnel=subprocess.Popen([str(exe),'run','--profile-file',str(p)],cwd=str(exe.parent),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   self.log('Tunnel started PID '+str(self.tunnel.pid)+' using '+str(p))
   threading.Thread(target=self.reader,args=(self.tunnel,),daemon=True).start()
  except Exception as e:messagebox.showerror('Tunnel start',str(e));self.log('Tunnel start failed: '+str(e))
 def reader(self,p):
  noise={'provided','supplied','run','invoking','OnStart hook executing','OnStart hook executed',
         'OnStop hook executing','OnStop hook executed','mcp channel route resolved'}
  interesting=('error','failed','warn','connect','timeout','poll','ready','started','listening',
               'exit','shutdown','metadata','tunnel-client','web ui','stdio mcp')
  for line in p.stdout:
   raw=line.strip()
   if not raw:continue
   level='';msg=raw
   try:
    d=json.loads(raw)
    if isinstance(d,dict):
     level=str(d.get('level') or d.get('severity') or '').upper()
     msg=str(d.get('msg') or d.get('message') or d.get('error') or d.get('event') or '')
     if msg in ('run','provided','supplied','invoking'):
      msg=str(d.get('error') or d.get('err') or msg)
   except (ValueError,TypeError):pass
   if not self.verbose.get():
    if msg in noise or msg.startswith(('OnStart hook','OnStop hook')):self.suppressed+=1;continue
    if not any(word in msg.lower() for word in interesting) and level not in ('ERROR','WARN','WARNING','FATAL'):
     self.suppressed+=1;continue
   self.events.put(('log','[tunnel'+(' '+level if level else '')+'] '+msg[:550]))
  self.events.put(('log','Tunnel exited, code '+str(p.wait())+' | routine messages hidden: '+str(self.suppressed)))
 def stop(self):
  if self.tunnel and self.tunnel.poll() is None:
   self.tunnel.terminate();self.log('Stopped launcher-owned tunnel')
  else:self.log('No launcher-owned tunnel running')
 def open_dashboard(self):webbrowser.open('http://127.0.0.1:'+self.dashboard.get()+'/ui')
 def tick(self):
  def worker():
   try:
    url='http://127.0.0.1:'+self.dashboard.get()+'/healthz'
    with urllib.request.urlopen(url,timeout=1) as r:status='HTTP '+str(r.status)
   except Exception:status='Not reachable'
   proc='Running PID '+str(self.tunnel.pid) if self.tunnel and self.tunnel.poll() is None else 'Not running in launcher'
   self.events.put(('health','Tunnel: '+proc+' | health: '+status+' (health alone does not confirm cloud MCP access)'))
   for name in self.selected():
    port=APPS[name][2]
    self.events.put(('status',name,'CLI MODE' if port is None else ('LISTENING' if listening(port) else 'Not listening')))
  threading.Thread(target=worker,daemon=True).start()
  self.after(5000,self.tick)

if __name__=='__main__':UI().mainloop()