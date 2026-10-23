"""ArtCraft Windows launcher. Configure executable paths in artcraft_router.json."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "artcraft_router.json"
ROUTER = ROOT / "artcraft_unified_router.py"

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ArtCraft Unified MCP Launcher")
        self.geometry("760x560")
        self.config_data = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.selected = {}
        self.children = {}
        ttk.Label(self, text="ArtCraft Unified MCP Router", font=("Segoe UI", 16, "bold")).pack(pady=12)
        frame = ttk.LabelFrame(self, text="Applications", padding=12)
        frame.pack(fill="x", padx=16)
        for name, spec in self.config_data["apps"].items():
            var = tk.BooleanVar(value=spec.get("enabled", False))
            self.selected[name] = var
            ttk.Checkbutton(frame, text=name, variable=var).pack(anchor="w")
        self.tunnel_path = tk.StringVar(value=os.environ.get("ARTCRAFT_TUNNEL_EXE", ""))
        self.profile_path = tk.StringVar(value=os.environ.get("ARTCRAFT_TUNNEL_PROFILE", ""))
        for label, var in [("Tunnel executable", self.tunnel_path), ("Tunnel profile", self.profile_path)]:
            row = ttk.Frame(self)
            row.pack(fill="x", padx=16, pady=5)
            ttk.Label(row, text=label, width=20).pack(side="left")
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Browse", command=lambda v=var: v.set(filedialog.askopenfilename())).pack(side="left")
        actions = ttk.Frame(self)
        actions.pack(pady=10)
        ttk.Button(actions, text="Save selected apps", command=self.save).pack(side="left", padx=4)
        ttk.Button(actions, text="Start local router", command=self.start_router).pack(side="left", padx=4)
        ttk.Button(actions, text="Start tunnel", command=self.start_tunnel).pack(side="left", padx=4)
        ttk.Button(actions, text="Stop processes", command=self.stop).pack(side="left", padx=4)
        self.output = tk.Text(self, height=8)
        self.output.pack(fill="both", expand=True, padx=16, pady=8)

    def log(self, message):
        self.output.insert("end", str(message) + "\n")
        self.output.see("end")

    def save(self):
        for name, spec in self.config_data["apps"].items():
            spec["enabled"] = self.selected[name].get()
        CONFIG.write_text(json.dumps(self.config_data, indent=2) + "\n", encoding="utf-8")
        self.log("Saved " + str(CONFIG))

    def start_router(self):
        self.save()
        if "router" in self.children and self.children["router"].poll() is None:
            self.log("Router already running")
            return
        # Router communicates over stdio; use an MCP client to interact with it.
        self.log("For local MCP clients, configure: " + sys.executable + " " + str(ROUTER) + " --config " + str(CONFIG))
        self.log("Do not start the router separately when the tunnel/client launches it via stdio.")

    def start_tunnel(self):
        self.save()
        exe, profile = self.tunnel_path.get(), self.profile_path.get()
        if not Path(exe).is_file() or not Path(profile).is_file():
            messagebox.showerror("Missing configuration", "Select a valid tunnel executable and profile.")
            return
        if "tunnel" in self.children and self.children["tunnel"].poll() is None:
            self.log("Tunnel already running")
            return
        self.children["tunnel"] = subprocess.Popen([exe, "run", "--profile-file", profile], cwd=str(Path(exe).parent))
        self.log("Started tunnel; verify its MCP channel points to this router.")

    def stop(self):
        for name, proc in list(self.children.items()):
            if proc.poll() is None:
                proc.terminate()
                self.log("Stopped " + name)

if __name__ == "__main__":
    Launcher().mainloop()
