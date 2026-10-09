#!/usr/bin/env python3
"""DISA STIG Conversion Tool - DISA STIG to SolarWinds compliance importer.

One self-contained file: GUI and CLI together, standard library only.

Takes a STIG package as DISA publishes it on https://public.cyber.mil/stigs/downloads/
(a zip whose payload is one or more XCCDF benchmark files named ``*-xccdf.xml``; the
``.xsl`` alongside them is only the browser stylesheet) and turns every rule into a
rule in an NCM compliance policy report, delivered to the server through the SWIS
verbs on ``Cirrus.PolicyReports``. An SCM compliance policy ``.yaml`` instead imports
verbatim through ``Orion.PolicyEngine.Policy.ImportPolicy``.

    Open the GUI (also what a double-click on Windows does):
        python disa_stig_tool.py

    Build a Windows .exe of it:
        pip install pyinstaller
        pyinstaller --onefile --windowed --name DISASTIGConversionTool disa_stig_tool.py

    Download a package from DISA's public mirror:
        python disa_stig_tool.py download U_Cisco_IOS_Router_Y26M07_STIG

    See what a package contains before touching a server:
        python disa_stig_tool.py parse U_Cisco_IOS_Router_Y26M07_STIG.zip

    Write console-importable files without a server (NCM .ncm-report.xml,
    SCM .scm-policy.yaml):
        python disa_stig_tool.py convert U_Cisco_IOS_Router_Y26M07_STIG.zip

    Import into NCM and start compliance caching for the new report:
        python disa_stig_tool.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \\
            --host orion.example.com --user admin

    Undo an import (preview first with --dry-run):
        python disa_stig_tool.py remove --name "<report name>" \\
            --host orion.example.com --user admin --yes

The password is read from the SWIS_PASSWORD environment variable, or prompted for.
Never hard-code it and never pass it on the command line.

Every run writes a log file, one line per decision and per SWIS call, with secrets
redacted; its path is printed when the run starts and ends. --log-file PATH and
--log-level debug|info|warn (on every command, and after "gui") change it. See the
"Run log" section of README.md.

What the import produces
------------------------

One policy report per XCCDF benchmark in the package (the Cisco IOS Router package,
for example, carries two: NDM and RTR), each holding one policy, and one NCM rule per
XCCDF rule. Severity maps high to ErrorLevel 2, medium to 1 and low to 0; the console
names those levels critical, warning and info by default, but the names are editable
per server. The STIG's Fix Text is stored as the rule's remediation script for an
operator to review and run; ``ExecuteScriptAutomatically`` is always false, so this
tool never creates a rule that pushes configuration on its own.

Manual STIGs describe checks in prose, not machine patterns, so by default every
imported rule uses a sentinel pattern that cannot occur in a device configuration
with "pattern must exist" set. The result: every rule reports a violation on every
node in scope, which is the honest state: each finding is an open action item
carrying the full check text and the fix script, until an engineer replaces the
sentinel with a real pattern for that rule in the NCM console. ``--mode heuristic``
instead seeds each rule with the first config-looking line found in the STIG's check
content (marking the rest for review); treat those patterns as drafts, not audits.

Endpoint facts (SWIS REST on port 17774, platform 2023.1+) and the compliance verb
contract are documented in docs/modules/ncm-compliance-reports.md of this repository
and verified against 2026.2.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import io
import json
import logging
import os
import platform
import queue
import re
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import xml.parsers.expat
import zipfile

# One version for the tool, shared by both editions (disa_stig_tool.ps1 carries the
# same number). It is written into every log file's start-of-run line.
TOOL_VERSION = "2.0.0"
USER_AGENT = f"disa-stig-conversion-tool/{TOOL_VERSION}"

DEFAULT_PORT = 17774
BASE_PATH = "/SolarWinds/InformationService/v3/Json"

# DISA's public download mirror. The listing page is public.cyber.mil/stigs/downloads/
# and every package on it resolves to this WordPress upload path.
DISA_ZIP_BASE = "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/"

XCCDF_NS = "{http://checklists.nist.gov/xccdf/1.1}"

# XCCDF severity -> NCM ErrorLevel. The console's default names for 2/1/0 are
# critical/warning/info, but an administrator can rename the levels per server
# (Manage Violation Levels), so only the numbers are portable.
SEVERITY_TO_ERRORLEVEL = {"high": 2, "medium": 1, "low": 0}

# SCM compliance policy output. SolarWinds' own published policy files are plain
# .yaml; the docs name no dedicated extension, so this tool writes .scm-policy.yaml.
# .scm-profile is the extension of SCM *collection profile* exports (UTF-16 JSON,
# docs/modules/scm-profile-portability-audit.md), which older builds of this tool
# also used for policy YAML. That legacy output is still accepted on input.
SCM_POLICY_SUFFIX = ".scm-policy.yaml"
LEGACY_SCM_POLICY_SUFFIX = ".scm-profile"
SCM_INPUT_SUFFIXES = (".yaml", ".yml", LEGACY_SCM_POLICY_SUFFIX)
# NCM reads a `Like` pattern literally unless the advanced setting
# ComplianceRulesWildcardsEnabled is turned on, which it is not by default
# (NCM 2023.1.1 and later). A pattern carrying * or ? therefore means one thing
# on a stock server and another on a tuned one, so rules that would be
# ambiguous are emitted as an escaped Regex instead of a Like.
WILDCARD_CHARS = "*?"
# Escaped explicitly rather than with re.escape, because the PowerShell edition
# has to produce the same bytes and neither re.escape nor [regex]::Escape emits
# the same set. These are the metacharacters of the .NET engine NCM evaluates
# regular expressions with.
REGEX_METACHARACTERS = "\\^$.|?*+()[]{}"


def escape_regex(text):
    """Turn a literal config line into a regex that matches exactly itself."""
    return "".join(("\\" + ch) if ch in REGEX_METACHARACTERS else ch for ch in text)


# Config lines in IOS/NX-OS/JunOS check text tend to open with one of these tokens.
# Used only by --mode heuristic to seed a draft pattern.
CONFIG_TOKENS = (
    "aaa ", "ip ", "ipv6 ", "line ", "snmp-server ", "ntp ", "logging ", "login ",
    "banner ", "crypto ", "interface ", "router ", "access-list ", "username ",
    "service ", "no ", "hostname ", "enable ", "archive", "clock ", "boot ",
)


class SwisError(RuntimeError):
    """A SWIS request failed. Carries the server's message where one was returned."""


# Credentials live in memory only: never written to disk, never placed in URLs,
# and always redacted from anything the tool prints or logs.
_SECRETS = []


def register_secret(value):
    if value:
        _SECRETS.append(value)


def redact(text):
    for secret in _SECRETS:
        text = text.replace(secret, "••••••")
    return text


# ---------------------------------------------------------------------------
# Run log: one line per event, the same format in both editions
# ---------------------------------------------------------------------------
#
#   2026-10-09T14:03:07.123Z INFO  swis   Cirrus.PolicyReports.AddPolicyRule(...) -> ok 41 ms
#
# <UTC ISO-8601 with milliseconds>Z, the level padded to 5, the component padded to
# 6, then the message on one line (line breaks are written as a literal \n). Every
# line goes through redact(), so a registered secret never reaches the file. The
# console output is unchanged; the file is additive. disa_stig_tool.ps1 writes the
# identical format through Write-ToolLog.

LOG_COMPONENTS = ("main", "parse", "route", "scope", "build", "swis", "import", "verify",
                  "rollbk", "remove", "scm", "file", "gui")
LOG_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING,
              "error": logging.ERROR}
LOG_BODY_LIMIT = 4096   # debug-level request/response bodies are cut to this many chars

_LOG = logging.getLogger("disa_stig_tool")
_LOG.propagate = False
_LOG.addHandler(logging.NullHandler())   # no stderr fallback when no file is set up
_LOG.setLevel(logging.INFO)
_LOG_LOCK = threading.Lock()
_LOG_STATE = {"path": None, "handler": None, "stream": None, "started": None,
              "stats": {}}
_STAT_KEYS = ("swis_calls", "swis_failed", "files_written", "imported", "warnings", "errors")


def _reset_stats():
    _LOG_STATE["stats"] = {key: 0 for key in _STAT_KEYS}


_reset_stats()


def _bump(key, n=1):
    with _LOG_LOCK:
        _LOG_STATE["stats"][key] = _LOG_STATE["stats"].get(key, 0) + n


def format_log_line(created, level, component, message):
    """One log line. ``created`` is a POSIX timestamp, ``level`` one of LOG_LEVELS."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(created))
    millis = int((created % 1) * 1000)
    text = redact(str(message)).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    return f"{stamp}.{millis:03d}Z {level.upper():<5} {component:<6} {text}"


class _RedactFilter(logging.Filter):
    """Pass every record through the secret redaction before it is formatted."""

    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class _LineFormatter(logging.Formatter):
    _NAMES = {logging.DEBUG: "debug", logging.INFO: "info", logging.WARNING: "warn",
              logging.ERROR: "error", logging.CRITICAL: "error"}

    def format(self, record):
        return format_log_line(record.created, self._NAMES.get(record.levelno, "info"),
                               getattr(record, "component", "main"), record.getMessage())


def default_log_path(now=None, env=None, platform_name=None, home=None):
    """Where the run log goes when --log-file is not given.

    Windows: %LOCALAPPDATA%\\DisaStigTool\\logs\\disa-stig-tool_<yyyyMMdd-HHmmss>.log;
    elsewhere ~/.local/state/disa-stig-tool/logs/ (or $XDG_STATE_HOME when set). The
    time stamp in the name is UTC, like the lines inside.
    """
    env = os.environ if env is None else env
    platform_name = sys.platform if platform_name is None else platform_name
    home = home or os.path.expanduser("~")
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(time.time() if now is None else now))
    name = f"disa-stig-tool_{stamp}.log"
    if platform_name.startswith("win"):
        base = env.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return os.path.join(base, "DisaStigTool", "logs", name)
    base = env.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
    return os.path.join(base, "disa-stig-tool", "logs", name)


def close_logging():
    """Detach and close the log file, if one is open."""
    handler, stream = _LOG_STATE["handler"], _LOG_STATE["stream"]
    if handler is not None:
        _LOG.removeHandler(handler)
        handler.close()
    if stream is not None:
        stream.close()
    _LOG_STATE.update(path=None, handler=None, stream=None)


def setup_logging(path=None, level="info"):
    """Open the run log once per run and return its absolute path.

    An explicit ``path`` that cannot be opened is an error. When the default
    location cannot be created, the log falls back to the temp directory rather
    than stopping the run.
    """
    close_logging()
    if level not in LOG_LEVELS:
        raise ValueError(f"unknown log level {level!r}; use debug, info or warn")
    candidates = [path] if path else [
        default_log_path(),
        os.path.join(tempfile.gettempdir(), "disa-stig-tool", "logs",
                     os.path.basename(default_log_path()))]
    stream, error = None, None
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        try:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
            stream = open(candidate, "a", encoding="utf-8", newline="\n")
            break
        except OSError as exc:
            error = exc
    if stream is None:
        raise OSError(f"cannot open the log file: {error}")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_LineFormatter())
    handler.addFilter(_RedactFilter())
    handler.setLevel(LOG_LEVELS[level])
    _LOG.setLevel(LOG_LEVELS[level])
    _LOG.addHandler(handler)
    _reset_stats()
    _LOG_STATE.update(path=candidate, handler=handler, stream=stream, started=time.time())
    return candidate


def log_path():
    """The open log file's path, or None."""
    return _LOG_STATE["path"]


def log_debug_enabled():
    return _LOG_STATE["handler"] is not None and _LOG.isEnabledFor(logging.DEBUG)


def log_event(component, message, level="info"):
    """Write one event to the run log (a no-op until setup_logging has run).

    ``component`` is one of LOG_COMPONENTS; ``level`` is debug, info, warn or error.
    """
    if level == "warn":
        _bump("warnings")
    elif level == "error":
        _bump("errors")
    if component not in LOG_COMPONENTS:
        component = "main"
    _LOG.log(LOG_LEVELS.get(level, logging.INFO), "%s", message,
             extra={"component": component})


def _say(log, component, message, level="info"):
    """Send a message to the caller's console callback and to the run log."""
    if log:
        log(message)
    log_event(component, message, level)


def truncate_body(text, limit=LOG_BODY_LIMIT):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated, {len(text)} chars]"


def _format_command_line(argv):
    def quote(arg):
        return f'"{arg}"' if (not arg or any(ch in arg for ch in ' \t"')) else arg
    return " ".join(quote(a) for a in [os.path.basename(sys.argv[0] or "disa_stig_tool.py")]
                    + list(argv))


def log_run_start(argv, mode="cli"):
    """Start-of-run lines: tool version, interpreter, OS, the command line, the log file."""
    log_event("main", f"DISA STIG Conversion Tool {TOOL_VERSION} (Python edition), {mode} run")
    log_event("main", f"interpreter: Python {platform.python_version()} "
                      f"({platform.python_implementation()}) {sys.executable}")
    log_event("main", f"os: {platform.platform()}")
    log_event("main", f"command line: {_format_command_line(argv)}")
    log_event("main", f"log file: {log_path()} (level "
                      f"{logging.getLevelName(_LOG.level).lower().replace('warning', 'warn')})")


def log_run_end(exit_code):
    """End-of-run summary with counts and the exit code."""
    s = _LOG_STATE["stats"]
    started = _LOG_STATE["started"] or time.time()
    log_event("main", (
        f"run end: exit code {exit_code}; {s['swis_calls']} SWIS call(s), {s['swis_failed']} "
        f"failed; {s['files_written']} file(s) written; {s['imported']} import(s) verified; "
        f"{s['warnings']} warning(s), {s['errors']} error(s); "
        f"{time.time() - started:.1f} s"))


def fetch_server_cert(host, port=DEFAULT_PORT):
    """Fetch the certificate SWIS presents, for explicit trust (pinning).

    Returns (pem, sha256_fingerprint, looks_like_stock) where looks_like_stock
    is True when the certificate carries the stock 'SolarWinds-Orion' name.
    The fetch itself does not verify — that is the point: the operator inspects
    the fingerprint once, and every later connection verifies against exactly
    this certificate.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=30) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(True)
    fingerprint = hashlib.sha256(der).hexdigest().upper()
    fingerprint = ":".join(fingerprint[i:i + 2] for i in range(0, len(fingerprint), 2))
    return ssl.DER_cert_to_PEM_cert(der), fingerprint, b"SolarWinds-Orion" in der


class SwisClient:
    """Minimal SWIS REST client — the same contract scripts/python/swis_client.py shows."""

    def __init__(self, host, username, password, port=DEFAULT_PORT, verify=True, ca_file=None,
                 pinned_pem=None):
        self.base = f"https://{host}:{port}{BASE_PATH}"
        self.username = username
        self.password = password
        register_secret(password)
        # The Basic token carries the password too, so it is redacted as well.
        register_secret(base64.b64encode(f"{username}:{password}".encode()).decode())
        tls = ("pinned server certificate" if pinned_pem else
               f"verified against {ca_file}" if verify and ca_file else
               "verified against the system trust store" if verify else
               "NOT verified (--insecure, lab only)")
        log_event("swis", f"SWIS endpoint https://{host}:{port}{BASE_PATH} as user "
                          f"'{username}' (basic auth); TLS {tls}")
        if not verify and not pinned_pem:
            log_event("swis", "TLS verification is off for this session", "warn")
        if pinned_pem:
            # Trust exactly the fetched SolarWinds-Orion certificate. The stock
            # certificate's CN is 'SolarWinds-Orion', not the host name, so the
            # hostname check is off — the chain check against the pinned
            # certificate is what authenticates the server.
            self.ctx = ssl.create_default_context(cadata=pinned_pem)
            self.ctx.check_hostname = False
        elif verify:
            self.ctx = ssl.create_default_context(cafile=ca_file)
        else:
            # Only for a lab. Accepts any certificate.
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def _request(self, method, path, body=None):
        url = f"{self.base}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=300) as resp:
                payload = resp.read().decode("utf-8", "replace")
                return json.loads(payload) if payload.strip() else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("Message", detail)
            except (ValueError, AttributeError):
                pass
            raise SwisError(f"HTTP {exc.code} from {url}\n{detail}") from exc
        except urllib.error.URLError as exc:
            raise SwisError(f"could not reach {url}: {exc.reason}") from exc

    def query(self, swql, parameters=None):
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        return (self._request("POST", "Query", body) or {}).get("results", [])

    def invoke(self, entity, verb, *args):
        return self._request("POST", f"Invoke/{entity}/{verb}", list(args))


def _summarize_value(value, width=60):
    """A short, log-safe description of one SWIS argument or result."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if len(value) <= width and "\n" not in value and "\r" not in value:
            return f'"{value}"'
        return f"<string {len(value)} chars>"
    if isinstance(value, dict):
        for key in ("RuleName", "PolicyName", "Name"):
            if value.get(key):
                return f"<object {str(value[key])[:width]}>"
        return f"<object {len(value)} keys>"
    if isinstance(value, (list, tuple)):
        return f"[{len(value)} item(s)]"
    return f"<{type(value).__name__}>"


def _one_line(text, width):
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[:width] + "..."


