#!/usr/bin/env python3
"""stig2ncm GUI — import DISA STIG compliance content into SolarWinds.

A small Windows-friendly desktop front end over stig2ncm.py. Point it at a
SolarWinds server, pick (or drop, or give the URL of) a STIG file, and import:

  * STIG zip / *-xccdf.xml / .xsl  →  NCM compliance policy report
                                      (Cirrus.PolicyReports.AddPolicyReport + StartCaching)
  * SCM policy .yaml               →  Server Configuration Monitor compliance policy
                                      (Orion.PolicyEngine.Policy.ImportPolicy)

The target module is detected from the file itself; nothing to configure.

Run from source:            python stig2ncm_gui.py
Build a Windows .exe:       pip install pyinstaller
                            pyinstaller --onefile --windowed --name STIG2SolarWinds ^
                                stig2ncm_gui.py
    (build on Windows; both stig2ncm files must sit in the same folder)

Optional extras, both auto-detected at runtime:
  * "Login with current Windows user" needs:  pip install requests requests-negotiate-sspi
    (Windows only — SSPI is what produces the current user's Negotiate token)
  * Drag-and-drop onto the window needs:      pip install tkinterdnd2
    Without it the Browse button does the same job.
"""

from __future__ import annotations

import os
import queue
import ssl
import sys
import tempfile
import threading
import tkinter as tk
import urllib.request
from tkinter import filedialog, messagebox, ttk

# stig2ncm.py sits next to this file, in source and in a PyInstaller bundle alike.
sys.path.insert(0, os.path.dirname(os.path.abspath(
    getattr(sys, "_MEIPASS", None) or __file__)))
import stig2ncm as core  # noqa: E402

try:  # optional: drag-and-drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except ImportError:
    HAVE_DND = False


class WindowsAuthClient:
    """SWIS client that authenticates as the current Windows user (SSPI/Negotiate).

    Same query/invoke surface as core.SwisClient, carried by `requests` because
    the standard library cannot produce a Negotiate token.
    """

    def __init__(self, host, port, verify):
        try:
            import requests
            from requests_negotiate_sspi import HttpNegotiateAuth
        except ImportError as exc:
            raise core.SwisError(
                "Windows-user login needs the requests and requests-negotiate-sspi "
                "packages (Windows only):\n    pip install requests requests-negotiate-sspi"
            ) from exc
        self.base = f"https://{host}:{port}{core.BASE_PATH}"
        self.session = requests.Session()
        self.session.auth = HttpNegotiateAuth()
        self.session.verify = verify
        if not verify:
            import urllib3
            urllib3.disable_warnings()

    def _request(self, path, body):
        resp = self.session.post(f"{self.base}/{path}", json=body, timeout=300)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("Message", resp.text)
            except ValueError:
                detail = resp.text
            raise core.SwisError(f"HTTP {resp.status_code} from {path}\n{detail}")
        return resp.json() if resp.text.strip() else None

    def query(self, swql, parameters=None):
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        return (self._request("Query", body) or {}).get("results", [])

    def invoke(self, entity, verb, *args):
        return self._request(f"Invoke/{entity}/{verb}", list(args))