class LoggedSwis:
    """Wraps any client with the query()/invoke() surface (SwisClient,
    WindowsAuthClient, or a test double) and writes one log line per SWIS call:
    entity.verb or the query, a short argument summary, the duration in ms, and ok
    or the error message. At debug level the redacted request and response bodies
    follow, cut to LOG_BODY_LIMIT characters."""

    def __init__(self, inner):
        self.inner = inner

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def query(self, swql, parameters=None):
        label = "query " + _one_line(swql, 160)
        if parameters:
            label += " params {" + ", ".join(f"{k}={_summarize_value(v)}"
                                             for k, v in parameters.items()) + "}"
        body = {"query": swql, "parameters": parameters} if parameters else {"query": swql}
        return self._call(label, body, lambda: self.inner.query(swql, parameters))

    def invoke(self, entity, verb, *args):
        label = f"{entity}.{verb}(" + ", ".join(_summarize_value(a) for a in args) + ")"
        return self._call(label, list(args), lambda: self.inner.invoke(entity, verb, *args))

    def _call(self, label, body, fn):
        _bump("swis_calls")
        if log_debug_enabled():
            log_event("swis", "request " + label + " body "
                      + truncate_body(json.dumps(body, default=str, ensure_ascii=False)), "debug")
        start = time.perf_counter()
        try:
            result = fn()
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            _bump("swis_failed")
            log_event("swis", f"{label} -> error {elapsed} ms: {exc}", "warn")
            raise
        elapsed = int((time.perf_counter() - start) * 1000)
        outcome = (f"{len(result)} row(s)" if label.startswith("query ") and isinstance(result, list)
                   else _summarize_value(result))
        log_event("swis", f"{label} -> ok {elapsed} ms, {outcome}")
        if log_debug_enabled():
            log_event("swis", "response " + label + " body "
                      + truncate_body(json.dumps(result, default=str, ensure_ascii=False)), "debug")
        return result


def logged(client):
    """Wrap a SWIS client for call logging (idempotent)."""
    return client if client is None or isinstance(client, LoggedSwis) else LoggedSwis(client)


# ---------------------------------------------------------------------------
# Safe output: generated file names and PowerShell probe literals
# ---------------------------------------------------------------------------

MAX_FILE_NAME = 200
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} \
    | {f"LPT{i}" for i in range(1, 10)}


def safe_file_name(stem, suffix=""):
    """The one place every generated file name goes through, in both editions.

    Keeps [A-Za-z0-9._-], collapses every other run of characters to a single
    underscore, strips leading dots, and caps the whole name (suffix included) at
    MAX_FILE_NAME characters, so a STIG title can neither climb out of the output
    folder ("../../x") nor exceed the 255-character file name limit.
    """
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", stem or "").lstrip(".")
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        name = "_" + name
    name = name[:max(1, MAX_FILE_NAME - len(suffix))] or "unnamed"
    return name + suffix


# SCM probes run as PowerShell on every assigned node, so nothing from the STIG
# may reach script source unquoted. Ids are validated, and the probe text is a
# single-quoted PowerShell literal, in which only the quote characters are
# special. PowerShell also treats U+2018-U+201B as single quotes.
VULN_ID_PATTERN = re.compile(r"^V-[0-9]+\Z")
RULE_ID_PATTERN = re.compile(r"^SV-[0-9]+r[0-9]+_rule\Z")
_PS_SINGLE_QUOTES = "'‘’‚‛"


def ps_single_quote(text):
    """A PowerShell single-quoted string literal holding ``text`` verbatim."""
    return "'" + "".join(ch + ch if ch in _PS_SINGLE_QUOTES else ch for ch in str(text)) + "'"


def scm_probe_id(vuln_id, rule_id=""):
    """The vuln id as it may appear in an SCM probe, validated.

    A DISA id is V-<digits> (rule ids SV-<digits>r<digits>_rule), after any SCAP
    xccdf_ prefix is stripped. Anything else is reduced to [A-Za-z0-9._-] with a
    warning in the log, so the probe and its expression stay predictable.
    """
    vid = _strip_scap_prefix(vuln_id)
    rid = _strip_scap_prefix(rule_id)
    if rid and not RULE_ID_PATTERN.match(rid):
        log_event("scm", f"rule id {rid!r} does not match SV-<n>r<n>_rule; it is used only "
                         "in ids and comments, never in probe source", "warn")
    if VULN_ID_PATTERN.match(vid):
        return vid
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", vid) or "V-unknown"
    log_event("scm", f"vuln id {vid!r} does not match V-<n>; the SCM probe uses the "
                     f"sanitized id {safe!r}", "warn")
    return safe


# ---------------------------------------------------------------------------
# SCM policy YAML (Server Configuration Monitor / PolicyEngine)
# ---------------------------------------------------------------------------
#
# SCM compliance policies are YAML documents tagged `!policy` with
# `pluginName: SCM`. The SWIS import verb takes the document text verbatim —
# Orion.PolicyEngine.Policy.ImportPolicy(yaml) returns the new PolicyID — so no
# YAML parsing is needed to import; the light regex scan below is only for
# previews and sanity checks.

def is_scm_policy_text(text):
    head = text.lstrip()[:2000]
    return head.startswith("!policy") or ("pluginName: SCM" in head and "rules:" in text)


def scan_scm_policy(text):
    """Cheap preview of an SCM policy YAML: name, rule ids, severities."""
    name = ""
    m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    if m:
        name = m.group(1).strip().strip("'\"")
    unique_id = ""
    m = re.search(r"^uniqueId:\s*(\S+)", text, re.MULTILINE)
    if m:
        unique_id = m.group(1).strip().strip("'\"")
    rules = re.findall(r"^- displayId:\s*(\S+)", text, re.MULTILINE)
    severities = re.findall(r"^\s{2}severity:\s*(\S+)", text, re.MULTILINE)
    counts = {}
    for s in severities:
        counts[s] = counts.get(s, 0) + 1
    return {"name": name, "uniqueId": unique_id, "rules": rules,
            "severity_counts": counts}


def decode_text_bytes(raw):
    """Decode a policy or profile file by its bytes: UTF-16 (BOM or NUL-interleaved
    ASCII, as SCM exports are UTF-16LE) or UTF-8 with an optional BOM."""
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    head = raw[:64]
    if len(head) >= 4 and head[1:2] == b"\x00" and head[3:4] == b"\x00":
        return raw.decode("utf-16-le")
    if len(head) >= 4 and head[0:1] == b"\x00" and head[2:3] == b"\x00":
        return raw.decode("utf-16-be")
    return raw.decode("utf-8-sig")


def classify_scm_text(text):
    """'policy' (tagged-YAML compliance policy), 'profile' (JSON, the SCM
    collection-profile export format) or 'unknown'."""
    if is_scm_policy_text(text):
        return "policy"
    stripped = text.lstrip("﻿ \t\r\n")
    if stripped.startswith("{"):
        try:
            json.loads(stripped)
            return "profile"
        except ValueError:
            pass
    return "unknown"


SCM_PROFILE_REFUSAL = (
    "{path}: this is an SCM collection profile (JSON, the format SCM profile exports "
    "use), not a tagged-YAML compliance policy. Collection profiles define what SCM "
    "collects; they carry no compliance rules, and this tool does not import them. "
    "Import a profile through SCM's own profile import workflow or "
    "Orion.SCM.Profiles.ImportProfile(profileJson), after the review described in "
    "docs/modules/scm-profile-portability-audit.md.")


def load_scm_policy(path, log=None):
    """Read an SCM policy YAML file, tolerating a UTF-8/UTF-16 BOM.

    ``.scm-profile`` input is classified by content: policy YAML that an older
    build of this tool wrote under that extension is accepted with a note (sent
    to ``log``); a JSON collection profile is refused, because that extension
    belongs to SCM collection profiles and they are not compliance policies.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    text = decode_text_bytes(raw)
    kind = classify_scm_text(text)
    if kind == "profile":
        log_event("scm", f"refused {path}: JSON SCM collection profile, not a policy", "warn")
        raise ValueError(SCM_PROFILE_REFUSAL.format(path=path))
    if kind != "policy":
        log_event("scm", f"refused {path}: not a tagged-YAML SCM compliance policy", "warn")
        raise ValueError(f"{path}: not an SCM compliance policy "
                         "(expected a YAML document tagged !policy with pluginName: SCM)")
    log_event("scm", f"read SCM policy file {path} ({len(raw)} bytes)")
    if path.lower().endswith(LEGACY_SCM_POLICY_SUFFIX):
        msg = (f"note: {os.path.basename(path)} is SCM policy YAML written by an older build "
               f"of this tool under the {LEGACY_SCM_POLICY_SUFFIX} extension, which belongs "
               "to SCM collection profiles (JSON). It is read as a compliance policy; new "
               f"conversions write {SCM_POLICY_SUFFIX}, so rename the file to avoid confusion.")
        _say(log, "scm", msg, "warn")
    return text


def import_scm_policy(swis, text, log=None):
    """Import one SCM policy via Orion.PolicyEngine.Policy.ImportPolicy.

    Returns (policy_id, name). Refuses to import when a policy with the same
    name **or the same uniqueId** already exists — this tool never overwrites or
    duplicates, and SolarWinds rejects both collisions server side. Checking the
    uniqueId matters here because the tool derives it deterministically from the
    benchmark, so re-importing a STIG under a new --name still collides, and the
    server-side rejection is far less legible than this one.

    The import is verified by reading the rules back: ImportPolicy returning an
    id is not by itself evidence that the rules landed.
    """
    info = scan_scm_policy(text)
    log_event("scm", f"SCM policy \"{info['name']}\" uniqueId {info['uniqueId'] or '(none)'}, "
                     f"{len(info['rules'])} rule(s); checking for a name/uniqueId collision")
    clauses, params = [], {}
    if info["name"]:
        clauses.append("Name = @n")
        params["n"] = info["name"]
    if info["uniqueId"]:
        clauses.append("UniqueId = @u")
        params["u"] = info["uniqueId"]
    if clauses:
        existing = swis.query(
            "SELECT PolicyID, Name, UniqueId, BuiltIn FROM Orion.PolicyEngine.Policy "
            "WHERE " + " OR ".join(clauses), params)
        if existing:
            hit = existing[0]
            why = ("the same name" if (hit.get("Name") or "") == info["name"]
                   else "the same uniqueId")
            msg = (f"a policy with {why} already exists: \"{hit.get('Name')}\" "
                   f"(PolicyID {hit.get('PolicyID')}, UniqueId {hit.get('UniqueId')}); "
                   "refusing to duplicate. SolarWinds rejects an import that matches "
                   "either field.")
            log_event("scm", msg, "error")
            raise SwisError(msg)
    policy_id = swis.invoke("Orion.PolicyEngine.Policy", "ImportPolicy", text)
    if policy_id is None:
        log_event("scm", "ImportPolicy returned no PolicyID; the policy was not created", "error")
        raise SwisError("No data returned from Orion.PolicyEngine.Policy.ImportPolicy — "
                        "the policy was not created")
    log_event("scm", f"ImportPolicy returned PolicyID {policy_id}; reading the rules back")
    stored = swis.query("SELECT COUNT(RuleID) AS N FROM Orion.PolicyEngine.Rule "
                        "WHERE PolicyID = @p", {"p": policy_id})
    n_stored = (stored[0].get("N") if stored else 0) or 0
    if not n_stored:
        msg = (f"No data returned reading rules back for PolicyID {policy_id} — the "
               "policy row exists but holds no rules, so the import cannot be confirmed. "
               "Check the account's rights on Orion.PolicyEngine.Policy.")
        log_event("verify", msg, "error")
        raise SwisError(msg)
    _say(log, "verify", f"verified: PolicyID {policy_id} holds {n_stored} rule(s)")
    _bump("imported")
    return policy_id, info["name"]


# ---------------------------------------------------------------------------
# XCCDF parsing
# ---------------------------------------------------------------------------

def strip_html(text):
    """XCCDF descriptions embed pseudo-XML tags (VulnDiscussion, …) as escaped text."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def extract_tag(description, tag):
    """Pull one pseudo-tag's body out of an XCCDF <description> blob."""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", description or "", re.DOTALL)
    return m.group(1).strip() if m else ""


# DISA publishes two editions. Manual STIGs are bare XCCDF 1.1 benchmarks with prose
# check text. SCAP Benchmark editions (the xml-only zips, for automated scanners) are
# SCAP 1.3 data-streams: a <data-stream-collection> root embedding an XCCDF **1.2**
# benchmark whose ids are prefixed (xccdf_mil.disa.stig_group_V-…) and whose checks
# are OVAL references instead of prose.
XCCDF_12_NS = "{http://checklists.nist.gov/xccdf/1.2}"
_SCAP_ID_PREFIX = re.compile(r"^xccdf_[^_]+(?:\.[^_]+)*_(?:group|rule|benchmark)_")


def _strip_scap_prefix(value):
    return _SCAP_ID_PREFIX.sub("", value or "")


class _PrologDone(Exception):
    """Raised by the prolog scan once the root element starts."""


DTD_REFUSAL = ("refused: the document declares a DTD (<!DOCTYPE>); DTDs and entity "
               "declarations are never processed, so external entities cannot be resolved")


def refuse_dtd(xml_bytes, source_name):
    """Refuse any document that declares a DTD, before it is parsed for content.

    XCCDF does not use DTDs, and refusing them outright closes the external-entity
    (XXE) and entity-expansion classes in both editions alike: the PowerShell edition
    loads XML with DtdProcessing=Prohibit. Only the prolog is scanned (the scan
    stops at the root element), and expat honours the declared encoding and BOM.
    """
    scanner = xml.parsers.expat.ParserCreate()

    def doctype(*_args):
        raise ValueError(f"{source_name}: {DTD_REFUSAL}")

    def start(*_args):
        raise _PrologDone()

    scanner.StartDoctypeDeclHandler = doctype
    scanner.StartElementHandler = start
    try:
        scanner.Parse(xml_bytes, True)
    except _PrologDone:
        pass
    except xml.parsers.expat.ExpatError:
        pass    # not well-formed: the content parse below reports it


def parse_benchmarks(xml_bytes, source_name):
    """Parse an XCCDF file (manual or SCAP data-stream) into a list of benchmark dicts."""
    refuse_dtd(xml_bytes, source_name)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"{source_name}: not well-formed XML ({exc})") from exc
    found = []
    for ns in (XCCDF_NS, XCCDF_12_NS):
        if root.tag == f"{ns}Benchmark":
            found.append((root, ns))
        else:
            found.extend((b, ns) for b in root.iter(f"{ns}Benchmark"))
    if not found:
        raise ValueError(f"{source_name}: no XCCDF Benchmark element found "
                         f"(root is {root.tag})")
    return [_parse_one_benchmark(b, ns, source_name) for b, ns in found]


def parse_benchmark(xml_bytes, source_name):
    """Back-compatible single-benchmark parse (first benchmark in the file)."""
    return parse_benchmarks(xml_bytes, source_name)[0]


def _parse_one_benchmark(root, ns, source_name):
    def text(elem, name):
        child = elem.find(f"{ns}{name}")
        return (child.text or "").strip() if child is not None else ""

    release = ""
    for pt in root.findall(f"{ns}plain-text"):
        if pt.get("id") == "release-info":
            release = (pt.text or "").strip()

    status = root.find(f"{ns}status")
    status_date = status.get("date", "") if status is not None else ""

    rules = []
    for group in root.iter(f"{ns}Group"):
        rule = group.find(f"{ns}Rule")
        if rule is None:
            continue
        description = rule.findtext(f"{ns}description", default="")
        check = rule.find(f"{ns}check")
        check_content, oval_ref = "", ""
        if check is not None:
            check_content = check.findtext(f"{ns}check-content", default="").strip()
            ref = check.find(f"{ns}check-content-ref")
            if ref is not None and (ref.get("name") or "").startswith("oval:"):
                oval_ref = ref.get("name")
        rules.append({
            "vuln_id": _strip_scap_prefix(group.get("id", "")),   # V-215662
            "rule_id": _strip_scap_prefix(rule.get("id", "")),    # SV-215662r…_rule
            "stig_id": text(rule, "version"),                     # CISC-ND-000010
            "severity": rule.get("severity", "medium").lower(),
            "title": text(rule, "title"),
            "discussion": extract_tag(description, "VulnDiscussion"),
            "check_content": check_content,
            "oval_ref": oval_ref,
            "fix_text": rule.findtext(f"{ns}fixtext", default="").strip(),
            "ccis": [i.text for i in rule.findall(f"{ns}ident")
                     if i.text and (i.get("system") or "").endswith("/cci")],
        })

    benchmark = {
        "source": source_name,
        "benchmark_id": _strip_scap_prefix(root.get("id", "")),
        "title": root.findtext(f"{ns}title", default="").strip(),
        "version": root.findtext(f"{ns}version", default="").strip(),
        "release": release,
        "status_date": status_date,
        "edition": "scap" if ns == XCCDF_12_NS else "manual",
        "rules": rules,
    }
    log_event("parse", f"benchmark {benchmark['benchmark_id'] or '(no id)'} "
                       f"\"{benchmark['title']}\" V{benchmark['version']} "
                       f"({benchmark['release'] or 'no release info'}), "
                       f"{benchmark['edition']} edition, {len(rules)} rule(s), from {source_name}")
    return benchmark


def _try_parse_xml(xml_bytes, name):
    """Parse benchmarks from bytes, returning [] when the XML is not one.

    Zip discovery goes by content, not filename: DISA's naming varies
    ("*-xccdf.xml", "*Manualxccdf.xml", "*_Benchmark.xml"), and the stylesheet
    or a stray XML must simply be skipped rather than fail the whole zip. Every
    skip is logged with its reason.
    """
    head = xml_bytes[:200]
    if b"<?xml" not in head and b"<" not in head:
        log_event("parse", f"skipped {name}: does not look like XML")
        return []
    try:
        found = parse_benchmarks(xml_bytes, name)
    except ValueError as exc:
        reason = str(exc)
        if reason.startswith(f"{name}: "):
            reason = reason[len(name) + 2:]
        level = "info" if reason.startswith("no XCCDF Benchmark") else "warn"
        log_event("parse", f"skipped {name}: {reason}", level)
        return []
    log_event("parse", f"parsed {name}: {len(found)} benchmark(s)")
    return found


def _dedupe_benchmarks(benchmarks):
    """When both editions of the same benchmark are present, keep the manual one.

    Verified against real files: where both editions carry the same check, the
    fix text is identical, and only the manual edition has the check prose —
    importing both would only duplicate rules.
    """
    by_id = {}
    for b in benchmarks:
        key = b["benchmark_id"] or b["title"]
        held = by_id.get(key)
        if held is None:
            by_id[key] = b
        elif held["edition"] == "scap" and b["edition"] == "manual":
            log_event("parse", f"dedupe {key}: kept the manual edition from {b['source']}, "
                               f"dropped the SCAP edition from {held['source']}")
            by_id[key] = b
        else:
            log_event("parse", f"dedupe {key}: kept the {held['edition']} edition from "
                               f"{held['source']}, dropped the {b['edition']} edition from "
                               f"{b['source']}")
    return list(by_id.values())


def load_benchmarks(path):
    """Load every XCCDF benchmark from a STIG zip, a bare XML file, or a directory.

    Handles all three zip shapes DISA publishes: xsl+xml (manual), xml-only
    (SCAP data-stream), and compilation zips nesting one zip per STIG.
    """
    benchmarks = []

    def skip(name, why):
        log_event("parse", f"skipped {name}: {why}")

    if os.path.isdir(path):
        log_event("parse", f"input {path}: directory")
        for dirpath, _dirs, files in os.walk(path):
            for name in sorted(files):
                if name.lower().endswith(".xml"):
                    with open(os.path.join(dirpath, name), "rb") as fh:
                        benchmarks.extend(_try_parse_xml(fh.read(), name))
                else:
                    skip(name, "not an .xml file")
    elif zipfile.is_zipfile(path):
        log_event("parse", f"input {path}: zip ({os.path.getsize(path)} bytes)")
        with zipfile.ZipFile(path) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                base = os.path.basename(info.filename)
                if info.is_dir():
                    continue
                if base.lower().endswith(".xml"):
                    benchmarks.extend(_try_parse_xml(zf.read(info), base))
                elif base.lower().endswith(".zip"):
                    # Compilation zips (SRG-STIG Library) nest one zip per STIG.
                    log_event("parse", f"nested zip {info.filename}: reading its members")
                    inner = io.BytesIO(zf.read(info))
                    with zipfile.ZipFile(inner) as izf:
                        for iinfo in sorted(izf.infolist(), key=lambda i: i.filename):
                            ibase = os.path.basename(iinfo.filename)
                            if iinfo.is_dir():
                                continue
                            if ibase.lower().endswith(".xml"):
                                benchmarks.extend(_try_parse_xml(izf.read(iinfo), ibase))
                            else:
                                skip(f"{info.filename}/{iinfo.filename}", "not an .xml member")
                else:
                    skip(info.filename, "not an .xml or .zip member (stylesheet, document "
                                        "or other content)")
    elif path.lower().endswith(".xml"):
        log_event("parse", f"input {path}: XML file")
        with open(path, "rb") as fh:
            try:
                benchmarks.extend(parse_benchmarks(fh.read(), os.path.basename(path)))
            except ValueError as exc:
                log_event("parse", f"refused {path}: {exc}", "warn")
                raise
    elif path.lower().endswith(".xsl"):
        # The .xsl is only the display stylesheet; the data lives in the
        # benchmark XML sitting next to it. Resolve that silently.
        folder = os.path.dirname(os.path.abspath(path))
        log_event("parse", f"input {path}: stylesheet; reading the XML files next to it in "
                           f"{folder}")
        for n in sorted(os.listdir(folder)):
            if n.lower().endswith(".xml"):
                with open(os.path.join(folder, n), "rb") as fh:
                    benchmarks.extend(_try_parse_xml(fh.read(), n))
        if not benchmarks:
            raise ValueError(f"{path}: this is the STIG stylesheet, not the data, and no "
                             "XCCDF benchmark XML was found next to it")
    else:
        log_event("parse", f"refused {path}: not a zip, directory, or XCCDF .xml file", "warn")
        raise ValueError(f"{path}: not a zip, directory, or XCCDF .xml file")
    benchmarks = _dedupe_benchmarks(benchmarks)
    if not benchmarks:
        log_event("parse", f"{path}: no XCCDF benchmark found inside", "warn")
        raise ValueError(f"{path}: no XCCDF benchmark found inside")
    log_event("parse", f"{path}: {len(benchmarks)} benchmark(s) after dedupe")
    return benchmarks


# ---------------------------------------------------------------------------
# NCM payload building
# ---------------------------------------------------------------------------