class App:
    def __init__(self, root):
        self.root = root
        root.title("STIG → SolarWinds compliance importer")
        root.minsize(680, 560)
        self.log_queue = queue.Queue()
        self._downloaded = None  # temp file path when the source is a URL

        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        # --- connection -----------------------------------------------------
        conn = ttk.LabelFrame(frame, text="SolarWinds server", padding=8)
        conn.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        conn.columnconfigure(1, weight=1)

        ttk.Label(conn, text="Server IP/FQDN").grid(row=0, column=0, sticky="w", **pad)
        self.host = tk.StringVar()
        ttk.Entry(conn, textvariable=self.host).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(conn, text="SWIS port").grid(row=0, column=2, sticky="e", **pad)
        self.port = tk.StringVar(value=str(core.DEFAULT_PORT))
        ttk.Entry(conn, textvariable=self.port, width=7).grid(row=0, column=3, **pad)

        ttk.Label(conn, text="Username").grid(row=1, column=0, sticky="w", **pad)
        self.user = tk.StringVar()
        self.user_entry = ttk.Entry(conn, textvariable=self.user)
        self.user_entry.grid(row=1, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(conn, text="Password").grid(row=2, column=0, sticky="w", **pad)
        self.password = tk.StringVar()
        self.pass_entry = ttk.Entry(conn, textvariable=self.password, show="•")
        self.pass_entry.grid(row=2, column=1, columnspan=3, sticky="ew", **pad)

        self.win_auth = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn, text="Login with current Windows user",
                        variable=self.win_auth, command=self._toggle_auth).grid(
            row=3, column=0, columnspan=2, sticky="w", **pad)
        self.verify_tls = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn, text="Verify TLS certificate",
                        variable=self.verify_tls).grid(row=3, column=2, columnspan=2,
                                                       sticky="e", **pad)

        # --- source ----------------------------------------------------------
        src = ttk.LabelFrame(frame, text="STIG source", padding=8)
        src.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        src.columnconfigure(1, weight=1)

        self.source_kind = tk.StringVar(value="file")
        ttk.Radiobutton(src, text="File (zip, xccdf .xml, .xsl, SCM .yaml)",
                        variable=self.source_kind, value="file",
                        command=self._toggle_source).grid(row=0, column=0, columnspan=2,
                                                          sticky="w", **pad)
        self.file_path = tk.StringVar()
        self.file_entry = ttk.Entry(src, textvariable=self.file_path)
        self.file_entry.grid(row=1, column=1, sticky="ew", **pad)
        self.browse_btn = ttk.Button(src, text="Browse…", command=self._browse)
        self.browse_btn.grid(row=1, column=2, **pad)
        drop_hint = "or drop a file anywhere on this window" if HAVE_DND else \
            "(install tkinterdnd2 to enable drag-and-drop)"
        ttk.Label(src, text=drop_hint, foreground="gray").grid(
            row=2, column=1, sticky="w", padx=8)

        ttk.Radiobutton(src, text="STIG package URL (e.g. a dl.dod.cyber.mil zip link)",
                        variable=self.source_kind, value="url",
                        command=self._toggle_source).grid(row=3, column=0, columnspan=2,
                                                          sticky="w", **pad)
        self.url = tk.StringVar()
        self.url_entry = ttk.Entry(src, textvariable=self.url)
        self.url_entry.grid(row=4, column=1, columnspan=2, sticky="ew", **pad)

        # --- NCM options (ignored for SCM yaml) -------------------------------
        opts = ttk.LabelFrame(frame, text="NCM options (used for zip/xml sources only)",
                              padding=8)
        opts.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        opts.columnconfigure(1, weight=1)
        ttk.Label(opts, text="Node scope (Where clause)").grid(row=0, column=0,
                                                               sticky="w", **pad)
        self.node_where = tk.StringVar(value="(Nodes.Vendor = 'Cisco')")
        ttk.Entry(opts, textvariable=self.node_where).grid(row=0, column=1,
                                                           sticky="ew", **pad)
        ttk.Label(opts, text="Rule patterns").grid(row=1, column=0, sticky="w", **pad)
        self.mode = tk.StringVar(value="manual")
        box = ttk.Combobox(opts, textvariable=self.mode, state="readonly", width=52,
                           values=("manual — every rule flags for review (recommended)",
                                   "heuristic — draft patterns from the STIG check text"))
        box.current(0)
        box.grid(row=1, column=1, sticky="w", **pad)

        # --- actions and log --------------------------------------------------
        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.test_btn = ttk.Button(btns, text="Test connection", command=self._on_test)
        self.test_btn.pack(side="left", padx=4)
        self.preview_btn = ttk.Button(btns, text="Preview file", command=self._on_preview)
        self.preview_btn.pack(side="left", padx=4)
        self.import_btn = ttk.Button(btns, text="Import", command=self._on_import)
        self.import_btn.pack(side="left", padx=4)

        self.log = tk.Text(frame, height=14, state="disabled", wrap="word")
        self.log.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        frame.rowconfigure(4, weight=1)

        self._toggle_auth()
        self._toggle_source()
        if HAVE_DND:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self._on_drop)
        root.after(150, self._drain_log)

    # ---- UI plumbing --------------------------------------------------------

    def _toggle_auth(self):
        state = "disabled" if self.win_auth.get() else "normal"
        self.user_entry.configure(state=state)
        self.pass_entry.configure(state=state)

    def _toggle_source(self):
        file_mode = self.source_kind.get() == "file"
        self.file_entry.configure(state="normal" if file_mode else "disabled")
        self.browse_btn.configure(state="normal" if file_mode else "disabled")
        self.url_entry.configure(state="disabled" if file_mode else "normal")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select a STIG file",
            filetypes=[("STIG content", "*.zip *.xml *.xsl *.yaml *.yml"),
                       ("All files", "*.*")])
        if path:
            self.file_path.set(path)

    def _on_drop(self, event):
        path = event.data.strip("{}").split("} {")[0]
        self.source_kind.set("file")
        self._toggle_source()
        self.file_path.set(path)
        self._log(f"dropped: {path}")

    def _log(self, msg):
        self.log_queue.put(msg)

    def _drain_log(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", msg + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log)

    def _busy(self, working):
        state = "disabled" if working else "normal"
        for b in (self.test_btn, self.preview_btn, self.import_btn):
            b.configure(state=state)

    def _run_bg(self, fn):
        self._busy(True)

        def wrapper():
            try:
                fn()
            except Exception as exc:  # surfaced to the log, never a crash
                self._log(f"ERROR: {exc}")
            finally:
                self.root.after(0, self._busy, False)

        threading.Thread(target=wrapper, daemon=True).start()

    # ---- shared helpers ------------------------------------------------------

    def _client(self):
        host = self.host.get().strip()
        if not host:
            raise core.SwisError("enter the SolarWinds server IP/FQDN first")
        port = int(self.port.get().strip() or core.DEFAULT_PORT)
        verify = self.verify_tls.get()
        if self.win_auth.get():
            return WindowsAuthClient(host, port, verify)
        user = self.user.get().strip()
        if not user:
            raise core.SwisError("enter a username (or tick Windows-user login)")
        return core.SwisClient(host, user, self.password.get(), port=port, verify=verify)

    def _resolve_source(self):
        """Return a local file path for the chosen source, downloading a URL if needed."""
        if self.source_kind.get() == "file":
            path = self.file_path.get().strip()
            if not path or not os.path.isfile(path):
                raise ValueError("choose a file first")
            return path
        url = self.url.get().strip()
        if not url:
            raise ValueError("enter the STIG package URL first")
        name = os.path.basename(url.split("?")[0]) or "stig-download"
        dest = os.path.join(tempfile.gettempdir(), name)
        self._log(f"downloading {url} …")
        req = urllib.request.Request(url, headers={"User-Agent": "stig2ncm/1.0"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=300, context=ctx) as resp, \
                open(dest, "wb") as out:
            while chunk := resp.read(1 << 16):
                out.write(chunk)
        self._log(f"saved {dest} ({os.path.getsize(dest):,} bytes)")
        self._downloaded = dest
        return dest

    def _describe(self, path):
        """Detect the target module and return ('scm'|'ncm', preview lines)."""
        if core.is_scm_path(path):
            info = core.scan_scm_policy(core.load_scm_policy(path))
            sev = ", ".join(f"{v} {k}" for k, v in sorted(info["severity_counts"].items()))
            return "scm", [f"SCM compliance policy: {info['name']}",
                           f"  {len(info['rules'])} rules ({sev})",
                           "  target: Server Configuration Monitor "
                           "(Orion.PolicyEngine.Policy.ImportPolicy)"]
        lines = []
        benchmarks = core.load_benchmarks(path)
        for b in benchmarks:
            counts = {}
            for r in b["rules"]:
                counts[r["severity"]] = counts.get(r["severity"], 0) + 1
            sev = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low")
                            if s in counts)
            lines.append(f"NCM: {b['title']}")
            lines.append(f"  V{b['version']} {b['release']} — {len(b['rules'])} rules ({sev})")
        lines.append("  target: NCM compliance (Cirrus.PolicyReports.AddPolicyReport)")
        return "ncm", lines

    # ---- actions --------------------------------------------------------------

    def _on_test(self):
        def work():
            swis = self._client()
            rows = swis.query("SELECT TOP 1 EngineVersion FROM Orion.Engines")
            version = rows[0]["EngineVersion"] if rows else "unknown"
            ncm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Cirrus.%'")[0]["C"]
            scm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Orion.PolicyEngine.%'")[0]["C"]
            self._log(f"connected — platform {version}; "
                      f"NCM {'present' if ncm else 'NOT installed'}, "
                      f"SCM policy engine {'present' if scm else 'NOT installed'}")
        self._run_bg(work)

    def _on_preview(self):
        def work():
            path = self._resolve_source()
            for line in self._describe(path)[1]:
                self._log(line)
        self._run_bg(work)

    def _on_import(self):
        def work():
            path = self._resolve_source()
            kind, lines = self._describe(path)
            for line in lines:
                self._log(line)
            swis = self._client()
            if kind == "scm":
                policy_id, name = core.import_scm_policy(swis, core.load_scm_policy(path))
                self._log(f"imported SCM policy \"{name}\" (PolicyID {policy_id}).")
                self._log("Assign it to nodes under Settings → SCM Settings → Policies.")
                return
            mode = "heuristic" if self.mode.get().startswith("heuristic") else "manual"
            report = core.build_report(core.load_benchmarks(path),
                                       node_where=self.node_where.get().strip()
                                       or "(Nodes.Vendor = 'Cisco')",
                                       mode=mode)
            existing = swis.query(
                "SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                {"n": report["Name"]})
            if existing:
                raise core.SwisError(
                    f"a report named \"{report['Name']}\" already exists — "
                    "delete or rename it first; this tool never overwrites")
            n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
            self._log(f"importing \"{report['Name']}\" — "
                      f"{len(report['AssignedPolicies'])} policies, {n_rules} rules …")
            new_id = swis.invoke("Cirrus.PolicyReports", "AddPolicyReport", report, True)
            self._log(f"imported ({new_id}); starting compliance caching …")
            swis.invoke("Cirrus.PolicyReports", "StartCaching", [new_id])
            self._log("done — see My Dashboards → Network Configuration → Compliance.")
        self._run_bg(work)


def main():
    root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        # No display (e.g. run over SSH) — fail with guidance, not a traceback.
        print(f"could not start the GUI: {exc}\nUse the CLI instead: python stig2ncm.py --help",
              file=sys.stderr)
        sys.exit(1)