def heuristic_pattern(check_content):
    """First line of check text that looks like a device configuration command."""
    for line in (check_content or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.endswith((":", "?", ".")):
            continue
        lowered = stripped.lower()
        if any(lowered.startswith(tok) for tok in CONFIG_TOKENS):
            return stripped
    return None


def rule_object(rule, grouping, mode):
    """One XCCDF rule → one Cirrus.PolicyReports rule contract object.

    Field names follow the SolarWinds.NCM.Contracts.Compliance.PolicyRule contract
    (docs/modules/ncm-compliance-reports.md), not the SWQL column names.
    """
    sentinel = f"STIG-MANUAL-REVIEW-{rule['vuln_id']}"
    pattern_type = "Like"
    pattern, note = sentinel, (
        "PATTERN NOT SET: this sentinel never matches, so the rule flags every node "
        "as a violation until you replace it with a real pattern for this check."
    )
    if mode == "heuristic":
        found = heuristic_pattern(rule["check_content"])
        if found:
            pattern, note = found, (
                "DRAFT PATTERN extracted automatically from the STIG check text — "
                "verify it before trusting this rule's results."
            )
            if any(ch in found for ch in WILDCARD_CHARS):
                # A Like pattern treats * and ? as wildcards only when the server
                # has ComplianceRulesWildcardsEnabled turned on, which is off by
                # default from NCM 2023.1.1. Escaping the text into a Regex makes
                # the rule mean the same thing on either server.
                pattern_type = "Regex"
                pattern = escape_regex(found)
                note += (" Emitted as an escaped Regex rather than a Like pattern "
                         "because the extracted text contains * or ?, which a Like "
                         "pattern only treats as wildcards when the server's "
                         "ComplianceRulesWildcardsEnabled advanced setting is on "
                         "(NCM 2023.1.1 and later; off by default).")

    comments = "\n\n".join(part for part in (
        f"{rule['vuln_id']} / {rule['rule_id']} / STIG ID {rule['stig_id']}"
        + (f" / {', '.join(rule['ccis'])}" if rule["ccis"] else ""),
        note,
        "Discussion:\n" + rule["discussion"] if rule["discussion"] else "",
        "Check:\n" + rule["check_content"] if rule["check_content"] else "",
        ("Machine check (SCAP edition): OVAL definition " + rule["oval_ref"]
         + " — no manual check text in this edition; the manual STIG for this "
           "product carries the prose.") if rule.get("oval_ref") and not rule["check_content"] else "",
    ) if part)

    name = f"{rule['vuln_id']} [{rule['severity']}] {rule['title']}"
    return {
        "RuleId": str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm:" + rule["rule_id"])),  # historic namespace string; changing it would change every derived RuleId
        "RuleName": name[:250],
        "Comments": comments,
        "Grouping": grouping,
        "SimplePatternText": pattern,
        "PatternType": pattern_type,
        "PatternMustExist": True,
        "AdvancedMode": False,
        "MultiLineRulePatterns": [],
        "ConfigBlockStart": "",
        "ConfigBlockEnd": "",
        "ConfigBlockPatternType": "Like",
        "ConfigBlockMustExist": False,
        "IsConfigBlockPatternRegEx": False,
        "ErrorLevel": SEVERITY_TO_ERRORLEVEL.get(rule["severity"], 1),
        # Fix Text as an operator-run script. Never auto-executed: an imported
        # checklist must not be allowed to push configuration on its own.
        "RemediateScript": rule["fix_text"],
        "RemediateScriptType": "CLI",
        "ExecuteScriptAutomatically": False,
        "ExecuteRemediationScriptPerBlock": False,
        "ExecuteScriptInConfigMode": False,
        "Owner": "DISA STIG Conversion Tool",
    }


# SolarWinds documents one flat limit on the whole feature: a policy report
# cannot be run against a config that was downloaded in XML format. Palo Alto is
# the vendor that hits it by default, and the failure is silent - the rules
# import, cache, and then report nothing at all - so it is worth saying out loud
# before the import rather than after a day of empty results.
XML_CONFIG_VENDORS = ("palo alto", "paloalto", "panorama")


def xml_config_warning(node_where):
    """A warning string when the node scope selects devices whose configs are XML."""
    lowered = (node_where or "").lower()
    if not any(v in lowered for v in XML_CONFIG_VENDORS):
        return None
    log_event("scope", f"node scope {node_where} selects devices whose configs back up as "
                       "XML; NCM policy reports cannot evaluate XML configs", "warn")
    return ("warning: NCM policy reports cannot be run against configurations "
            "downloaded in XML format, which is how Palo Alto devices back up unless "
            "the config type is changed. The report will import and cache normally and "
            "then report no violations at all, which reads like compliance. Confirm "
            "those nodes have a text config of the selected type, or route this "
            "benchmark to SCM instead.")


def make_node_selection_string(node_where):
    """The NodeSelectionString in the format real console exports carry.

    Verified against exports from a live 2026.2.2 server: the literal prefix
    ``WebCriteria:``, an XML-escaped ArrayOfWebSelectionCriteria document (the
    console node-picker's state), then ``SQL:Where (…)`` — the part NCM
    actually filters on. Column names in the SQL fragment are bare (Vendor,
    not Nodes.Vendor).
    """
    where = re.sub(r"\bNodes\.", "", node_where or "").strip()
    if not where.lower().startswith("("):
        where = f"({where})"
    m = re.search(r"Vendor\s*(?:=|LIKE)\s*'%?([^%']+)%?'", where, re.IGNORECASE)
    criteria = ""
    if m:
        vendor = m.group(1)
        criteria = (
            '<?xml version="1.0" encoding="utf-16"?>\n'
            '<ArrayOfWebSelectionCriteria xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            "  <WebSelectionCriteria>\n"
            f"    <Id>{uuid.uuid5(uuid.NAMESPACE_URL, 'stig2ncm-criteria:' + vendor)}</Id>\n"
            "    <LogicalCondition />\n"
            "    <SelectedColumn>Vendor</SelectedColumn>\n"
            "    <MatchType>=</MatchType>\n"
            f"    <SelectedValue>{vendor}</SelectedValue>\n"
            "  </WebSelectionCriteria>\n"
            "</ArrayOfWebSelectionCriteria>")
    return f"WebCriteria:{criteria}SQL:Where {where} "


def build_reports(benchmarks, name=None, grouping="DISA STIG", node_where="(Vendor = 'Cisco')",
                  config_type="Any", mode="manual", source_path=None, enabled=True):
    """Assemble one PolicyReport contract object per benchmark.

    Matching how the console's own exports are structured (one policy per
    report): each benchmark in the package becomes its own report — the Cisco
    IOS Router package yields an NDM report (35 rules) and an RTR report
    (92 rules) — whose single policy carries the device scope and joins the
    report to its rules.
    """
    if name is None and source_path and source_path.lower().endswith(".zip"):
        name = os.path.splitext(os.path.basename(source_path))[0]
    reports = []
    for b in benchmarks:
        policy_group = f"{grouping}/{b['benchmark_id']}" if b["benchmark_id"] else grouping
        rules = [rule_object(r, policy_group, mode) for r in b["rules"]]
        policy = {
            "PolicyId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                       "stig2ncm-policy:" + (b["benchmark_id"] or b["title"]))),
            "PolicyName": f"{b['title']} V{b['version']} ({b['release']})"[:250],
            "Comments": f"Imported by the DISA STIG Conversion Tool from {b['source']} (benchmark {b['benchmark_id']}, "
                        f"status date {b['status_date']}).",
            "Grouping": grouping,
            "NodeSelectionString": make_node_selection_string(node_where),
            "ConfigTypes": config_type,
            "AssignedPolicyRules": rules,
            "AssignedRulesList": [r["RuleId"] for r in rules],
        }
        base = name or b["title"]
        report_name = f"{base} - {b['benchmark_id']}" if name and b["benchmark_id"] else base
        reports.append({
            "ID": str(uuid.uuid4()),  # advisory only — the server assigns its own GUID
            "Name": report_name[:250],
            "Comments": f"DISA STIG imported by the DISA STIG Conversion Tool from "
                        f"{b['source']} ({b['release']}).",
            "Group": grouping,
            "ShowSummaryFlag": True,
            "ShowRulesWithoutViolationFlag": True,
            "AssignedPolicies": [policy],
            "AssignedPoliciesList": [policy["PolicyId"]],
            # Disabled is worth having for a large STIG an engineer still has to
            # tune: the report exists and holds its rules, but evaluates nothing
            # until it is switched on.
            "ReportStatus": "Enabled" if enabled else "Disabled",
        })
        log_event("build", f"report \"{reports[-1]['Name']}\": policy \"{policy['PolicyName']}\" "
                           f"(PolicyId {policy['PolicyId']}), {len(rules)} rule(s), mode {mode}, "
                           f"ReportStatus {reports[-1]['ReportStatus']}, ConfigTypes "
                           f"{config_type}, grouping {policy_group}")
    return reports


def build_report(benchmarks, **kwargs):
    """Back-compatible single-report build (first benchmark only)."""
    return build_reports(benchmarks, **kwargs)[0]


def write_text_file(path, text, newline="\n"):
    """Write one generated file (UTF-8, no BOM) and log it."""
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    _bump("files_written")
    log_event("file", f"wrote {os.path.abspath(path)} ({os.path.getsize(path)} bytes)")
    return path


def write_console_file(report, folder="."):
    """Write a report as a console-importable file, byte-matching real exports:
    UTF-8 without BOM, CRLF line endings, and the (lying) utf-16 declaration."""
    out = os.path.join(folder, safe_file_name(report["Name"], ".ncm-report.xml"))
    root = ET.fromstring(report_contract_xml(report))
    ET.indent(root, space="  ")
    body = '<?xml version="1.0" encoding="utf-16"?>\n' + ET.tostring(root, encoding="unicode")
    return write_text_file(out, body, newline="\r\n")


# ---------------------------------------------------------------------------
# Console XML wire format for the NCM contract objects
# ---------------------------------------------------------------------------
#
# The SolarWinds.NCM.Contracts.Compliance.* types are XML-serialized on the
# wire. Some servers map a JSON object onto them; others hand the argument to
# an XML reader and fail with HTTP 400 "Value cannot be null. Parameter name:
# input" (observed on 2026.2.2). For those, the argument must be the contract
# XML as a string — the same shape as a console export file, and element order
# matters because .NET XML deserializers on the receiving side are
# order-sensitive. Order below is copied from real console exports (and from
# apps/porter's export writer in this repository).

def _b_str(value):
    return "true" if value else "false"


def _sub(parent, name, text):
    el = ET.SubElement(parent, name)
    el.text = text if text else None
    return el


def _rule_xml_into(parent, rule):
    r = ET.SubElement(parent, "PolicyRule")
    pats = ET.SubElement(r, "MultiLineRulePatterns")
    for p in rule.get("MultiLineRulePatterns") or []:
        m = ET.SubElement(pats, "MultiLineRulePattern")
        _sub(m, "EndBracket", p.get("EndBracket") or "")
        _sub(m, "PatternType", str(p.get("PatternType") or "Like"))
        _sub(m, "Condition", p.get("Condition") or "")
        _sub(m, "Pattern", p.get("Pattern") or "")
        _sub(m, "Criteria", _b_str(p.get("Criteria")))
        _sub(m, "BeginBracket", p.get("BeginBracket") or "")
    _sub(r, "RuleId", rule.get("RuleId") or "")
    _sub(r, "RuleName", rule.get("RuleName") or "")
    _sub(r, "Comments", rule.get("Comments") or "")
    _sub(r, "Grouping", rule.get("Grouping") or "")
    _sub(r, "RemediateScript", rule.get("RemediateScript") or "")
    _sub(r, "ConfigBlockStart", rule.get("ConfigBlockStart") or "")
    _sub(r, "ConfigBlockEnd", rule.get("ConfigBlockEnd") or "")
    _sub(r, "ConfigBlockPatternType", str(rule.get("ConfigBlockPatternType") or "Like"))
    _sub(r, "ConfigBlockMustExist", _b_str(rule.get("ConfigBlockMustExist")))
    _sub(r, "PatternType", str(rule.get("PatternType") or "Like"))
    _sub(r, "PatternMustExist", _b_str(rule.get("PatternMustExist")))
    _sub(r, "AdvancedMode", _b_str(rule.get("AdvancedMode")))
    _sub(r, "ErrorLevel", str(int(rule.get("ErrorLevel") or 0)))
    _sub(r, "SimplePatternText", rule.get("SimplePatternText") or "")
    _sub(r, "ExecuteScriptAutomatically", _b_str(rule.get("ExecuteScriptAutomatically")))
    _sub(r, "Owner", rule.get("Owner") or "")
    _sub(r, "RemediateScriptType", str(rule.get("RemediateScriptType") or "CLI"))
    _sub(r, "ExecuteRemediationScriptPerBlock",
         _b_str(rule.get("ExecuteRemediationScriptPerBlock")))
    _sub(r, "ExecuteScriptInConfigMode", _b_str(rule.get("ExecuteScriptInConfigMode")))
    return r


def report_contract_xml(report):
    """The full nested report as console-export XML — the AddPolicyReport argument."""
    root = ET.Element("PolicyReport", {
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    })
    _sub(root, "ID", report.get("ID") or "")
    _sub(root, "Name", report.get("Name") or "")
    _sub(root, "Comments", report.get("Comments") or "")
    _sub(root, "Group", report.get("Group") or "")
    _sub(root, "ShowSummaryFlag", _b_str(report.get("ShowSummaryFlag")))
    _sub(root, "ShowRulesWithoutViolationFlag",
         _b_str(report.get("ShowRulesWithoutViolationFlag")))
    pols = ET.SubElement(root, "AssignedPolicies")
    for p in report.get("AssignedPolicies") or []:
        pe = ET.SubElement(pols, "Policy")
        _sub(pe, "NodeSelectionString", p.get("NodeSelectionString") or "")
        _sub(pe, "ConfigTypes", str(p.get("ConfigTypes") or "Any"))
        rules_el = ET.SubElement(pe, "AssignedPolicyRules")
        for r in p.get("AssignedPolicyRules") or []:
            _rule_xml_into(rules_el, r)
        _sub(pe, "Grouping", p.get("Grouping") or "")
        _sub(pe, "Comments", p.get("Comments") or "")
        _sub(pe, "PolicyName", p.get("PolicyName") or "")
    _sub(root, "ReportStatus", str(report.get("ReportStatus") or "Enabled"))
    return ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------------------
# DataContract XML wire format (the .NET serializer behind "cannot unpackage")
# ---------------------------------------------------------------------------
#
# When the server says it "cannot unpackage" a parameter, it read the XML but
# the DataContractSerializer rejected it: that serializer wants the contract's
# namespace and its members in a fixed (alphabetical, absent explicit Order)
# sequence. These writers emit that shape; `ns` is the contract namespace to
# try ("" for contracts declared with an empty namespace).

DC_NS = "http://schemas.datacontract.org/2004/07/SolarWinds.NCM.Contracts.Compliance"
ARRAYS_NS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"


def _dc_el(parent, ns, name, text=None):
    el = ET.SubElement(parent, f"{{{ns}}}{name}" if ns else name)
    if text is not None and text != "":
        el.text = text
    return el


def _dc_string_list(parent, ns, name, values):
    holder = _dc_el(parent, ns, name)
    for v in values:
        item = ET.SubElement(holder, f"{{{ARRAYS_NS}}}string")
        item.text = v


def dc_rule_xml(rule, ns=DC_NS):
    root = ET.Element(f"{{{ns}}}PolicyRule" if ns else "PolicyRule")
    _dc_el(root, ns, "AdvancedMode", _b_str(rule.get("AdvancedMode")))
    _dc_el(root, ns, "Comments", rule.get("Comments") or "")
    _dc_el(root, ns, "ConfigBlockEnd", rule.get("ConfigBlockEnd") or "")
    _dc_el(root, ns, "ConfigBlockMustExist", _b_str(rule.get("ConfigBlockMustExist")))
    _dc_el(root, ns, "ConfigBlockPatternType", str(rule.get("ConfigBlockPatternType") or "Like"))
    _dc_el(root, ns, "ConfigBlockStart", rule.get("ConfigBlockStart") or "")
    _dc_el(root, ns, "ErrorLevel", str(int(rule.get("ErrorLevel") or 0)))
    _dc_el(root, ns, "ExecuteRemediationScriptPerBlock",
           _b_str(rule.get("ExecuteRemediationScriptPerBlock")))
    _dc_el(root, ns, "ExecuteScriptAutomatically", _b_str(rule.get("ExecuteScriptAutomatically")))
    _dc_el(root, ns, "ExecuteScriptInConfigMode", _b_str(rule.get("ExecuteScriptInConfigMode")))
    _dc_el(root, ns, "Grouping", rule.get("Grouping") or "")
    _dc_el(root, ns, "IsConfigBlockPatternRegEx", _b_str(rule.get("IsConfigBlockPatternRegEx")))
    _dc_el(root, ns, "MultiLineRulePatterns")
    _dc_el(root, ns, "Owner", rule.get("Owner") or "")
    _dc_el(root, ns, "PatternMustExist", _b_str(rule.get("PatternMustExist")))
    _dc_el(root, ns, "PatternType", str(rule.get("PatternType") or "Like"))
    _dc_el(root, ns, "RemediateScript", rule.get("RemediateScript") or "")
    _dc_el(root, ns, "RemediateScriptType", str(rule.get("RemediateScriptType") or "CLI"))
    _dc_el(root, ns, "RuleId", rule.get("RuleId") or "")
    _dc_el(root, ns, "RuleName", rule.get("RuleName") or "")
    _dc_el(root, ns, "SimplePatternText", rule.get("SimplePatternText") or "")
    return ET.tostring(root, encoding="unicode")


def dc_policy_xml(policy, rule_ids, ns=DC_NS):
    root = ET.Element(f"{{{ns}}}Policy" if ns else "Policy")
    _dc_el(root, ns, "AssignedPolicyRules")
    _dc_string_list(root, ns, "AssignedRulesList", rule_ids)
    _dc_el(root, ns, "Comments", policy.get("Comments") or "")
    _dc_el(root, ns, "ConfigTypes", str(policy.get("ConfigTypes") or "Any"))
    _dc_el(root, ns, "Grouping", policy.get("Grouping") or "")
    _dc_el(root, ns, "NodeSelectionString", policy.get("NodeSelectionString") or "")
    _dc_el(root, ns, "PolicyId", policy.get("PolicyId") or "")
    _dc_el(root, ns, "PolicyName", policy.get("PolicyName") or "")
    return ET.tostring(root, encoding="unicode")


def dc_report_xml(report, policy_ids, ns=DC_NS):
    root = ET.Element(f"{{{ns}}}PolicyReport" if ns else "PolicyReport")
    _dc_el(root, ns, "AssignedPolicies")
    _dc_string_list(root, ns, "AssignedPoliciesList", policy_ids)
    _dc_el(root, ns, "Comments", report.get("Comments") or "")
    _dc_el(root, ns, "Group", report.get("Group") or "")
    _dc_el(root, ns, "ID", report.get("ID") or "")
    _dc_el(root, ns, "Name", report.get("Name") or "")
    _dc_el(root, ns, "ReportStatus", str(report.get("ReportStatus") or "Enabled"))
    _dc_el(root, ns, "ShowRulesWithoutViolationFlag",
           _b_str(report.get("ShowRulesWithoutViolationFlag")))
    _dc_el(root, ns, "ShowSummaryFlag", _b_str(report.get("ShowSummaryFlag")))
    return ET.tostring(root, encoding="unicode")


# The wire formats the probe tries, in order. Each entry maps a rule/policy/
# report to the AddPolicyRule / AddPolicy / AddPolicyReport argument.
WIRE_FORMATS = {
    "json": {
        "label": "JSON contract objects",
        "rule": lambda r: r,
        "policy": lambda p, ids: dict(p, AssignedPolicyRules=[], AssignedRulesList=ids),
        "report": lambda rep, ids: dict(rep, AssignedPolicies=[], AssignedPoliciesList=ids),
    },
    "xml-dc": {
        "label": "DataContract XML strings",
        "rule": lambda r: dc_rule_xml(r, DC_NS),
        "policy": lambda p, ids: dc_policy_xml(p, ids, DC_NS),
        "report": lambda rep, ids: dc_report_xml(rep, ids, DC_NS),
    },
    "xml-plain": {
        "label": "plain XML strings (no namespace)",
        "rule": lambda r: dc_rule_xml(r, ""),
        "policy": lambda p, ids: dc_policy_xml(p, ids, ""),
        "report": lambda rep, ids: dc_report_xml(rep, ids, ""),
    },
}


def _clean_id(value, fallback):
    """Verb results come back as JSON strings that may carry quotes or braces."""
    if isinstance(value, str):
        cleaned = value.strip().strip('"').strip("{}").strip()
        if cleaned:
            return cleaned
    return fallback


def _norm_id(value):
    """Compare GUIDs from verb results and SWQL rows on equal terms."""
    return str(value or "").strip().strip('"').strip("{}").strip().lower()


def _query_ids(swis, swql, ids, chunk=100):
    """Run an `IN @ids` query over a list of ids in bounded chunks."""
    ids = [i for i in ids if i]
    rows = []
    for start in range(0, len(ids), chunk):
        rows.extend(swis.query(swql, {"ids": ids[start:start + chunk]}) or [])
    return rows


def existing_ncm_ids(swis, report):
    """Which of the RuleIds/PolicyIds this report would submit already exist.

    RuleIds are uuid5-derived from the DISA rule id, so a second import of the
    same STIG release submits the same ids an earlier import did. A rollback must
    not delete those earlier objects, so they are recorded before anything is
    created. Unverified: whether AddPolicyRule/AddPolicy honour a submitted id or
    always assign a fresh one is not documented; the returned id is used either
    way, and this snapshot only matters when it equals an existing one.
    """
    rule_ids = [r["RuleId"] for p in report["AssignedPolicies"]
                for r in p["AssignedPolicyRules"]]
    policy_ids = [p["PolicyId"] for p in report["AssignedPolicies"] if p.get("PolicyId")]
    rules = {_norm_id(row.get("PolicyRuleID")) for row in _query_ids(
        swis, "SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids",
        rule_ids)}
    policies = {_norm_id(row.get("PolicyID")) for row in _query_ids(
        swis, "SELECT PolicyID FROM Cirrus.Policies WHERE PolicyID IN @ids",
        policy_ids)}
    return {"rules": rules, "policies": policies}


def _verify_report(swis, report_id, expected_policies, expected_rules, log):
    """Read the report back — the import is only done if the tree actually exists."""
    log_event("verify", f"reading report {report_id} back (expecting {expected_policies} "
                        f"policies and {expected_rules} rules)")
    stored = swis.invoke("Cirrus.PolicyReports", "GetPolicyReport", report_id, True)
    if not stored:
        msg = (f"No data returned from GetPolicyReport for report {report_id} — "
               "the import cannot be confirmed")
        log_event("verify", msg, "error")
        raise SwisError(msg)
    stored_policies = stored.get("AssignedPolicies") or []
    stored_rules = sum(len(p.get("AssignedPolicyRules") or []) for p in stored_policies)
    if not stored_policies or stored_rules == 0:
        msg = (f"verification failed: report {report_id} was created but holds "
               f"{len(stored_policies)} policies and {stored_rules} rules "
               f"(expected {expected_policies} and {expected_rules}). Check the account's NCM "
               "role (WebUploader or higher) and the server's compliance settings.")
        log_event("verify", msg, "error")
        raise SwisError(msg)
    _say(log, "verify",
         f"verified: report holds {len(stored_policies)} policies and {stored_rules} rules")
    return report_id, len(stored_policies), stored_rules


def test_rule(swis, rule, config_text=None, config_id=None, fmt=None):
    """Evaluate one generated rule against a real configuration, server side.

    ``TestRule(policyRule, config)`` takes the configuration as text and
    ``TestRuleOnBackedUpConfig(policyRule, configId)`` takes the id of a config
    NCM already holds. Neither creates anything: this is the console's own
    "test the rule before you save it" path, and it needs only the WebDownloader
    role. It is the one way to find out that a generated pattern does what the
    STIG check text implied before a whole benchmark is imported on the strength
    of it.

    The rule travels as the same contract type AddPolicyRule takes, so the same
    wire-format ambiguity applies; ``fmt`` carries the format that worked so the
    caller can reuse it. Returns (result, fmt).

    SolarWinds documents the return as a string and does not document its
    shape, so the caller is handed it verbatim rather than parsed. Macros are
    not expanded for a config passed as text - only the backed-up-config route
    resolves them.
    """
    names = [fmt] if fmt else list(WIRE_FORMATS)
    rejections = []
    for name in names:
        spec = WIRE_FORMATS[name]
        try:
            if config_id:
                result = swis.invoke("Cirrus.PolicyReports", "TestRuleOnBackedUpConfig",
                                     spec["rule"](rule), config_id)
            else:
                result = swis.invoke("Cirrus.PolicyReports", "TestRule",
                                     spec["rule"](rule), config_text or "")
            return result, name
        except SwisError as exc:
            if "HTTP 400" not in str(exc):
                raise
            rejections.append(f"{spec['label']}: {str(exc).splitlines()[-1]}")
    raise SwisError("this server accepted none of the wire formats for TestRule:\n  "
                    + "\n  ".join(rejections))


def test_reports(swis, reports, config_text=None, config_id=None, limit=10, log=print):
    """Dry-run the generated rules against one configuration and report back.

    Returns (tested, with_output). Nothing is written to the server.
    """
    rules = [r for rep_ in reports for pol in rep_["AssignedPolicies"]
             for r in pol["AssignedPolicyRules"]]
    total = len(rules)
    if limit and limit > 0:
        rules = rules[:limit]
    source = f"backed-up config {config_id}" if config_id else "the supplied config text"
    _say(log, "verify", f"testing {len(rules)} of {total} rule(s) against {source} "
                        "(nothing is created on the server) …")
    fmt = None
    with_output = 0
    for rule in rules:
        result, fmt = test_rule(swis, rule, config_text, config_id, fmt)
        text = "" if result is None else str(result).strip()
        if text:
            with_output += 1
        first = text.splitlines()[0][:160] if text else "(no output)"
        _say(log, "verify", f"  {rule['RuleName'][:70]} -> {first}")
    _say(log, "verify", f"{len(rules)} rule(s) tested, {with_output} returned output. "
                        "SolarWinds does not document the shape of the TestRule result, so it "
                        "is echoed above exactly as the server sent it and not interpreted here.")
    return len(rules), with_output


def rollback_ncm(swis, rule_ids, policy_ids, report_id, log, preexisting=None):
    """Undo a partial bottom-up import.

    A STIG report is built from the bottom up, so a failure at the policy or
    report step leaves every rule already created sitting in the NCM rules
    library with nothing pointing at it. They are invisible in the Compliance
    view, they are not deleted by anything, and the next attempt at the same
    STIG adds a second full set. Deleting them explicitly, newest level first,
    is the only way back to the state before the import.

    Children are removed by their own verbs rather than with
    ``DeletePolicyReports(ids, deleteChildren=true)``, because that flag also
    reaches policies and rules that other reports share.

    ``preexisting`` is the snapshot from ``existing_ncm_ids``: any id that was
    already on the server before this run (the deterministic RuleIds make an
    earlier import of the same STIG release the usual case, and ``_clean_id``
    falls back to the submitted id when a verb returns nothing) is skipped, so a
    rollback deletes only what this run created.
    """
    preexisting = preexisting or {"rules": set(), "policies": set()}

    def split(ids, known):
        ours, kept, seen = [], [], set()
        for i in ids:
            key = _norm_id(i)
            if not key or key in seen:
                continue
            seen.add(key)
            (kept if key in known else ours).append(i)
        return ours, kept

    def drop(verb, *args):
        try:
            swis.invoke("Cirrus.PolicyReports", verb, *args)
            return True
        except SwisError as exc:
            _say(log, "rollbk", f"rollback: {verb} failed, clean up by hand - {exc}", "error")
            return False

    policy_ids, kept_policies = split(policy_ids or [], preexisting["policies"])
    rule_ids, kept_rules = split(rule_ids or [], preexisting["rules"])
    log_event("rollbk", f"rollback plan: report {report_id or '(none created)'}, "
                        f"{len(policy_ids)} policy id(s) and {len(rule_ids)} rule id(s) to "
                        f"delete; {len(kept_policies)} policy id(s) and {len(kept_rules)} rule "
                        "id(s) kept because they existed before this run")
    if report_id:
        _say(log, "rollbk", f"rollback: deleting report {report_id}")
        drop("DeletePolicyReports", [report_id], False)
    if policy_ids:
        _say(log, "rollbk", f"rollback: deleting {len(policy_ids)} policy/policies")
        drop("DeletePolicies", policy_ids, False)
    if rule_ids:
        _say(log, "rollbk", f"rollback: deleting {len(rule_ids)} rule(s)")
        drop("DeletePolicyRules", rule_ids)
    for label, kept in (("policy", kept_policies), ("rule", kept_rules)):
        for i in kept:
            _say(log, "rollbk", f"rollback: skipped {label} {i} - it existed on the server "
                                "before this import (an earlier import of the same STIG "
                                "release?), so this run did not create it")


class NcmWireError(SwisError):
    """No wire format the server accepts was found. Carries a console-importable
    XML file body so the caller can save it and finish the import through the
    NCM web console (Compliance → Manage Policy Reports → Import)."""

    def __init__(self, message, console_xml):
        super().__init__(message)
        self.console_xml = console_xml


def import_ncm_report(swis, report, log=print, rollback=True):
    """Import the report, probing how this server accepts the NCM contract types.

    The JSON endpoint's handling of SolarWinds.NCM.Contracts.Compliance.*
    varies by server: some map JSON objects, some want the contract serialized
    as an XML string ("Value cannot be null" / "cannot unpackage" are the two
    observed rejections). One cheap AddPolicyRule call probes each candidate
    format — JSON object, DataContract XML, plain XML — and the first one the
    server accepts is used for the whole bottom-up import (rules → policies →
    report, linked by ID lists). If none works, a nested console-format
    AddPolicyReport is tried, and as a last resort NcmWireError hands back a
    console-importable file so the import can be finished in the web UI.

    The result is verified by reading the report back before caching starts.
    Returns (report_id, policy_count, rule_count) as confirmed by the read-back.

    ``rollback`` deletes whatever the failed attempt managed to create, so a
    half-built import does not leave orphaned rules behind. Pass False to keep
    them for diagnosis. Rules and policies whose ids already existed before the
    run are never deleted by the rollback (see ``existing_ncm_ids``).
    """
    preexisting = existing_ncm_ids(swis, report)
    log_event("import", f"existing-id snapshot for \"{report['Name']}\": "
                        f"{len(preexisting['rules'])} rule id(s) and "
                        f"{len(preexisting['policies'])} policy id(s) already on the server")
    if preexisting["rules"] or preexisting["policies"]:
        _say(log, "import", f"note: {len(preexisting['rules'])} rule id(s) and "
                            f"{len(preexisting['policies'])} policy id(s) this report submits "
                            "already exist on the server; a rollback will leave those alone")
    probe_rule = report["AssignedPolicies"][0]["AssignedPolicyRules"][0]
    fmt = None
    first_rule_id = None
    rejections = []
    for name, spec in WIRE_FORMATS.items():
        try:
            result = swis.invoke("Cirrus.PolicyReports", "AddPolicyRule",
                                 spec["rule"](probe_rule))
            first_rule_id = _clean_id(result, probe_rule["RuleId"])
            fmt = name
            _say(log, "import", f"server accepts {spec['label']}")
            break
        except SwisError as exc:
            if "HTTP 400" not in str(exc):
                log_event("import", f"wire-format probe stopped: {spec['label']} failed with "
                                    "a non-400 error, so no other format is tried", "error")
                raise
            rejections.append(f"{spec['label']}: {str(exc).splitlines()[-1]}")
            _say(log, "import",
                 f"server rejected {spec['label']}; trying the next wire format …", "warn")
    if fmt:
        return _import_ncm_bottom_up(swis, report, log, WIRE_FORMATS[fmt],
                                     first_rule_id, rollback, preexisting)

    _say(log, "import", "no per-item wire format accepted; trying one nested AddPolicyReport "
                        "in the console-export format …", "warn")
    n_policies = len(report["AssignedPolicies"])
    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    try:
        report_id = _clean_id(
            swis.invoke("Cirrus.PolicyReports", "AddPolicyReport",
                        report_contract_xml(report), True), "")
        if report_id:
            return _verify_report(swis, report_id, n_policies, n_rules, log)
        rejections.append("console-format XML: no report id returned")
    except SwisError as exc:
        if "HTTP 400" not in str(exc):
            raise
        rejections.append(f"console-format XML: {str(exc).splitlines()[-1]}")
    log_event("import", "no wire format accepted for \"" + report["Name"] + "\": "
                        + "; ".join(rejections) + "; console-importable files will be written",
              "error")
    raise NcmWireError(
        "this server accepted none of the wire formats for the NCM compliance "
        "contract types:\n  " + "\n  ".join(rejections) + "\n"
        "A console-importable report file has been written instead — import it in "
        "the web console under Compliance → Manage Policy Reports → Import.",
        '<?xml version="1.0" encoding="utf-16"?>' + report_contract_xml(report))


def _import_ncm_bottom_up(swis, report, log, spec, first_rule_id, rollback=True,
                          preexisting=None):
    policy_ids = []
    all_rule_ids = [first_rule_id]
    report_id = ""
    first = True
    try:
        for policy in report["AssignedPolicies"]:
            rules = policy["AssignedPolicyRules"]
            _say(log, "import",
                 f"creating {len(rules)} rules for policy \"{policy['PolicyName']}\" …")
            rule_ids = []
            for i, rule in enumerate(rules, 1):
                if first:
                    # The probe already created this rule.
                    rule_ids.append(first_rule_id)
                    first = False
                    continue
                result = swis.invoke("Cirrus.PolicyReports", "AddPolicyRule",
                                     spec["rule"](rule))
                new_rule_id = _clean_id(result, rule["RuleId"])
                rule_ids.append(new_rule_id)
                all_rule_ids.append(new_rule_id)
                if i % 25 == 0:
                    _say(log, "import", f"  {i}/{len(rules)} rules created")

            result = swis.invoke("Cirrus.PolicyReports", "AddPolicy",
                                 spec["policy"](policy, rule_ids), False)
            policy_ids.append(_clean_id(result, policy["PolicyId"]))
            _say(log, "import",
                 f"created policy \"{policy['PolicyName']}\" with {len(rule_ids)} rules")

        report_id = _clean_id(
            swis.invoke("Cirrus.PolicyReports", "AddPolicyReport",
                        spec["report"](report, policy_ids), False), "")
        if not report_id:
            raise SwisError("AddPolicyReport did not return the new report id")
        log_event("import", f"AddPolicyReport returned report id {report_id}")

        return _verify_report(swis, report_id, len(policy_ids), len(all_rule_ids), log)
    except SwisError as exc:
        log_event("import", f"import of \"{report['Name']}\" failed: {exc}", "error")
        if rollback:
            _say(log, "import", "import failed part way through; removing what it created …")
            rollback_ncm(swis, all_rule_ids, policy_ids, report_id, log, preexisting)
        else:
            _say(log, "import", f"import failed part way through; {len(all_rule_ids)} rule(s) "
                                f"and {len(policy_ids)} policy/policies were left on the server "
                                "(--no-rollback)", "warn")
        raise


def import_ncm_reports(swis, reports, log=print, rollback=True):
    """Import several reports in turn, stopping at the first failure.

    Returns (imported, failure, remaining): ``imported`` lists
    (report, report_id, rule_count) for every report that completed and was
    verified, ``failure`` is the exception that stopped the run (None when all
    succeeded), and ``remaining`` lists the reports that were not imported,
    the failed one first. Reports imported before a failure stay on the server
    and are still the caller's to cache or disable.
    """
    imported = []
    for index, report in enumerate(reports):
        n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
        _say(log, "import", f"importing \"{report['Name']}\" - {n_rules} rules ...")
        try:
            new_id, _n_pol, n_stored = import_ncm_report(swis, report, log=log,
                                                         rollback=rollback)
        except SwisError as exc:
            log_event("import", f"stopping at \"{report['Name']}\": {len(imported)} of "
                                f"{len(reports)} report(s) imported, {len(reports) - index} "
                                "not imported", "error")
            return imported, exc, list(reports[index:])
        imported.append((report, new_id, n_stored))
        _bump("imported")
        _say(log, "import", f"imported: \"{report['Name']}\" ({new_id}) - {n_stored} rules")
    return imported, None, []


def finish_ncm_imports(swis, new_ids, disabled=False, no_cache=False, log=print):
    """Disable or start caching the reports a run imported. Returns True when the
    requested end state was confirmed (or nothing was asked of the server)."""
    if not new_ids:
        return True
    if disabled:
        # ReportStatus travels in the payload, but UpdateReportStatus is the verb
        # that owns the field, so say it explicitly rather than trusting the
        # import to have carried it, and read it back.
        swis.invoke("Cirrus.PolicyReports", "UpdateReportStatus", "Disabled", list(new_ids))
        stored = swis.query("SELECT Name, ReportStatus FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids",
                            {"ids": list(new_ids)})
        if not stored:
            _say(log, "verify", "warning: No data returned reading ReportStatus back after "
                                "UpdateReportStatus; confirm the reports are disabled in the "
                                "console", "warn")
            return False
        still_on = [r.get("Name") for r in stored if r.get("ReportStatus")]
        if still_on:
            _say(log, "verify", "warning: still enabled after UpdateReportStatus: "
                 + ", ".join(still_on), "warn")
            return False
        _say(log, "import", f"{len(new_ids)} report(s) imported Disabled and not cached. Enable "
                            "them in the console, or with UpdateReportStatus('Enabled', [ids]), "
                            "once the rules have been reviewed.")
        return True
    if no_cache:
        _say(log, "import", "compliance caching not started (--no-cache); the reports show no "
                            "data until you run Update Violations in the console or invoke "
                            "StartCaching.")
        return True
    # Always pass the specific GUIDs: an empty array would re-cache every report.
    swis.invoke("Cirrus.PolicyReports", "StartCaching", list(new_ids))
    _say(log, "import", f"compliance caching started for {len(new_ids)} report(s). Watch them "
                        "under My Dashboards > Network Configuration > Compliance. The policy "
                        "cache also refreshes on its own at 11:55 PM daily when that job is "
                        "enabled.")
    return True


# ---------------------------------------------------------------------------
# Removing an imported report: report, then unshared policies, then unshared rules
# ---------------------------------------------------------------------------
#
# DeletePolicyReports(ids, deleteChildren=false) on its own leaves the report's
# policies and rules behind with nothing pointing at them, the orphan state
# docs/modules/ncm-compliance-reports.md warns about; deleteChildren=true also
# reaches children other reports share. The clean path reads the tree, deletes
# the report row, then the policies with DeletePolicies(ids, false), then the
# rules with DeletePolicyRules, skipping anything another report or policy still
# references (Cirrus.PolicyAssignment / Cirrus.PolicyRuleAssignment).

def plan_ncm_removal(swis, report_ids, log=print):
    """Work out what removing these reports deletes and what it must keep."""
    report_keys = {_norm_id(r) for r in report_ids}
    policies, rules, names = {}, {}, {}

    def add(store, value, name=None):
        key = _norm_id(value)
        if key:
            store.setdefault(key, str(value).strip().strip("{}"))
            if name and key not in names:
                names[key] = name

    for report_id in report_ids:
        tree = swis.invoke("Cirrus.PolicyReports", "GetPolicyReport", report_id, True)
        if not tree:
            _say(log, "remove", f"note: No data returned from GetPolicyReport for {report_id}; "
                                "its policies and rules are taken from Cirrus.PolicyAssignment "
                                "alone", "warn")
            continue
        for pid in tree.get("AssignedPoliciesList") or []:
            add(policies, pid)
        for pol in tree.get("AssignedPolicies") or []:
            add(policies, pol.get("PolicyId"), pol.get("PolicyName"))
            for rid in pol.get("AssignedRulesList") or []:
                add(rules, rid)
            for rule in pol.get("AssignedPolicyRules") or []:
                add(rules, rule.get("RuleId"), rule.get("RuleName"))
    # The export tree is not documented to carry PolicyId, so the SWQL link
    # tables are read as well; together they give the report's full membership.
    for row in _query_ids(swis, "SELECT PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyReportID IN @ids",
                          list(report_ids)):
        add(policies, row.get("PolicyID"))
    for row in _query_ids(swis, "SELECT PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyID IN @ids",
                          list(policies.values())):
        add(rules, row.get("PolicyRuleID"))

    kept_policies = {}
    for row in _query_ids(swis, "SELECT PolicyReportID, PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyID IN @ids",
                          list(policies.values())):
        other = _norm_id(row.get("PolicyReportID"))
        key = _norm_id(row.get("PolicyID"))
        if key in policies and other and other not in report_keys:
            kept_policies.setdefault(key, []).append(str(row.get("PolicyReportID")))
    delete_policy_keys = set(policies) - set(kept_policies)

    kept_rules = {}
    for row in _query_ids(swis, "SELECT PolicyID, PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyRuleID IN @ids",
                          list(rules.values())):
        other = _norm_id(row.get("PolicyID"))
        key = _norm_id(row.get("PolicyRuleID"))
        if key in rules and other and other not in delete_policy_keys:
            kept_rules.setdefault(key, []).append(str(row.get("PolicyID")))

    log_event("remove", f"removal plan for {len(report_ids)} report(s): {len(policies)} "
                        f"policy/policies and {len(rules)} rule(s) found; "
                        f"{len(delete_policy_keys)} policy/policies and "
                        f"{len(set(rules) - set(kept_rules))} rule(s) to delete, "
                        f"{len(kept_policies)} policy/policies and {len(kept_rules)} rule(s) "
                        "kept because something else still uses them")
    return {
        "reports": list(report_ids),
        "delete_policies": [policies[k] for k in policies if k in delete_policy_keys],
        "keep_policies": {policies[k]: v for k, v in kept_policies.items()},
        "delete_rules": [rules[k] for k in rules if k not in kept_rules],
        "keep_rules": {rules[k]: v for k, v in kept_rules.items()},
        "names": {v: names[k] for store in (policies, rules) for k, v in store.items()
                  if k in names},
    }


def describe_removal_plan(plan, log=print, prefix=""):
    names = plan["names"]

    def label(i):
        return f"{i} \"{names[i]}\"" if i in names else i

    _say(log, "remove", f"{prefix}report(s): {len(plan['reports'])}  "
         + ", ".join(plan["reports"]))
    _say(log, "remove", f"{prefix}policies to delete: {len(plan['delete_policies'])}")
    for i in plan["delete_policies"]:
        _say(log, "remove", f"{prefix}  - {label(i)}")
    _say(log, "remove", f"{prefix}rules to delete: {len(plan['delete_rules'])}")
    for pid, others in plan["keep_policies"].items():
        _say(log, "remove", f"{prefix}kept policy {label(pid)}: still assigned to another "
                            f"report ({', '.join(others)})")
    for rid, others in plan["keep_rules"].items():
        _say(log, "remove", f"{prefix}kept rule {label(rid)}: still assigned to a policy that "
                            f"is not being deleted ({', '.join(others)})")


def remove_ncm_reports(swis, plan, log=print):
    """Delete the report rows, then the unshared policies, then the unshared rules.

    deleteChildren is false on both delete verbs that take it: the children this
    run may delete are named explicitly instead. Returns a summary dict.
    """
    swis.invoke("Cirrus.PolicyReports", "DeletePolicyReports", list(plan["reports"]), False)
    _say(log, "remove", f"deleted {len(plan['reports'])} report(s)")
    if plan["delete_policies"]:
        swis.invoke("Cirrus.PolicyReports", "DeletePolicies", list(plan["delete_policies"]), False)
        _say(log, "remove", f"deleted {len(plan['delete_policies'])} policy/policies")
    if plan["delete_rules"]:
        swis.invoke("Cirrus.PolicyReports", "DeletePolicyRules", list(plan["delete_rules"]))
        _say(log, "remove", f"deleted {len(plan['delete_rules'])} rule(s)")
    left = {
        "reports": _query_ids(swis, "SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids",
                              plan["reports"]),
        "policies": _query_ids(swis, "SELECT PolicyID FROM Cirrus.Policies WHERE PolicyID IN @ids",
                               plan["delete_policies"]),
        "rules": _query_ids(swis, "SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids",
                            plan["delete_rules"]),
    }
    for kind, rows in left.items():
        if rows:
            _say(log, "remove", f"warning: {len(rows)} {kind} still present after the delete "
                                "call", "warn")
    return left


# ---------------------------------------------------------------------------
# Target detection: which compliance module should this STIG land in?
# ---------------------------------------------------------------------------
#
# The zip/file name and the benchmark title carry the product. Network-vendor
# keywords route to NCM and also set the policy's node scope; OS keywords route
# to Server Configuration Monitor.

# keyword (matched case-insensitively) -> the Vendor value NCM nodes report
NETWORK_VENDORS = {
    "cisco": "Cisco", "ios ": "Cisco", "ios_": "Cisco", "nx-os": "Cisco",
    "nx_os": "Cisco", "asa": "Cisco", "juniper": "Juniper", "junos": "Juniper",
    "arista": "Arista", "palo alto": "Palo Alto", "palo_alto": "Palo Alto",
    "paloalto": "Palo Alto", "f5 ": "F5", "f5_": "F5", "big-ip": "F5",
    "bigip": "F5", "fortinet": "Fortinet", "fortigate": "Fortinet",
    "brocade": "Brocade", "check point": "Check Point", "checkpoint": "Check Point",
    "arubaos": "Aruba", "aruba": "Aruba", "extreme": "Extreme", "huawei": "Huawei",
    "dell os10": "Dell", "router": None, "switch": None, "firewall": None,
    "network device": None,
}

# keyword -> (display OS name, SWQL filter against Orion.Nodes for assignment)
SERVER_OSES = {
    "red hat": ("Red Hat Enterprise Linux", "MachineType LIKE '%Red Hat%'"),
    "rhel": ("Red Hat Enterprise Linux", "MachineType LIKE '%Red Hat%'"),
    "ubuntu": ("Ubuntu", "MachineType LIKE '%Ubuntu%'"),
    "debian": ("Debian", "MachineType LIKE '%Debian%'"),
    "centos": ("CentOS", "MachineType LIKE '%CentOS%'"),
    "linux": ("Linux", "MachineType LIKE '%Linux%'"),
    "windows": ("Windows", "MachineType LIKE '%Windows%'"),
    "sql server": ("Windows", "MachineType LIKE '%Windows%'"),
    "iis": ("Windows", "MachineType LIKE '%Windows%'"),
    "exchange": ("Windows", "MachineType LIKE '%Windows%'"),
}


def detect_target(benchmarks, source_name):
    """Return ('network', vendor_or_None) or ('server', (os, swql)) or (None, None).

    Vendor keywords win over OS keywords only when they appear and no OS does;
    a Windows/Linux match routes to SCM even if generic words like 'router'
    also appear somewhere.
    """
    text = " ".join([source_name or ""] + [b["title"] + " " + b["source"]
                                           for b in benchmarks]).lower()
    for kw, os_info in SERVER_OSES.items():
        if kw in text:
            log_event("route", f"server keyword '{kw}' matched in the file/benchmark names "
                               f"-> server ({os_info[0]})")
            return "server", os_info
    vendor = None
    matched = []
    for kw, v in NETWORK_VENDORS.items():
        if kw in text:
            matched.append(kw)
            if v:
                vendor = v
                break
    if matched:
        log_event("route", "network keyword(s) " + ", ".join(f"'{k}'" for k in matched)
                           + f" matched -> network, vendor {vendor or '(not identified)'}")
        return "network", vendor
    log_event("route", "no server or network keyword matched the file/benchmark names")
    return None, None


def node_where_for(vendor):
    # Bare column names: the SQL fragment in real console exports says Vendor,
    # not Nodes.Vendor, and exact vendor equality is what the node picker writes.
    if not vendor:
        log_event("scope", "no vendor identified; the node scope defaults to "
                           "(Vendor = 'Cisco')", "warn")
    return f"(Vendor = '{vendor}')" if vendor else "(Vendor = 'Cisco')"


# ---------------------------------------------------------------------------
# Server Compliance: XCCDF -> SCM policy YAML
# ---------------------------------------------------------------------------
#
# SCM's policy engine imports the !policy YAML format (see the shipped IIS 8.5
# policy and docs/modules/scm-compliance-policies.md). A manual STIG has no
# machine checks, so each generated rule carries an attestation sentinel: a
# harmless Write-Host probe whose output never matches, keeping the rule
# failing — an open action item with the STIG's check and fix text attached —
# until an operator reviews it. JSON string quoting is valid YAML, which keeps
# the emitter dependency-free.

def _yq(value):
    """Quote a scalar for YAML via JSON (JSON strings are valid YAML)."""
    return json.dumps(value or "", ensure_ascii=False)


def xccdf_to_scm_yaml(benchmark):
    """Convert one XCCDF benchmark into an importable SCM compliance policy."""
    name = f"{benchmark['title']} V{benchmark['version']} ({benchmark['release']})"[:250]
    policy_uid = uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-scm:" + (benchmark["benchmark_id"]
                                                                   or benchmark["title"]))
    lines = [
        "!policy",
        f"name: {_yq(name)}",
        f"uniqueId: {policy_uid}",
        "pluginName: SCM",
        f"description: {_yq('DISA STIG imported by the DISA STIG Conversion Tool from ' + benchmark['source'] + '. Every rule is a manual-review attestation: it reports failed, with the STIG check and fix text attached, until an engineer verifies the setting and replaces or disables the rule. Nothing in this policy changes server configuration.')}",
        "version: 2",
        "builtIn: false",
        "rules:",
    ]
    for r in benchmark["rules"]:
        rule_uid = uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-scm-rule:" + r["rule_id"])
        check = r["check_content"] or (
            f"Machine check (SCAP edition): OVAL definition {r['oval_ref']}. "
            "The manual STIG for this product carries the prose check text."
            if r.get("oval_ref") else "")
        # The probe runs as PowerShell on every assigned node: the id is validated
        # and the whole text is a single-quoted literal, so no STIG content can
        # expand ($(...), $var) or escape (` or ") inside the script source.
        probe_id = scm_probe_id(r["vuln_id"], r["rule_id"])
        probe = "Write-Host " + ps_single_quote(f"{probe_id} reviewed: False")
        lines += [
            f"- displayId: {_yq(r['vuln_id'])}",
            f"  uniqueId: {rule_uid}",
            f"  name: {_yq(r['title'][:250])}",
            f"  severity: {r['severity'].capitalize()}",
            f"  description: {_yq(r['discussion'])}",
            f"  remediationDescription: {_yq(r['fix_text'])}",
            f"  checkText: {_yq(check)}",
            "  condition: !matches",
            f"    expression: {_yq(probe_id + ' reviewed: True')}",
            "    source: !scm.powershell",
            f"      description: {_yq('STIG ' + r['stig_id'] + ' manual-review attestation')}",
            f"      script: {_yq(probe)}",
        ]
    log_event("build", f"SCM policy \"{name}\" uniqueId {policy_uid}: "
                       f"{len(benchmark['rules'])} manual-review rule(s)")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_download(args):
    name = args.package
    if name.startswith("http://") or name.startswith("https://"):
        url = name
    else:
        if not name.lower().endswith(".zip"):
            name += ".zip"
        url = DISA_ZIP_BASE + name
    dest = os.path.join(args.dir, safe_file_name(
        os.path.basename(urllib.parse.urlsplit(url).path) or "stig-download.zip"))
    print(f"downloading {url}")
    log_event("file", f"downloading {url} to {os.path.abspath(dest)}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as out:
            while chunk := resp.read(1 << 16):
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: HTTP {exc.code} for {url}\n"
                 "Check the exact package name on https://public.cyber.mil/stigs/downloads/ "
                 "(names are case-sensitive), or pass the full URL.")
    _bump("files_written")
    log_event("file", f"wrote {os.path.abspath(dest)} ({os.path.getsize(dest)} bytes)")
    print(f"saved {dest} ({os.path.getsize(dest):,} bytes)")
    if not zipfile.is_zipfile(dest):
        sys.exit(f"error: {dest} is not a zip — the mirror may have returned an error page")
    for b in load_benchmarks(dest):
        print(f"  contains: {b['title']} — {len(b['rules'])} rules")


def is_scm_path(path):
    """A file routed to the SCM policy reader (.yaml/.yml, which covers the
    .scm-policy.yaml this tool writes, or a legacy .scm-profile, whose content
    load_scm_policy then classifies)."""
    return os.path.isfile(path) and path.lower().endswith(SCM_INPUT_SUFFIXES)


def scm_policy_filename(benchmark, stem=None):
    """File name for a converted SCM policy (see SCM_POLICY_SUFFIX)."""
    base = benchmark["benchmark_id"] or benchmark["title"]
    if stem:
        return safe_file_name(f"{stem}.{benchmark['benchmark_id'] or 'benchmark'}",
                              SCM_POLICY_SUFFIX)
    return safe_file_name(base, SCM_POLICY_SUFFIX)


def cmd_parse(args):
    if is_scm_path(args.path):
        info = scan_scm_policy(load_scm_policy(args.path, log=print))
        sev = ", ".join(f"{v} {k}" for k, v in sorted(info["severity_counts"].items()))
        print(f"{info['name']}  (SCM compliance policy)")
        print(f"  {len(info['rules'])} rules: {sev}")
        if args.rules:
            for r in info["rules"]:
                print(f"    {r}")
        return
    benchmarks = load_benchmarks(args.path)
    print(resolve_route("auto", benchmarks, os.path.basename(args.path))[2])
    for b in benchmarks:
        counts = {}
        for r in b["rules"]:
            counts[r["severity"]] = counts.get(r["severity"], 0) + 1
        sev = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low") if s in counts)
        print(f"{b['title']}  [{b['edition']} edition]")
        print(f"  benchmark {b['benchmark_id']}  V{b['version']}  {b['release']}  "
              f"(from {b['source']})")
        print(f"  {len(b['rules'])} rules: {sev}")
        if args.rules:
            for r in b["rules"]:
                print(f"    {r['vuln_id']:<10} {r['stig_id']:<18} [{r['severity']:<6}] {r['title']}")
        print()


def resolve_route(target, benchmarks, source_name, node_where=None):
    """Decide the destination module for parsed XCCDF benchmarks.

    target: 'auto' | 'network' | 'server' (the dropdown / --target choice).
    Returns ('network', where_clause, note) or ('server', (os_name, swql), note).
    """
    detected, info = detect_target(benchmarks, source_name)
    explicit_where = node_where and not node_where.lower().startswith("auto") \
        and not node_where.startswith("(auto")
    if target == "server" or (target == "auto" and detected == "server"):
        os_info = info if detected == "server" else ("(OS not recognized)",
                                                     "MachineType LIKE '%'")
        why = "detected from the file/benchmark name" if detected == "server" \
            else "forced by the Server Compliance selection"
        note = f"target: Server Configuration Monitor — {os_info[0]} ({why})"
        log_event("route", f"decision: SCM for {source_name} (--target {target}, detected "
                           f"{detected or 'nothing'}); {note}")
        log_event("scope", f"SCM node filter suggested for assignment: {os_info[1]}")
        return "server", os_info, note
    vendor = info if detected == "network" else None
    where = node_where if explicit_where else node_where_for(vendor)
    log_event("scope", f"NCM node scope {where} ("
                       + ("explicit --node-where" if explicit_where else
                          f"derived from vendor {vendor}" if vendor else "default") + ")")
    if target == "network" and detected == "server":
        note = ("target: NCM (forced by the Network Compliance selection — the file "
                "looks like a server STIG)")
    elif vendor:
        note = f"target: NCM — vendor {vendor} detected, node scope {where}"
    elif detected == "network":
        note = f"target: NCM — network device detected, node scope {where}"
    else:
        note = (f"target: NCM by default — nothing recognized in the name; "
                f"node scope {where} (override with the Server Compliance option "
                "or --target server if this is a server STIG)")
    log_event("route", f"decision: NCM for {source_name} (--target {target}, detected "
                       f"{detected or 'nothing'}); {note}",
              "warn" if detected is None and target == "auto" else "info")
    return "network", where, note


def make_reports_from_args(args, benchmarks, node_where):
    return build_reports(
        benchmarks, name=args.name, grouping=args.grouping,
        node_where=node_where, config_type=args.config_type, mode=args.mode,
        source_path=args.path, enabled=not getattr(args, "disabled", False),
    )


def cmd_build(args):
    if is_scm_path(args.path):
        info = scan_scm_policy(load_scm_policy(args.path, log=print))
        print(f"\"{info['name']}\" is an SCM compliance policy: the YAML file itself is "
              "the import payload — nothing to build.\n"
              "Import it with:  disa_stig_tool.py import <file> …  "
              "(or POST [yamlText] to Invoke/Orion.PolicyEngine.Policy/ImportPolicy)")
        return
    benchmarks = load_benchmarks(args.path)
    kind, info, note = resolve_route(args.target, benchmarks,
                                     os.path.basename(args.path), args.node_where)
    print(note)
    stem = os.path.splitext(os.path.basename(args.path))[0]
    if kind == "server":
        for b in benchmarks:
            out = args.output if args.output and len(benchmarks) == 1 else \
                scm_policy_filename(b, stem)
            write_text_file(out, xccdf_to_scm_yaml(b), newline=None)
            print(f"wrote {out}: SCM policy \"{b['title']}\" — {len(b['rules'])} rules")
        print("import with:  disa_stig_tool.py import <same source> --target server …")
        return
    warning = xml_config_warning(info)
    if warning:
        print(warning)
    reports = make_reports_from_args(args, benchmarks, info)
    for report in reports:
        out = write_console_file(report)
        n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
        print(f"wrote {out}: report \"{report['Name']}\" — {n_rules} rules "
              "(console-importable XML)")
    print("import via the API with:  disa_stig_tool.py import <same source> …  "
          "or through the web console: Compliance → Manage Policy Reports → Import")


def import_scm_benchmarks(swis, benchmarks, os_info, log=print):
    """Convert each benchmark to an SCM policy and import it via ImportPolicy."""
    os_name, swql = os_info
    for b in benchmarks:
        yaml_text = xccdf_to_scm_yaml(b)
        policy_id, name = import_scm_policy(swis, yaml_text, log=log)
        _say(log, "scm", f"imported SCM policy \"{name}\" (PolicyID {policy_id}) — "
                         f"{len(b['rules'])} manual-review rules")
    log_event("scope", f"SCM policies are not assigned by this tool; suggested node query: "
                       f"SELECT NodeID, Caption, MachineType FROM Orion.Nodes WHERE {swql}")
    log(f"Assign to your {os_name} nodes under Settings → SCM Settings → Policies "
        "(or Orion.PolicyEngine.Policy.AssignToEntity). Find them with:")
    log(f"  SELECT NodeID, Caption, MachineType FROM Orion.Nodes WHERE {swql}")
    log("SCM evaluates an assigned policy once a day and on demand "
        "(Orion.PolicyEngine.Policy.PollNowAndEvaluate). Until an engineer has "
        "verified a check, disable that rule in the console with a reason rather "
        "than leaving it failing: the reason is stored in "
        "Orion.PolicyEngine.Rule.DisableReason, and disabling is global, never "
        "per node.")


def connect(args):
    """Build a SwisClient from the shared connection arguments."""
    password = os.environ.get("SWIS_PASSWORD")
    log_event("swis", f"connecting to {args.host}:{args.port} as user '{args.user}'; password "
                      + ("from SWIS_PASSWORD" if password else "prompted for"))
    password = password or getpass.getpass(f"password for {args.user}: ")
    register_secret(password)
    pinned = None
    if args.pin_server_cert:
        pinned, fingerprint, stock = fetch_server_cert(args.host, args.port)
        log_event("swis", f"pinned the certificate {args.host}:{args.port} presents: SHA-256 "
                          f"{fingerprint}" + (" (stock SolarWinds-Orion)" if stock else ""))
        print(f"pinned the server certificate — SHA-256 {fingerprint}"
              + (" (stock SolarWinds-Orion certificate)" if stock else ""))
    return logged(SwisClient(args.host, args.user, password, port=args.port,
                             verify=not args.insecure, ca_file=args.ca_file, pinned_pem=pinned))


def cmd_test(args):
    """Evaluate the generated rules against a real config without importing."""
    if is_scm_path(args.path):
        sys.exit("error: rule testing is an NCM feature; an SCM policy has no "
                 "equivalent server-side dry run. Import it and use "
                 "Orion.PolicyEngine.Policy.PollNowAndEvaluate against one node.")
    config_text = None
    if args.config_file:
        with open(args.config_file, encoding="utf-8", errors="replace") as fh:
            config_text = fh.read()
    if not config_text and not args.config_id:
        sys.exit("error: give --config-file <path> or --config-id <NCM config GUID>. "
                 "Find one with: SELECT ConfigID, NodeID, ConfigType, DownloadTime "
                 "FROM NCM.ConfigArchive ORDER BY DownloadTime DESC")
    swis = logged(connect(args))
    benchmarks = load_benchmarks(args.path)
    kind, info, note = resolve_route(args.target, benchmarks,
                                     os.path.basename(args.path), args.node_where)
    print(note)
    if kind == "server":
        sys.exit("error: this benchmark routes to SCM, which has no TestRule verb. "
                 "Force NCM with --target network if you meant to test it there.")
    reports = make_reports_from_args(args, benchmarks, info)
    test_reports(swis, reports, config_text=config_text, config_id=args.config_id,
                 limit=args.limit)


def cmd_remove(args):
    """Delete an imported policy report, the supported way to undo an import.

    Reads the report's tree, then deletes the report row, its policies
    (DeletePolicies with deleteChildren false) and its rules (DeletePolicyRules),
    keeping any policy another report still uses and any rule another policy
    still uses. Prints exactly what was deleted and what was kept.
    """
    swis = logged(connect(args))
    log_event("remove", f"remove requested for report name \"{args.name}\" "
                        f"(dry run: {bool(args.dry_run)}, --yes: {bool(args.yes)})")
    found = swis.query("SELECT PolicyReportID, Name, Grouping FROM Cirrus.PolicyReports WHERE Name = @n",
                       {"n": args.name})
    if not found:
        sys.exit(f"error: no policy report named \"{args.name}\" on this server")
    log_event("remove", f"{len(found)} report(s) named \"{args.name}\": "
                        + ", ".join(str(r.get("PolicyReportID")) for r in found))
    if getattr(args, "delete_children", False):
        print("note: --delete-children is deprecated and ignored. remove now deletes the "
              "report's policies and rules itself, skipping any another report or policy "
              "still uses, and never passes deleteChildren=true.")
    ids = [r["PolicyReportID"] for r in found]
    plan = plan_ncm_removal(swis, ids)
    print(f"{'would delete' if args.dry_run else 'about to delete'} {len(ids)} report(s) "
          f"named \"{args.name}\":")
    describe_removal_plan(plan, print, prefix="  ")
    if args.dry_run:
        print("dry run: nothing was deleted.")
        log_event("remove", "dry run: nothing was deleted")
        return
    if not args.yes:
        sys.exit("refusing to delete without --yes (preview with --dry-run)")
    left = remove_ncm_reports(swis, plan)
    log_event("remove", f"done: deleted {len(ids)} report(s), {len(plan['delete_policies'])} "
                        f"policy/policies and {len(plan['delete_rules'])} rule(s)")
    print(f"done: deleted {len(ids)} report(s), {len(plan['delete_policies'])} "
          f"policy/policies and {len(plan['delete_rules'])} rule(s); kept "
          f"{len(plan['keep_policies'])} shared policy/policies and "
          f"{len(plan['keep_rules'])} shared rule(s).")
    if any(left.values()):
        sys.exit("error: some objects were still present after deletion; see the "
                 "warnings above")


def cmd_import(args):
    swis = logged(connect(args))

    if is_scm_path(args.path):
        text = load_scm_policy(args.path, log=print)
        policy_id, name = import_scm_policy(swis, text, log=print)
        log_event("scm", f"imported SCM policy \"{name}\" (PolicyID {policy_id})")
        print(f"imported SCM policy \"{name}\" (PolicyID {policy_id}).")
        print("Assign it to nodes under Settings → SCM Settings → Policies, or via "
              "Orion.PolicyEngine.Policy.AssignToEntity.")
        return

    benchmarks = load_benchmarks(args.path)
    kind, info, note = resolve_route(args.target, benchmarks,
                                     os.path.basename(args.path), args.node_where)
    print(note)
    if kind == "server":
        import_scm_benchmarks(swis, benchmarks, info)
        return

    warning = xml_config_warning(info)
    if warning:
        print(warning)
    reports = make_reports_from_args(args, benchmarks, info)
    for report in reports:
        existing = swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                              {"n": report["Name"]})
        if existing:
            log_event("import", f"name collision: report \"{report['Name']}\" already exists "
                                f"({existing[0]['PolicyReportID']}); nothing was imported",
                      "error")
            sys.exit(f"error: a report named \"{report['Name']}\" already exists "
                     f"({existing[0]['PolicyReportID']}). Rename with --name, delete it "
                     f"with \"remove --name\", or remove it in the console — this tool "
                     "never overwrites.")

    imported, failure, remaining = import_ncm_reports(
        swis, reports, log=print, rollback=not args.no_rollback)
    new_ids = [new_id for _rep, new_id, _n in imported]
    # Reports that completed before a failure are real, verified imports: they
    # get the same caching / disabling as a fully successful run.
    finish_ncm_imports(swis, new_ids, disabled=args.disabled, no_cache=args.no_cache,
                       log=print)
    if failure is None:
        return
    if imported:
        print(f"{len(imported)} of {len(reports)} report(s) were imported before the "
              "failure and remain on the server: "
              + ", ".join(f"\"{rep['Name']}\"" for rep, _i, _n in imported))
    if isinstance(failure, NcmWireError):
        print(f"error: {failure}")
        log_event("import", f"writing console-importable files for {len(remaining)} "
                            "report(s) the API did not accept", "warn")
        for rep in remaining:
            print(f"wrote {write_console_file(rep)}")
        sys.exit("import the files written above through the web console: "
                 "Compliance > Manage Policy Reports > Import")
    print("not imported: " + ", ".join(f"\"{rep['Name']}\"" for rep in remaining))
    raise failure


def add_source_args(p):
    p.add_argument("path", help="STIG zip, extracted directory, a single *-xccdf.xml file, "
                                "or an SCM policy .yaml / .scm-policy.yaml")
    p.add_argument("--name", help="report name base: each report is named '<name> - "
                                  "<benchmark id>' (default: the zip file name for a zip, "
                                  "otherwise the benchmark title)")
    p.add_argument("--grouping", default="DISA STIG", help="folder for report/policies/rules")
    p.add_argument("--target", choices=("auto", "network", "server"), default="auto",
                   help="auto: route by the file/benchmark name (network vendors to NCM, "
                        "Windows/Linux/RHEL/Debian/Ubuntu/CentOS to SCM). "
                        "network: NCM compliance only. server: SCM compliance only.")
    p.add_argument("--node-where", default="auto",
                   help="NCM node-selection Where clause, e.g. \"(Vendor = 'Cisco')\". "
                        "Default auto: derived from the detected vendor.")
    p.add_argument("--config-type", default="Any",
                   help="config type the rules scan: Any, Running, Startup, ...")
    p.add_argument("--mode", choices=("manual", "heuristic"), default="manual",
                   help="manual: sentinel patterns, every rule flags for review (default). "
                        "heuristic: seed draft patterns from the STIG check text.")
    p.add_argument("--disabled", action="store_true",
                   help="create the NCM report with ReportStatus Disabled and skip "
                        "caching, so a large benchmark can be reviewed and tuned "
                        "before it starts evaluating")


def add_log_args(p):
    p.add_argument("--log-file", metavar="PATH",
                   help="write the run log here instead of the default location "
                        "(Windows: %%LOCALAPPDATA%%\\DisaStigTool\\logs; elsewhere "
                        "~/.local/state/disa-stig-tool/logs)")
    p.add_argument("--log-level", choices=("debug", "info", "warn"), default="info",
                   help="info (default) logs every decision and SWIS call; debug adds the "
                        "redacted request and response bodies (cut to 4 KB); warn keeps "
                        "only warnings and errors")


def add_connection_args(p):
    p.add_argument("--host", required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--ca-file", help="CA bundle that signs the SWIS certificate")
    p.add_argument("--pin-server-cert", action="store_true",
                   help="fetch the server's certificate (the stock self-signed "
                        "'SolarWinds-Orion' one), print its SHA-256 fingerprint, and "
                        "verify this session against exactly that certificate")
    p.add_argument("--insecure", action="store_true",
                   help="skip TLS verification (lab only)")




# ---------------------------------------------------------------------------
# The GUI
# ---------------------------------------------------------------------------
# tkinter ships with python.org and Windows-store Python; some minimal Linux
# installs lack it. The CLI must keep working there, so the import is guarded.

try:
    import tkinter as tk
    from tkinter import filedialog, ttk
    HAVE_TK = True
except ImportError:
    HAVE_TK = False

try:  # optional: drag-and-drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except ImportError:
    HAVE_DND = False


class WindowsAuthClient:
    """SWIS client that authenticates as the current Windows user (SSPI/Negotiate).

    Same query/invoke surface as SwisClient, carried by `requests` because
    the standard library cannot produce a Negotiate token.
    """

    def __init__(self, host, port, verify):
        try:
            import requests
            from requests_negotiate_sspi import HttpNegotiateAuth
        except ImportError as exc:
            raise SwisError(
                "Windows-user login needs the requests and requests-negotiate-sspi "
                "packages (Windows only):\n    pip install requests requests-negotiate-sspi"
            ) from exc
        self.base = f"https://{host}:{port}{BASE_PATH}"
        try:
            who = getpass.getuser()
        except Exception:   # getuser raises when no user name source exists
            who = "(unknown)"
        log_event("swis", f"SWIS endpoint {self.base} as the current Windows user '{who}' "
                          f"(Negotiate); TLS "
                          + ("verified against the system trust store" if verify
                             else "NOT verified (lab only)"))
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
            raise SwisError(f"HTTP {resp.status_code} from {path}\n{detail}")
        return resp.json() if resp.text.strip() else None

    def query(self, swql, parameters=None):
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        return (self._request("Query", body) or {}).get("results", [])

    def invoke(self, entity, verb, *args):
        return self._request(f"Invoke/{entity}/{verb}", list(args))


DISCLAIMER_TEXT = ("This is not built by SolarWinds Inc. or DISA. All Code is visible "
                   "for Code Audit and documentation is available for SWIS calls.")
ACK_TEXT = ("I Acknowledge that I will check the Reports Imported and Understand that "
            "DISA STIG Reports do not always include explicit instructions to resolve. "
            "Resolution falls on Agency application of the standards set by the "
            "DISA STIG System")

MAX_BATCH_FILES = 10
BTN_GREEN, BTN_YELLOW, BTN_RED = "#c6efce", "#ffeb9c", "#ffc7ce"


def file_module(path):
    """NCM or SCM for one file — the module a batch locks to."""
    if is_scm_path(path):
        load_scm_policy(path)   # refuses a JSON collection profile up front
        return "SCM"
    benchmarks = load_benchmarks(path)
    kind, _info = detect_target(benchmarks, os.path.basename(path))
    return "SCM" if kind == "server" else "NCM"


def show_disclaimer(root):
    """Startup gate: the acknowledgment checkbox must be ticked to proceed."""
    gate = tk.Toplevel(root)
    gate.title("DISA STIG Conversion Tool")
    gate.grab_set()
    gate.protocol("WM_DELETE_WINDOW", lambda: (result.update(ok=False), gate.destroy()))
    result = {"ok": False}
    frame = ttk.Frame(gate, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=DISCLAIMER_TEXT, wraplength=560,
              font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 12))
    acked = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text=ACK_TEXT, variable=acked,
                    command=lambda: proceed.configure(
                        state="normal" if acked.get() else "disabled")).pack(anchor="w")
    proceed = ttk.Button(frame, text="Proceed", state="disabled",
                         command=lambda: (result.update(ok=True), gate.destroy()))
    proceed.pack(anchor="e", pady=(16, 0))
    gate.wait_window()
    return result["ok"]


class App:
    def __init__(self, root, log_file=None):
        self.root = root
        self.log_file = log_file or log_path()
        root.title("DISA STIG Conversion Tool")
        root.minsize(760, 640)
        self.log_queue = queue.Queue()
        self.pinned_pem = None       # memory only, like the credentials
        self.batch_module = None     # locked to NCM or SCM by the first file

        pad = {"padx": 8, "pady": 3}
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
        self.port = tk.StringVar(value=str(DEFAULT_PORT))
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
        self.verify_tls = tk.BooleanVar(value=True)
        ttk.Checkbutton(conn, text="Verify TLS certificate (default)",
                        variable=self.verify_tls).grid(row=3, column=2, columnspan=2,
                                                       sticky="e", **pad)
        # live connection status, directly under the login controls
        self.conn_status = tk.StringVar(value="Connection: not tested")
        ttk.Label(conn, textvariable=self.conn_status).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(conn, text="Trust server certificate…",
                   command=self._on_pin_cert).grid(row=4, column=2, columnspan=2,
                                                   sticky="e", **pad)

        # --- files (up to MAX_BATCH_FILES; one module per batch) --------------
        src = ttk.LabelFrame(
            frame, text=f"STIG files (up to {MAX_BATCH_FILES} — one module per "
                        "batch: NCM or SCM, never both)", padding=8)
        src.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        src.columnconfigure(0, weight=1)
        self.file_list = tk.Listbox(src, height=5)
        self.file_list.grid(row=0, column=0, rowspan=3, sticky="ew", **pad)
        ttk.Button(src, text="Browse…", command=self._browse).grid(row=0, column=1, **pad)
        ttk.Button(src, text="Remove", command=self._remove_file).grid(row=1, column=1, **pad)
        ttk.Button(src, text="Clear", command=self._clear_files).grid(row=2, column=1, **pad)
        self.url = tk.StringVar()
        ttk.Entry(src, textvariable=self.url).grid(row=3, column=0, sticky="ew", **pad)
        ttk.Button(src, text="Add URL", command=self._add_url).grid(row=3, column=1, **pad)
        self.module_notice = tk.StringVar(
            value="Module: (select a file — the batch locks to NCM or SCM "
                  "based on the first file)")
        ttk.Label(src, textvariable=self.module_notice).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)

        # --- import options ---------------------------------------------------
        opts = ttk.LabelFrame(frame, text="Import options", padding=8)
        opts.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        opts.columnconfigure(1, weight=1)
        ttk.Label(opts, text="Compliance target").grid(row=0, column=0, sticky="w", **pad)
        self.target = tk.StringVar()
        target_box = ttk.Combobox(
            opts, textvariable=self.target, state="readonly", width=52,
            values=("Auto Compliance Assignment — route by file name / device type",
                    "Network Compliance — network devices only (NCM)",
                    "Server Compliance — server systems (SCM)"))
        target_box.current(0)
        target_box.grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(opts, text="NCM node scope").grid(row=1, column=0, sticky="w", **pad)
        self.node_where = tk.StringVar(value="(auto — from the detected vendor)")
        ttk.Entry(opts, textvariable=self.node_where).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Label(opts, text="NCM rule patterns").grid(row=2, column=0, sticky="w", **pad)
        self.mode = tk.StringVar(value="manual")
        box = ttk.Combobox(opts, textvariable=self.mode, state="readonly", width=52,
                           values=("manual — every rule flags for review (recommended)",
                                   "heuristic — draft patterns from the STIG check text"))
        box.current(0)
        box.grid(row=2, column=1, sticky="w", **pad)
        self.import_disabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, variable=self.import_disabled,
            text="Import the NCM report disabled (no caching) so it can be reviewed first"
        ).grid(row=3, column=1, sticky="w", **pad)

        # --- actions (tk.Buttons so completion colors show) -------------------
        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.test_btn = tk.Button(btns, text="Test Connection", command=self._on_test)
        self.test_btn.pack(side="left", padx=4)
        self.import_btn = tk.Button(btns, text="Import",
                                    command=lambda: self._on_batch(offline=False))
        self.import_btn.pack(side="left", padx=4)
        self.convert_btn = tk.Button(btns, text="Local File Conversion Only",
                                     command=lambda: self._on_batch(offline=True))
        self.convert_btn.pack(side="left", padx=4)
        self.details_btn = ttk.Button(btns, text="Show detailed log",
                                      command=self._toggle_details)
        self.details_btn.pack(side="right", padx=4)

        # --- summary (always visible) + auto-hidden detailed log --------------
        self.summary = tk.Text(frame, height=8, state="disabled", wrap="word")
        self.summary.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        self.summary.tag_configure("success", foreground="#1e7d32")
        self.summary.tag_configure("fail", foreground="#b00020")
        self.summary.tag_configure("warn", foreground="#8a6d00")
        frame.rowconfigure(4, weight=1)
        self.detail = tk.Text(frame, height=10, state="disabled", wrap="word")
        self.detail.grid(row=5, column=0, columnspan=2, sticky="nsew", **pad)
        self.detail.grid_remove()
        frame.rowconfigure(5, weight=1)
        # --- where the run log is written (the same file format as the CLI) ---
        ttk.Label(frame, text=f"Log file: {self.log_file or '(not written)'}").grid(
            row=6, column=0, columnspan=2, sticky="w", **pad)
        if self.log_file:
            self._summary_line(f"log file: {self.log_file}")

        self._toggle_auth()
        if HAVE_DND:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self._on_drop)
        root.after(150, self._drain_log)

    def _toggle_auth(self):
        state = "disabled" if self.win_auth.get() else "normal"
        self.user_entry.configure(state=state)
        self.pass_entry.configure(state=state)

    # ---- logging: colored summary, hidden detail -----------------------------

    def _append(self, widget, msg, tag=None):
        widget.configure(state="normal")
        if tag:
            widget.insert("end", redact(str(msg)) + "\n", tag)
        else:
            widget.insert("end", redact(str(msg)) + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _summary_line(self, msg, tag=None):
        log_event("gui", msg, {"fail": "error", "warn": "warn"}.get(tag, "info"))
        self.root.after(0, self._append, self.summary, msg, tag)

    def _log(self, msg):        # detailed log (worker threads use this)
        self.log_queue.put(redact(str(msg)))

    def _drain_log(self):
        try:
            while True:
                self._append(self.detail, self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log)

    def _toggle_details(self):
        if self.detail.winfo_viewable():
            self.detail.grid_remove()
            self.details_btn.configure(text="Show detailed log")
        else:
            self.detail.grid()
            self.details_btn.configure(text="Hide detailed log")

    def _show_issue(self):
        self.root.after(0, lambda: (self.detail.grid(),
                                    self.details_btn.configure(text="Hide detailed log")))

    def _set_button(self, btn, color):
        self.root.after(0, lambda: btn.configure(bg=color, activebackground=color))

    # ---- file batch ----------------------------------------------------------

    def _add_files(self, paths):
        for path in paths:
            if self.file_list.size() >= MAX_BATCH_FILES:
                self._summary_line(f"at most {MAX_BATCH_FILES} files per batch", "warn")
                return
            try:
                module = file_module(path)
            except (ValueError, OSError) as exc:
                self._summary_line(f"skipped {os.path.basename(path)}: {exc}", "fail")
                continue
            if self.batch_module is None:
                self.batch_module = module
                self.module_notice.set(f"Module: locked to {module} for this batch "
                                       "(from the first file selected)")
                self._summary_line(f"notice: this batch is now a {module} import")
            elif module != self.batch_module:
                self._summary_line(
                    f"skipped {os.path.basename(path)}: it is a {module} file, but this "
                    f"batch is locked to {self.batch_module} — run it in a separate batch",
                    "warn")
                continue
            self.file_list.insert("end", path)

    def _browse(self):
        paths = filedialog.askopenfilenames(
            title="Select STIG files",
            filetypes=[("STIG content", "*.zip *.xml *.xsl *.yaml *.yml *.scm-profile"),
                       # .scm-profile only for policy YAML from older builds; a JSON
                       # collection profile is refused when it is added.
                       ("All files", "*.*")])
        if paths:
            self._add_files(paths)

    def _remove_file(self):
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
        if self.file_list.size() == 0:
            self._clear_files()

    def _clear_files(self):
        self.file_list.delete(0, "end")
        self.batch_module = None
        self.module_notice.set("Module: (select a file — the batch locks to NCM or SCM "
                               "based on the first file)")

    def _on_drop(self, event):
        self._add_files([p for p in self.root.tk.splitlist(event.data)])

    def _add_url(self):
        url = self.url.get().strip()
        if not url:
            return
        def work():
            name = safe_file_name(os.path.basename(url.split("?")[0]) or "stig-download")
            dest = os.path.join(tempfile.gettempdir(), name)
            log_event("file", f"downloading {url} to {dest}")
            self._log(f"downloading {url} …")
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as out:
                while chunk := resp.read(1 << 16):
                    out.write(chunk)
            _bump("files_written")
            log_event("file", f"wrote {dest} ({os.path.getsize(dest)} bytes)")
            self._log(f"saved {dest} ({os.path.getsize(dest):,} bytes)")
            self.root.after(0, self._add_files, [dest])
        self._run_bg(work)

    # ---- shared helpers ------------------------------------------------------

    def _busy(self, working):
        state = "disabled" if working else "normal"
        for b in (self.test_btn, self.import_btn, self.convert_btn):
            b.configure(state=state)

    def _run_bg(self, fn):
        self._busy(True)
        def wrapper():
            try:
                fn()
            except Exception as exc:  # surfaced to the summary, never a crash
                self._summary_line(f"ERROR: {exc}", "fail")
                self._log(f"ERROR: {exc}")
                self._show_issue()
            finally:
                self.root.after(0, self._busy, False)
        threading.Thread(target=wrapper, daemon=True).start()

    def _client(self):
        host = self.host.get().strip()
        if not host:
            raise SwisError("enter the SolarWinds server IP/FQDN first")
        port = int(self.port.get().strip() or DEFAULT_PORT)
        verify = self.verify_tls.get()
        if self.win_auth.get():
            if self.pinned_pem:
                msg = ("note: certificate pinning applies to username/password "
                       "connections; the Windows-user login uses the system trust store")
                log_event("swis", msg, "warn")
                self._log(msg)
            return logged(WindowsAuthClient(host, port, verify))
        user = self.user.get().strip()
        if not user:
            raise SwisError("enter a username (or tick Windows-user login)")
        return logged(SwisClient(host, user, self.password.get(), port=port, verify=verify,
                                 pinned_pem=self.pinned_pem))

    def _target_choice(self):
        label = self.target.get()
        if label.startswith("Network"):
            return "network"
        if label.startswith("Server"):
            return "server"
        return "auto"

    def _on_pin_cert(self):
        def work():
            host = self.host.get().strip()
            if not host:
                raise SwisError("enter the SolarWinds server IP/FQDN first")
            port = int(self.port.get().strip() or DEFAULT_PORT)
            pem, fingerprint, stock = fetch_server_cert(host, port)
            log_event("swis", f"pinned the certificate {host}:{port} presents: SHA-256 "
                              f"{fingerprint}" + (" (stock SolarWinds-Orion)" if stock else ""))
            self.pinned_pem = pem  # memory only — dropped when the window closes
            note = " (stock SolarWinds-Orion certificate)" if stock else ""
            self._summary_line(f"trusted the certificate {host}:{port} presents — "
                               f"SHA-256 {fingerprint}{note}")
            self._log("this session now verifies against exactly that certificate")
        self._run_bg(work)

    # ---- actions --------------------------------------------------------------

    def _on_test(self):
        self.test_btn.configure(bg="SystemButtonFace" if sys.platform == "win32" else "#d9d9d9")
        self.conn_status.set("Connection: testing …")
        log_event("gui", "Test Connection pressed")
        def work():
            try:
                swis = self._client()
                rows = swis.query("SELECT TOP 1 EngineVersion FROM Orion.Engines")
            except SwisError as exc:
                self._set_button(self.test_btn, BTN_RED)
                self.conn_status.set("Connection: FAILED")
                self._summary_line(f"connection failed: {exc}", "fail")
                self._log(str(exc))
                self._show_issue()
                return
            problems = []
            version = rows[0]["EngineVersion"] if rows else "unknown"
            if not rows:
                problems.append("No data returned from the Orion.Engines query — "
                                "connected, but the account may lack read access")
            match = re.match(r"(\d+)", str(version))
            if match and int(match.group(1)) < 2023:
                problems.append(f"SWIS version mismatch: platform {version} predates "
                                "2023.1 — the REST port is 17778 there, not 17774")
            ncm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Cirrus.%'")[0]["C"]
            scm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Orion.PolicyEngine.%'")[0]["C"]
            if not ncm:
                problems.append("[NCM] Cirrus entities not present — NCM is not "
                                "installed or not readable by this account")
            if not scm:
                problems.append("[SCM] Orion.PolicyEngine entities not present — SCM is "
                                "not installed or not readable by this account")
            if problems:
                self._set_button(self.test_btn, BTN_YELLOW)
                self.conn_status.set(f"Connection: limited — platform {version} (see log)")
                self._summary_line(f"connected with limitations — platform {version}", "warn")
                for problem in problems:
                    log_event("swis", problem, "warn")
                    self._log(problem)
                self._show_issue()
            else:
                self._set_button(self.test_btn, BTN_GREEN)
                self.conn_status.set(f"Connection: OK — platform {version}")
                self._summary_line(f"connected — platform {version}; NCM present, "
                                   "SCM policy engine present", "success")
        self._run_bg(work)

    def _resolve_ncm_where(self, benchmarks, source_name):
        _kind, info, note = resolve_route(self._target_choice(), benchmarks,
                                          source_name, self.node_where.get().strip())
        self._log(note)
        return info

    def _on_batch(self, offline):
        btn = self.convert_btn if offline else self.import_btn
        btn.configure(bg="SystemButtonFace" if sys.platform == "win32" else "#d9d9d9")
        files = list(self.file_list.get(0, "end"))
        module = self.batch_module
        if not files:
            self._summary_line("select at least one file", "warn")
            return
        log_event("gui", f"{'Local File Conversion Only' if offline else 'Import'} pressed: "
                         f"{len(files)} {module} file(s): " + ", ".join(files))
        def work():
            swis = None if offline else self._client()
            ok = fail = 0
            for path in files:
                prefix = f"[{module}]"
                try:
                    if module == "SCM":
                        done = self._do_scm(swis, path, offline, prefix)
                    else:
                        done = self._do_ncm(swis, path, offline, prefix)
                    ok += 1 if done else 0
                    fail += 0 if done else 1
                except (SwisError, ValueError, OSError) as exc:
                    fail += 1
                    self._summary_line(f"{prefix} FAILED {os.path.basename(path)}: {exc}",
                                       "fail")
                    self._log(f"{prefix} {exc}")
                    self._show_issue()
            color = BTN_GREEN if fail == 0 else (BTN_YELLOW if ok else BTN_RED)
            self._set_button(btn, color)
            log_event("gui", f"batch finished: {ok} file(s) succeeded, {fail} failed",
                      "info" if fail == 0 else "warn")
            if self.log_file:
                self._summary_line(f"details are in the log file: {self.log_file}")
        self._run_bg(work)

    def _do_scm(self, swis, path, offline, prefix):
        if is_scm_path(path):
            if offline:
                self._summary_line(f"{prefix} {os.path.basename(path)} is already an "
                                   "importable SCM policy — nothing to convert")
                return True
            policy_id, name = import_scm_policy(swis, load_scm_policy(path, log=self._log),
                                                log=self._log)
            self._summary_line(f"SUCCESS {prefix} \"{name}\" (PolicyID {policy_id})",
                               "success")
            return True
        folder = os.path.dirname(path) if os.access(os.path.dirname(path) or ".",
                                                    os.W_OK) else tempfile.gettempdir()
        for b in load_benchmarks(path):
            if offline:
                out = os.path.join(folder, scm_policy_filename(b))
                write_text_file(out, xccdf_to_scm_yaml(b), newline=None)
                self._summary_line(f"SUCCESS {prefix} wrote {os.path.basename(out)} — "
                                   f"{len(b['rules'])} rules", "success")
            else:
                policy_id, name = import_scm_policy(swis, xccdf_to_scm_yaml(b),
                                                    log=self._log)
                self._summary_line(f"SUCCESS {prefix} \"{name}\" "
                                   f"(PolicyID {policy_id}) — {len(b['rules'])} "
                                   "manual-review rules", "success")
        return True

    def _do_ncm(self, swis, path, offline, prefix):
        benchmarks = load_benchmarks(path)
        info = self._resolve_ncm_where(benchmarks, os.path.basename(path))
        if not isinstance(info, str):   # forced-server info tuple can't reach here
            info = node_where_for(None)
        warning = xml_config_warning(info)
        if warning:
            self._summary_line(f"{prefix} {warning}", "warn")
            self._show_issue()
        mode = "heuristic" if self.mode.get().startswith("heuristic") else "manual"
        enabled = not self.import_disabled.get()
        reports = build_reports(benchmarks, node_where=info, mode=mode,
                                source_path=os.path.basename(path), enabled=enabled)
        folder = os.path.dirname(path) if os.access(os.path.dirname(path) or ".",
                                                    os.W_OK) else tempfile.gettempdir()
        if offline:
            for report in reports:
                out = write_console_file(report, folder)
                n_rules = sum(len(p["AssignedPolicyRules"])
                              for p in report["AssignedPolicies"])
                self._summary_line(f"SUCCESS {prefix} wrote {os.path.basename(out)} — "
                                   f"{n_rules} rules", "success")
            return True
        for report in reports:
            existing = swis.query(
                "SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                {"n": report["Name"]})
            if existing:
                raise SwisError(f"a report named \"{report['Name']}\" already exists — "
                                "delete or rename it first; this tool never overwrites")
        imported, failure, remaining = import_ncm_reports(swis, reports, log=self._log)
        for report, _new_id, n_rul in imported:
            self._summary_line(f"SUCCESS {prefix} \"{report['Name']}\" — {n_rul} rules",
                               "success")
        # Reports verified before a failure are still cached or disabled.
        confirmed = finish_ncm_imports(swis, [i for _r, i, _n in imported],
                                       disabled=not enabled,
                                       log=lambda m: self._log(f"{prefix} {m}"))
        if not confirmed:
            self._summary_line(f"{prefix} ReportStatus could not be confirmed as "
                               "Disabled; see the detailed log", "warn")
            self._show_issue()
        if failure is None:
            return confirmed
        if isinstance(failure, NcmWireError):
            self._summary_line(f"{prefix} {failure}", "warn")
            for rep in remaining:
                self._summary_line(
                    f"{prefix} wrote {os.path.basename(write_console_file(rep, folder))} "
                    "— import it via Compliance → Manage Policy Reports → Import",
                    "warn")
            self._show_issue()
            return False
        if imported:
            self._summary_line(f"{prefix} {len(imported)} report(s) were imported before "
                               "the failure and remain on the server", "warn")
        raise failure


def run_gui():
    if not HAVE_TK:
        sys.exit("could not start the GUI: tkinter is not installed for this Python.\n"
                 "Install it (Windows/macOS installers include it; Debian/Ubuntu: "
                 "apt install python3-tk) or use the CLI: python disa_stig_tool.py --help")
    root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    root.withdraw()
    accepted = show_disclaimer(root)
    if not accepted:
        log_event("gui", "the disclaimer was not acknowledged; the GUI closed")
        root.destroy()
        return
    log_event("gui", "disclaimer acknowledged; main window opened")
    root.deiconify()
    App(root, log_path())
    root.mainloop()
    log_event("gui", "main window closed")


def configure_console_streams(streams=None):
    """Make printing robust on a Windows console or a redirected stream.

    A redirected stdout on Windows defaults to the ANSI code page (cp1252), which
    cannot encode the arrows, dashes and bullets that STIG titles and this tool's
    messages carry, and an unencodable character raises UnicodeEncodeError and
    kills the command. Re-encode as UTF-8 and replace anything that still cannot
    be written, where the stream supports reconfigure() (Python 3.7+).
    """
    for stream in streams if streams is not None else (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, io.UnsupportedOperation):
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError, io.UnsupportedOperation):
                pass


def build_parser():
    """The CLI. Help text is kept ASCII so it prints on any console code page."""
    top = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = top.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="fetch a STIG package zip from DISA's public mirror")
    d.add_argument("package", help="package name (e.g. U_Cisco_IOS_Router_Y26M07_STIG) or full URL")
    d.add_argument("--dir", default=".", help="directory to save into")
    add_log_args(d)

    pp = sub.add_parser("parse", help="show what a STIG package contains")
    pp.add_argument("path", help="STIG zip, directory, *-xccdf.xml file, or SCM policy .yaml")
    pp.add_argument("--rules", action="store_true", help="list every rule")
    add_log_args(pp)

    for alias in ("build", "convert"):
        b = sub.add_parser(alias, help="offline conversion, no server needed: write "
                           "console-importable files (NCM .ncm-report.xml / SCM "
                           ".scm-policy.yaml)")
        add_source_args(b)
        b.add_argument("-o", "--output", help="output file (single-benchmark sources only)")
        add_log_args(b)

    imp = sub.add_parser("import", help="import into NCM via SWIS and start caching")
    add_source_args(imp)
    add_connection_args(imp)
    imp.add_argument("--no-cache", action="store_true",
                     help="import but do not start compliance caching")
    imp.add_argument("--no-rollback", action="store_true",
                     help="on a failed import, leave the rules and policies it "
                          "already created on the server instead of deleting them")
    add_log_args(imp)

    tst = sub.add_parser("test", help="evaluate the generated rules against a real "
                                      "config, server side, without importing anything")
    add_source_args(tst)
    add_connection_args(tst)
    tst.add_argument("--config-file", help="a device configuration saved to a local file")
    tst.add_argument("--config-id",
                     help="ConfigID of a config NCM already holds (SELECT ConfigID, "
                          "NodeID, ConfigType, DownloadTime FROM NCM.ConfigArchive). "
                          "This route resolves NCM macros; pasted text does not.")
    tst.add_argument("--limit", type=int, default=10,
                     help="how many rules to test (default 10, 0 for all)")
    add_log_args(tst)

    rm = sub.add_parser("remove", help="delete an imported policy report by name, with "
                                       "its policies and rules unless another report "
                                       "or policy still uses them")
    add_connection_args(rm)
    rm.add_argument("--name", required=True, help="exact report name")
    rm.add_argument("--dry-run", action="store_true",
                    help="print what would be deleted and kept, delete nothing")
    rm.add_argument("--delete-children", action="store_true",
                    help="deprecated and ignored: remove always deletes the report's "
                         "unshared policies and rules, and never shared ones")
    rm.add_argument("--yes", action="store_true", help="confirm the deletion")
    add_log_args(rm)
    return top


def build_gui_parser():
    """``disa_stig_tool.py gui [--log-file PATH] [--log-level LEVEL]``."""
    g = argparse.ArgumentParser(prog="disa_stig_tool.py gui",
                                description="open the GUI (the same as no arguments)")
    add_log_args(g)
    return g


def _announce_log(path):
    """Print the log path (stderr keeps stdout exactly as it was)."""
    print(f"log file: {path}", file=sys.stderr)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    # Registered before anything is logged, so the start-of-run command line and
    # every later line are redacted even when the password was never used.
    register_secret(os.environ.get("SWIS_PASSWORD"))
    # No arguments (a double-click on Windows) or an explicit "gui" opens the GUI.
    if not argv or argv[0] == "gui":
        gui_args = build_gui_parser().parse_args(argv[1:])
        path = setup_logging(gui_args.log_file, gui_args.log_level)
        _announce_log(path)
        log_run_start(argv, mode="gui")
        code = 0
        try:
            run_gui()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if isinstance(exc.code, str):
                log_event("main", exc.code, "error")
            raise
        except Exception as exc:
            code = 1
            log_event("main", f"unexpected error: {exc!r}", "error")
            raise
        finally:
            log_run_end(code)
            _announce_log(path)
            close_logging()
        return
    configure_console_streams()
    args = build_parser().parse_args(argv)
    path = setup_logging(args.log_file, args.log_level)
    _announce_log(path)
    log_run_start(argv)
    code = 0
    try:
        {"download": cmd_download, "parse": cmd_parse, "build": cmd_build,
         "convert": cmd_build, "import": cmd_import, "test": cmd_test,
         "remove": cmd_remove}[args.cmd](args)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if isinstance(exc.code, str):
            log_event("main", exc.code, "error")
        raise
    except (ValueError, OSError, SwisError) as exc:
        code = 1
        log_event("main", f"error: {exc}", "error")
        sys.exit(redact(f"error: {exc}"))
    except Exception as exc:
        code = 1
        log_event("main", f"unexpected error: {exc!r}", "error")
        raise
    finally:
        log_run_end(code)
        _announce_log(path)
        close_logging()


if __name__ == "__main__":
    main()
