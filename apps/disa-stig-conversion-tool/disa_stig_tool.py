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

Every report, policy and SCM policy name ends in a version suffix (--suffix, _v1 by
default) that also seeds every generated id, so a new STIG release imports alongside the
old one with --suffix _v2; a name or id that already exists refuses the run before
anything is written, naming the next free suffix. Network STIGs are scoped by Vendor,
and Cisco ones also by a MachineType pattern per platform (IOS-XE, IOS-XR, NX-OS, ASA,
IOS; Tentative: the MachineType values are still to be verified against a live server).
An unrecognized network STIG is refused unless --vendor or --node-where is given.

Endpoint facts (SWIS REST on port 17774, platform 2023.1+) and the compliance verb
contract are documented in docs/modules/ncm-compliance-reports.md of this repository
and verified against 2026.2.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import http.client
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


# ---------------------------------------------------------------------------
# Version suffix: every name and every generated id carries it
# ---------------------------------------------------------------------------
#
# Since 2.0.0 every NCM report name, NCM policy name and SCM policy name ends in a
# version suffix (_v1 by default), and the same suffix is part of the uuid5 seed of
# every generated id: the NCM PolicyId and RuleIds, and the SCM policy uniqueId and
# rule uniqueIds. Importing a new STIG release next to the old one with --suffix _v2
# therefore produces entirely fresh names and ids, so nothing is shared with the _v1
# import and removing _v1 afterwards cannot touch the _v2 objects. The PowerShell
# edition uses the same seeds and the same names (Get-SuffixedName).

DEFAULT_SUFFIX = "_v1"
SUFFIX_PATTERN = re.compile(r"^_v[0-9]+\Z")
SUFFIX_TAIL = re.compile(r"_v([0-9]+)\Z")
NAME_LIMIT = 250


def validate_suffix(suffix):
    """The suffix to use, or ValueError. None or empty means the default (_v1)."""
    suffix = str(suffix) if suffix else DEFAULT_SUFFIX
    if not SUFFIX_PATTERN.match(suffix):
        raise ValueError(f"--suffix {suffix!r} is not valid: it must be _v followed by digits "
                         "(_v1, _v2, ...)")
    return suffix


def with_suffix(name, suffix, limit=NAME_LIMIT):
    """``name`` cut so that ``name + suffix`` fits ``limit`` characters, then the suffix.

    The suffix is never the part that is cut, so every generated name ends in it and
    the base can be recovered for the collision check (strip_suffix)."""
    return (name or "")[:max(0, limit - len(suffix))] + suffix


def strip_suffix(name):
    """(base, n) for a name ending in _v<n>, else (name, None)."""
    m = SUFFIX_TAIL.search(name or "")
    if not m:
        return name or "", None
    return name[:m.start()], int(m.group(1))


def next_free_suffix(existing_names, base, current_suffix):
    """The suffix to suggest after a collision: one above the highest _v<n> that any
    existing name ``base + _v<n>`` carries, and above the suffix that collided."""
    highest = int(current_suffix[2:])
    for name in existing_names:
        stem, n = strip_suffix(str(name or ""))
        if n is not None and stem == base:
            highest = max(highest, n)
    return f"_v{highest + 1}"


# Config lines in IOS/NX-OS/JunOS check text tend to open with one of these tokens.
# Used only by --mode heuristic to seed a draft pattern.
CONFIG_TOKENS = (
    "aaa ", "ip ", "ipv6 ", "line ", "snmp-server ", "ntp ", "logging ", "login ",
    "banner ", "crypto ", "interface ", "router ", "access-list ", "username ",
    "service ", "no ", "hostname ", "enable ", "archive", "clock ", "boot ",
)


class SwisError(RuntimeError):
    """A SWIS request failed. Carries the server's message where one was returned."""


class NcmVerificationError(SwisError):
    """The GetPolicyReport read-back did not match what the import submitted."""


class InIdsProbeError(SwisError):
    """An `IN @ids` query over GUIDs did not return the one row known to exist, so no
    decision (rollback, removal, the existing-id snapshot) may be based on it."""


# Failures below the SWIS contract, with no HTTP status: a timeout, a refused or reset
# connection, a TLS failure, a truncated response, or a body that is not JSON.
# requests' exceptions derive from OSError (IOError), so the Windows-login client is
# covered too. Each is re-raised as SwisError carrying the original type and message.
TRANSPORT_ERRORS = (OSError, http.client.HTTPException, json.JSONDecodeError)


def transport_error(exc, label):
    """A SwisError for a transport failure, keeping the original type and message."""
    return SwisError(f"transport error calling {label}: {type(exc).__name__}: {exc}")


def http_status(exc_or_text):
    """The HTTP status a SwisError message names (``HTTP 403 from ...``), or None."""
    m = re.search(r"\bHTTP (\d{3})\b", str(exc_or_text))
    return int(m.group(1)) if m else None


# The two HTTP 400 rejections docs/modules/ncm-compliance-reports.md records for the
# NCM contract types over JSON REST (a field observation on 2026.2.2): "Value cannot be
# null. Parameter name: input" (a JSON object handed to an XML reader) and "Verb ...
# cannot unpackage parameter 0" (XML the DataContractSerializer refused). Only these
# mean "this wire format was refused, try the next one". Any other 400, and every 401,
# 403, 409 or 500, stops that report with the server's message, rolls back what it
# created, and writes no console file that would suggest a format problem.
# Unverified: a server on another .NET runtime may word the null-argument rejection
# differently ("Value cannot be null. (Parameter 'input')"); such a message is treated
# as an undocumented 400, which stops the report rather than guessing.
WIRE_REJECTION_PATTERNS = (
    re.compile(r"Value cannot be null\.?\s*Parameter name:\s*input", re.IGNORECASE),
    re.compile(r"\bcannot unpackage parameter \d+", re.IGNORECASE),
)


def is_wire_rejection(exc_or_text):
    """True only for an HTTP 400 carrying one of the documented rejection texts."""
    text = str(exc_or_text)
    return http_status(text) == 400 and any(p.search(text) for p in WIRE_REJECTION_PATTERNS)


# The NCM role each Cirrus.PolicyReports verb this tool calls needs, from the verb
# descriptions in the 2026.2 schema (python tools/schema_query.py verb Cirrus.PolicyReports
# <verb>). When the server's "compliance only for administrators" option is on, every
# one of them is valid only for Orion administrators instead.
NCM_VERB_ROLES = (
    ("WebDownloader", ("AddPolicyRule", "AddPolicy", "AddPolicyReport", "GetPolicyReport",
                       "DeletePolicyRules", "DeletePolicies", "DeletePolicyReports",
                       "TestRule", "TestRuleOnBackedUpConfig")),
    ("WebUploader", ("StartCaching", "UpdateReportStatus")),
)
ROLE_HINT = ("Check that the account has at least the WebDownloader NCM role (WebUploader for "
             "StartCaching and UpdateReportStatus), or is an Orion administrator when the "
             "server restricts compliance to administrators.")


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
        except TRANSPORT_ERRORS as exc:
            # A read timeout, a reset connection, a truncated or non-JSON body.
            raise transport_error(exc, url) from exc

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
    follow, cut to LOG_BODY_LIMIT characters.

    A transport failure from the wrapped client (a timeout, a reset connection, a
    requests exception, a body that is not JSON) is re-raised as SwisError with the
    original type and message, so every caller handles one error type."""

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
            transport = isinstance(exc, TRANSPORT_ERRORS) and not isinstance(exc, SwisError)
            kind = f"{type(exc).__name__}: " if not isinstance(exc, SwisError) else ""
            log_event("swis", f"{label} -> error {elapsed} ms: {kind}{exc}", "warn")
            if transport:
                raise transport_error(exc, _one_line(label, 120)) from exc
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


# The SCM probe per OS family. Every family uses the same manual-review attestation
# today: a !scm.powershell source whose script is a single-quoted Write-Host literal
# (see scm_probe_id and ps_single_quote). Windows is the source type SolarWinds' own
# shipped STIG policies use (docs/modules/scm-compliance-policies.md). Linux STIGs
# also route to SCM and get the same probe, but that is Unverified: this repository
# documents no SCM policy source for Linux nodes, and SolarWinds' SCM documentation
# is understood to treat script data sources on Linux as unsupported, so the rule may
# report an error or Unknown there instead of failed. --scm-probe-template replaces
# the source block per run so another source type can be tried without code changes;
# README "Testing Linux STIGs in SCM" says what to check.
SCM_PROBES = {
    "windows": {"tag": "!scm.powershell", "verified": True,
                "label": "!scm.powershell Write-Host attestation (the source type "
                         "SolarWinds' shipped Windows STIG policies use)"},
    "linux": {"tag": "!scm.powershell", "verified": False,
              "label": "!scm.powershell Write-Host attestation (Unverified on Linux nodes)"},
}
LINUX_PROBE_WARNING = (
    "Linux STIG routed to SCM: the generated probe is !scm.powershell, which is Unverified on "
    "Linux nodes (no SCM policy source for Linux is documented in this repository, and script "
    "data sources on Linux are understood to be unsupported), so its rules may report an error "
    "or Unknown rather than failed. Import one policy, assign it to one test node and check it "
    "as README.md 'Testing Linux STIGs in SCM' describes; --scm-probe-template FILE tries "
    "another source type.")
PROBE_TEMPLATE_MAX = 4096
_TEMPLATE_TAG = re.compile(r"^!scm\.[A-Za-z][A-Za-z0-9_.]*\Z")
_TEMPLATE_LINE = re.compile(r"^( *)([A-Za-z_][A-Za-z0-9_-]*):(?: (.*))?\Z")
_TEMPLATE_DQ = re.compile(r'^"(?:[^"\\\x00-\x1f]|\\[^\x00-\x1f])*"\Z')
_TEMPLATE_SQ = re.compile(r"^'(?:[^'\x00-\x1f]|'')*'\Z")
_TEMPLATE_PLAIN = re.compile(r"^[A-Za-z0-9_./\\$(][^#\x00-\x1f]*\Z")


def os_family(os_info):
    """'windows', 'linux' or 'unknown' for the os_info tuple detect_target returns."""
    return os_info[2] if os_info and len(os_info) > 2 else "unknown"


def parse_probe_template(text, source="template"):
    """Validate an --scm-probe-template file and return its lines, ready to indent.

    The file is a YAML fragment: the source tag on the first line (``!scm.<type>``),
    then the source's mapping, one ``key: value`` per line, nested by spaces. It may
    use ``{id}``, which becomes the validated probe id (scm_probe_id: V-<n>, or the id
    reduced to [A-Za-z0-9._-]); never raw STIG text. ``{id}`` is accepted only inside
    a quoted scalar ("..." or '...'), where those characters cannot end the string,
    start a new key or change the PowerShell quoting inside it. Anything else
    (sequences, anchors, block scalars, flow collections, tabs, a placeholder in a key
    or a plain value) is refused with ValueError, before any file is written.
    """
    if len(text.encode("utf-8")) > PROBE_TEMPLATE_MAX:
        raise ValueError(f"{source}: the probe template is larger than {PROBE_TEMPLATE_MAX} bytes")
    lines = [line.rstrip() for line in text.lstrip("﻿").replace("\r\n", "\n")
             .replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError(f"{source}: the probe template is empty")
    if "\t" in "".join(lines):
        raise ValueError(f"{source}: tabs are not allowed in the probe template (YAML indents "
                         "with spaces)")
    if not _TEMPLATE_TAG.match(lines[0]):
        raise ValueError(f"{source}: the probe template must start with an SCM source tag on its "
                         f"own line, such as !scm.powershell (found {lines[0][:60]!r})")
    if "{id}" in lines[0]:
        raise ValueError(f"{source}: {{id}} is not allowed in the source tag")
    levels = [0]
    opened = False        # the previous key had no value, so a deeper level may follow
    for number, line in enumerate(lines[1:], 2):
        m = _TEMPLATE_LINE.match(line)
        if not m:
            raise ValueError(f"{source}: line {number} is not a 'key: value' mapping line "
                             f"({line.strip()[:60]!r}); sequences, anchors and flow "
                             "collections are not supported")
        indent, key, value = len(m.group(1)), m.group(2), (m.group(3) or "").strip()
        if opened and indent > levels[-1]:
            levels.append(indent)
        elif indent in levels:
            del levels[levels.index(indent) + 1:]
        else:
            raise ValueError(f"{source}: line {number} is indented inconsistently")
        if "{id}" in key:
            raise ValueError(f"{source}: line {number}: {{id}} is not allowed in a key")
        opened = not value
        if not value:
            continue
        if _TEMPLATE_DQ.match(value) or _TEMPLATE_SQ.match(value):
            if "\\{id}" in value:
                raise ValueError(f"{source}: line {number}: a backslash directly before {{id}} "
                                 "would turn the id into an escape sequence")
            continue
        if "{id}" in value:
            raise ValueError(f"{source}: line {number}: {{id}} is only allowed inside a quoted "
                             "string (\"...\" or '...')")
        if not _TEMPLATE_PLAIN.match(value) or ": " in value or value.endswith(":"):
            raise ValueError(f"{source}: line {number}: the value {value[:60]!r} is neither a "
                             "quoted string nor a plain scalar this tool accepts")
    if opened:
        raise ValueError(f"{source}: the last key has no value")
    return lines


def load_probe_template(path):
    """Read and validate --scm-probe-template; returns its lines (parse_probe_template)."""
    with open(path, "rb") as fh:
        raw = fh.read(PROBE_TEMPLATE_MAX + 1)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path}: the probe template is not UTF-8 ({exc})") from exc
    lines = parse_probe_template(text, path)
    uses_id = any("{id}" in line for line in lines)
    log_event("scm", f"probe template {path}: source {lines[0]}, {len(lines) - 1} mapping "
                     f"line(s), {{id}} {'used' if uses_id else 'not used'}")
    if not uses_id:
        log_event("scm", f"probe template {path} does not use {{id}}, so every rule collects the "
                         "same value; the expression '<id> reviewed: True' still never matches",
                  "warn")
    return lines


def scm_probe_lines(probe_id, stig_id, template=None):
    """The ``source:`` block of one generated rule, indented for the rule's condition."""
    if template:
        out = [f"    source: {template[0]}"]
        out += ["      " + line.replace("{id}", probe_id) for line in template[1:]]
        return out
    probe = "Write-Host " + ps_single_quote(f"{probe_id} reviewed: False")
    return [
        "    source: !scm.powershell",
        f"      description: {_yq('STIG ' + stig_id + ' manual-review attestation')}",
        f"      script: {_yq(probe)}",
    ]


def log_scm_probe_plan(family, template=None, template_path=None, log=None):
    """One log line for the OS detected and the probe used; a WARN for Linux."""
    probe = (f"template {template_path or '(given)'} ({template[0]})" if template
             else SCM_PROBES.get(family, SCM_PROBES["windows"])["label"])
    log_event("scm", f"SCM probe: OS family {family}; probe {probe}")
    if family == "unknown" and not template:
        log_event("scm", "the OS was not recognized from the file or benchmark names; the "
                         "Windows probe is used", "warn")
    if family == "linux":
        _say(log, "scm", "warning: " + LINUX_PROBE_WARNING, "warn")


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
            base, n = strip_suffix(info["name"])
            if n is not None:
                msg += " " + suffix_advice(swis, [("Orion.PolicyEngine.Policy", base)], f"_v{n}")
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


def ncm_rule_id(rule, suffix=DEFAULT_SUFFIX):
    # "stig2ncm:" is the historic namespace string; the suffix (2.0.0) makes every
    # suffix a fresh set of ids. The PowerShell edition derives the same value.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm:" + rule["rule_id"] + suffix))


def ncm_policy_id(benchmark, suffix=DEFAULT_SUFFIX):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-policy:"
                          + (benchmark["benchmark_id"] or benchmark["title"]) + suffix))


def rule_object(rule, grouping, mode, suffix=DEFAULT_SUFFIX):
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
        "RuleId": ncm_rule_id(rule, suffix),
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


_PICKER_VENDOR = re.compile(r"\bVendor\s*(?:=|LIKE)\s*'((?:[^']|'')*)'", re.IGNORECASE)


def picker_vendor(where):
    """The Vendor value a WHERE fragment compares with ('' doubled quotes undone, one
    leading and trailing % dropped), or None when there is none to show in the picker."""
    m = _PICKER_VENDOR.search(where or "")
    if not m:
        return None
    value = m.group(1).replace("''", "'")
    value = value[1:] if value.startswith("%") else value
    value = value[:-1] if value.endswith("%") else value
    return value if value and "%" not in value else None


def xml_text(value):
    """Escape a value for XML element text (&, <, >), as XmlSerializer writes it."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
    # The picker state is Vendor-only by design: a MachineType condition (the Cisco
    # platform scope) lives in the SQL part alone, which is what NCM filters on.
    vendor = picker_vendor(where)
    criteria = ""
    if vendor:
        criteria = (
            '<?xml version="1.0" encoding="utf-16"?>\n'
            '<ArrayOfWebSelectionCriteria xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            "  <WebSelectionCriteria>\n"
            f"    <Id>{uuid.uuid5(uuid.NAMESPACE_URL, 'stig2ncm-criteria:' + vendor)}</Id>\n"
            "    <LogicalCondition />\n"
            "    <SelectedColumn>Vendor</SelectedColumn>\n"
            "    <MatchType>=</MatchType>\n"
            f"    <SelectedValue>{xml_text(vendor)}</SelectedValue>\n"
            "  </WebSelectionCriteria>\n"
            "</ArrayOfWebSelectionCriteria>")
    return f"WebCriteria:{criteria}SQL:Where {where} "


def build_reports(benchmarks, name=None, grouping="DISA STIG", node_where="(Vendor = 'Cisco')",
                  config_type="Any", mode="manual", source_path=None, enabled=True,
                  suffix=DEFAULT_SUFFIX):
    """Assemble one PolicyReport contract object per benchmark.

    ``suffix`` (validated, _v1 by default) ends every report and policy name and is
    part of the PolicyId and RuleId seeds, so another suffix yields fresh ids.

    Matching how the console's own exports are structured (one policy per
    report): each benchmark in the package becomes its own report — the Cisco
    IOS Router package yields an NDM report (35 rules) and an RTR report
    (92 rules) — whose single policy carries the device scope and joins the
    report to its rules.
    """
    suffix = validate_suffix(suffix)
    if name is None and source_path and source_path.lower().endswith(".zip"):
        name = os.path.splitext(os.path.basename(source_path))[0]
    reports = []
    for b in benchmarks:
        policy_group = f"{grouping}/{b['benchmark_id']}" if b["benchmark_id"] else grouping
        rules = [rule_object(r, policy_group, mode, suffix) for r in b["rules"]]
        policy = {
            "PolicyId": ncm_policy_id(b, suffix),
            "PolicyName": with_suffix(f"{b['title']} V{b['version']} ({b['release']})", suffix),
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
            "Name": with_suffix(report_name, suffix),
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
                           f"{config_type}, grouping {policy_group}, suffix {suffix}")
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


def _row_value(row, column):
    """One column of a SWQL result row, or None when the row is not an object."""
    return row.get(column) if isinstance(row, dict) else None


# `IN @ids` with a JSON array is how this tool reads sets of GUIDs back (the rollback
# snapshot, the removal plan, the delete read-back). docs/swis/rest-api.md documents the
# array binding with integers; whether every server binds an array of GUID strings the
# same way is Unverified. A server that silently matched nothing would make the snapshot
# say "nothing existed before" (so a rollback could delete an earlier import's rules) and
# make a removal plan say "nothing is shared". So before any such decision the same query
# is run for one id known to exist, and exactly one matching row is required.
IN_IDS_PROBES = {
    "report": ("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids",
               "PolicyReportID"),
    "policy": ("SELECT PolicyID FROM Cirrus.Policies WHERE PolicyID IN @ids", "PolicyID"),
    "rule": ("SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids",
             "PolicyRuleID"),
}


def confirm_in_ids(swis, kind, known_id, purpose, component="import"):
    """Require ``IN @ids`` to return exactly the one ``kind`` row ``known_id`` names.

    Raises InIdsProbeError (nothing is deleted or decided) when it does not.
    """
    swql, column = IN_IDS_PROBES[kind]
    rows = swis.query(swql, {"ids": [known_id]})
    rows = rows if isinstance(rows, list) else []
    matches = [r for r in rows if _norm_id(_row_value(r, column)) == _norm_id(known_id)]
    if len(rows) != 1 or len(matches) != 1:
        msg = (f"IN @ids sanity probe failed before {purpose}: querying the {kind} {known_id}, "
               f"which is known to exist, returned {len(rows)} row(s) instead of exactly 1. "
               "This server does not bind a GUID array to IN @ids the way the tool expects, so a "
               "decision based on it could delete the wrong objects; stopping instead. "
               "Nothing was deleted by this step.")
        log_event(component, msg, "error")
        raise InIdsProbeError(msg)
    log_event(component, f"IN @ids sanity probe ok before {purpose}: the {kind} {known_id} "
                         "returned exactly one row")


def existing_ncm_ids(swis, report):
    """Which of the RuleIds/PolicyIds this report would submit already exist.

    RuleIds are uuid5-derived from the DISA rule id, so a second import of the
    same STIG release submits the same ids an earlier import did. A rollback must
    not delete those earlier objects, so they are recorded before anything is
    created. Unverified: whether AddPolicyRule/AddPolicy honour a submitted id or
    always assign a fresh one is not documented; the returned id is used either
    way, and this snapshot only matters when it equals an existing one.

    Each lookup is preceded by the IN @ids sanity probe on one row known to exist
    (the first one SELECT TOP 1 returns); an empty table needs no lookup at all.
    """
    rule_ids = [r["RuleId"] for p in report["AssignedPolicies"]
                for r in p["AssignedPolicyRules"]]
    policy_ids = [p["PolicyId"] for p in report["AssignedPolicies"] if p.get("PolicyId")]
    found = {}
    for kind, ids, sample_swql in (
            ("rule", rule_ids, "SELECT TOP 1 PolicyRuleID FROM Cirrus.PolicyRules"),
            ("policy", policy_ids, "SELECT TOP 1 PolicyID FROM Cirrus.Policies")):
        swql, column = IN_IDS_PROBES[kind]
        found[kind] = set()
        if not ids:
            continue
        sample = swis.query(sample_swql)
        known = _row_value(sample[0], column) if isinstance(sample, list) and sample else None
        if not known:
            log_event("import", f"the server returned no {kind} rows, so none of the "
                                f"{len(ids)} submitted {kind} id(s) can already exist")
            continue
        confirm_in_ids(swis, kind, known, f"the existing-{kind}-id snapshot")
        found[kind] = {_norm_id(_row_value(row, column)) for row in _query_ids(swis, swql, ids)}
    return {"rules": found["rule"], "policies": found["policy"]}


def expected_tree(report):
    """[(policy name, [rule names])] for what an import submits, in document order."""
    return [(str(p.get("PolicyName") or ""),
             [str(r.get("RuleName") or "") for r in p.get("AssignedPolicyRules") or []])
            for p in report.get("AssignedPolicies") or []]


def read_back_tree(stored):
    """The same shape from a GetPolicyReport(id, true) result, or None when it cannot
    be compared: not an object, an entry that is not an object, or the nested
    AssignedPolicies absent while AssignedPoliciesList names policies (the tree was
    not returned, which is not the same as an empty report)."""
    if not isinstance(stored, dict):
        return None
    policies = stored.get("AssignedPolicies")
    if not isinstance(policies, list):
        listed = stored.get("AssignedPoliciesList")
        return None if isinstance(listed, list) and listed else []
    tree = []
    for p in policies:
        if not isinstance(p, dict):
            return None
        rules = p.get("AssignedPolicyRules") or []
        if not isinstance(rules, list) or not all(isinstance(r, dict) for r in rules):
            return None
        tree.append((str(p.get("PolicyName") or ""), [str(r.get("RuleName") or "") for r in rules]))
    return tree


def compare_report_trees(expected, actual):
    """Differences between the submitted tree and the stored one: policy count, rule
    count, and per-policy rule names (the comparison Porter 0.3.0 makes). Empty means
    they match. The PowerShell edition's Compare-NcmReportTree returns the same text."""
    diffs = []
    n_expected = sum(len(rules) for _p, rules in expected)
    n_actual = sum(len(rules) for _p, rules in actual)
    if len(expected) != len(actual):
        diffs.append(f"policies: expected {len(expected)}, stored {len(actual)}")
    if n_expected != n_actual:
        diffs.append(f"rules: expected {n_expected}, stored {n_actual}")
    stored = {}
    for policy, rules in actual:
        stored.setdefault(policy, []).append(rules)
    for policy, rules in expected:
        candidates = stored.get(policy)
        if not candidates:
            diffs.append(f"policy \"{policy}\" missing")
            continue
        match = candidates.pop(0)
        have = set(match)
        missing = list(dict.fromkeys(r for r in rules if r not in have))
        if len(match) != len(rules) or missing:
            text = f"policy \"{policy}\": expected {len(rules)} rules, stored {len(match)}"
            if missing:
                text += (" (missing \"" + "\", \"".join(missing[:3]) + "\""
                         + (", ..." if len(missing) > 3 else "") + ")")
            diffs.append(text)
    return diffs


def _verify_report(swis, report_id, report, log):
    """Read the report back and compare it with what was submitted.

    The import is only done when the stored tree has the same policies, the same
    rule count and the same rule names per policy. A partial tree (one server was
    observed storing only the report row) or a result that is not a report object
    raises NcmVerificationError, which the callers treat as a failed import.
    """
    expected = expected_tree(report)
    n_policies = len(expected)
    n_rules = sum(len(rules) for _p, rules in expected)
    log_event("verify", f"reading report {report_id} back (expecting {n_policies} "
                        f"policies and {n_rules} rules)")
    stored = swis.invoke("Cirrus.PolicyReports", "GetPolicyReport", report_id, True)
    if stored is None or (isinstance(stored, str) and not stored.strip()):
        msg = (f"No data returned from GetPolicyReport for report {report_id} — "
               "the import cannot be confirmed")
        log_event("verify", msg, "error")
        raise NcmVerificationError(msg)
    actual = read_back_tree(stored)
    if actual is None:
        diffs = [f"GetPolicyReport(id, true) returned {_summarize_value(stored)} "
                 "instead of a readable report object"]
    else:
        diffs = compare_report_trees(expected, actual)
    if diffs:
        held = ("nothing readable" if actual is None else
                f"{len(actual)} policies / {sum(len(r) for _p, r in actual)} rules")
        msg = (f"verification failed: report {report_id} was created but the server holds "
               f"{held}; the import carried {n_policies} policies / {n_rules} rules - "
               + "; ".join(diffs[:5])
               + (f"; ... and {len(diffs) - 5} more" if len(diffs) > 5 else "")
               + ". " + ROLE_HINT)
        log_event("verify", msg, "error")
        raise NcmVerificationError(msg)
    _say(log, "verify", f"verified: report holds {len(actual)} policies and {n_rules} rules, "
                        "matching the import (policy names and rule names compared)")
    return report_id, len(actual), n_rules


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
            if not is_wire_rejection(exc):
                log_event("verify", f"TestRule stopped: {spec['label']} failed with an error "
                                    "that is not a documented wire-format rejection", "error")
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
        # Every failure is caught here (a timeout or a raw transport error as much as
        # an HTTP error), logged, and the rollback carries on with the next level.
        try:
            swis.invoke("Cirrus.PolicyReports", verb, *args)
            return True
        except Exception as exc:
            _say(log, "rollbk", f"rollback: {verb} failed, clean up by hand - "
                                f"{type(exc).__name__}: {exc}", "error")
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
        except Exception as exc:
            if not is_wire_rejection(exc):
                log_event("import", f"wire-format probe stopped: {spec['label']} failed with an "
                                    "error that is not a documented wire-format rejection "
                                    f"(HTTP {http_status(exc) or 'none'}), so no other format is "
                                    "tried and no console file is written for it", "error")
                if http_status(exc) is None:
                    _warn_unknown_outcome(log, "rule", probe_rule["RuleId"], preexisting)
                raise
            rejections.append(f"{spec['label']}: {str(exc).splitlines()[-1]}")
            _say(log, "import",
                 f"server rejected {spec['label']}; trying the next wire format …", "warn")
    if fmt:
        return _import_ncm_bottom_up(swis, report, log, WIRE_FORMATS[fmt],
                                     first_rule_id, rollback, preexisting)
    return _import_ncm_nested(swis, report, log, rollback, preexisting, rejections)


def _warn_unknown_outcome(log, kind, submitted_id, preexisting):
    """A call that failed below HTTP (a timeout, a reset) may still have run server side."""
    if _norm_id(submitted_id) in preexisting.get({"rule": "rules", "policy": "policies"}[kind],
                                                  set()):
        return
    _say(log, "import", f"warning: the outcome of the failed call is unknown (no HTTP status): "
                        f"if the server created the {kind} anyway, it is not in the rollback "
                        f"list. Check for {kind} id {submitted_id} (Unverified: whether the "
                        "server keeps a submitted id is not documented).", "warn")


def _import_ncm_nested(swis, report, log, rollback, preexisting, rejections):
    """The one-call nested AddPolicyReport in console-export XML, verified like the rest.

    A server has been observed accepting the nested call and storing only the report
    row, so a verification failure here deletes what the call created (the report,
    then its unshared policies and rules, never anything that existed before this run)
    and falls through to the console-file fallback. Any error that is not a documented
    wire-format rejection stops the report instead, with no console file.
    """
    _say(log, "import", "no per-item wire format accepted; trying one nested AddPolicyReport "
                        "in the console-export format …", "warn")
    report_id = ""
    try:
        report_id = _clean_id(
            swis.invoke("Cirrus.PolicyReports", "AddPolicyReport",
                        report_contract_xml(report), True), "")
    except Exception as exc:
        if not is_wire_rejection(exc):
            log_event("import", "nested AddPolicyReport failed with an error that is not a "
                                "documented wire-format rejection; stopping this report", "error")
            if http_status(exc) is None:
                _say(log, "import", "warning: the outcome of the failed AddPolicyReport is unknown "
                                    "(no HTTP status); if the server created the report anyway, "
                                    f"look for \"{report['Name']}\" and remove it", "warn")
            raise
        rejections.append(f"console-format XML: {str(exc).splitlines()[-1]}")
    else:
        if not report_id:
            # The collision check ran before the import, so a report with this name
            # now can only be the one this call created without returning its id.
            found = swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                               {"n": report["Name"]})
            report_id = str(_row_value(found[0], "PolicyReportID") or "") \
                if isinstance(found, list) and found else ""
            if report_id:
                _say(log, "import", f"nested AddPolicyReport returned no id, but a report named "
                                    f"\"{report['Name']}\" now exists ({report_id}); verifying it",
                     "warn")
            else:
                rejections.append("console-format XML: no report id returned and no report "
                                  "was created")
    if report_id:
        log_event("import", f"nested AddPolicyReport created report {report_id}")
        try:
            return _verify_report(swis, report_id, report, log)
        except Exception as exc:
            log_event("import", f"nested import of \"{report['Name']}\" failed verification: "
                                f"{exc}", "error")
            if rollback:
                _rollback_nested(swis, report_id, preexisting, log)
            else:
                _say(log, "import", f"report {report_id} was left on the server (--no-rollback); "
                                    "delete it before importing the console file, or the names "
                                    "collide", "warn")
            if not isinstance(exc, NcmVerificationError):
                raise
            rejections.append(f"console-format XML: accepted, but {exc}")
    log_event("import", "no wire format accepted for \"" + report["Name"] + "\": "
                        + "; ".join(rejections) + "; console-importable files will be written",
              "error")
    raise NcmWireError(
        "this server accepted none of the wire formats for the NCM compliance "
        "contract types:\n  " + "\n  ".join(rejections) + "\n"
        "A console-importable report file has been written instead — import it in "
        "the web console under Compliance → Manage Policy Reports → Import.",
        '<?xml version="1.0" encoding="utf-16"?>' + report_contract_xml(report))


def _rollback_nested(swis, report_id, preexisting, log):
    """Delete what a nested AddPolicyReport created: the report row, then the policies
    and rules nothing else uses (the same plan ``remove`` makes), skipping every id that
    existed before this run. The IN @ids probe in plan_ncm_removal runs first; when it
    fails, nothing is deleted and InIdsProbeError stops the report."""
    _say(log, "rollbk", f"rollback: removing the nested import's report {report_id} and what "
                        "only it uses …")
    plan = plan_ncm_removal(swis, [report_id], log=log)
    for key, kind, label in (("delete_policies", "policies", "policy"),
                             ("delete_rules", "rules", "rule")):
        kept = [i for i in plan[key] if _norm_id(i) in preexisting[kind]]
        if kept:
            plan[key] = [i for i in plan[key] if _norm_id(i) not in preexisting[kind]]
            for i in kept:
                _say(log, "rollbk", f"rollback: skipped {label} {i} - it existed on the server "
                                    "before this import")
    describe_removal_plan(plan, log, prefix="rollback: ")
    try:
        left = remove_ncm_reports(swis, plan, log)
    except Exception as exc:
        _say(log, "rollbk", f"rollback: deleting the nested import failed, clean up by hand "
                            f"(report {report_id}) - {type(exc).__name__}: {exc}", "error")
        return
    if any(left.values()):
        _say(log, "rollbk", f"rollback: some objects of report {report_id} are still present; "
                            "clean up by hand", "error")


def _import_ncm_bottom_up(swis, report, log, spec, first_rule_id, rollback=True,
                          preexisting=None):
    preexisting = preexisting or {"rules": set(), "policies": set()}
    policy_ids = []
    all_rule_ids = [first_rule_id]
    report_id = ""
    first = True
    pending = None     # (kind, submitted id) of the call in flight, for an unknown outcome
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
                pending = ("rule", rule["RuleId"])
                result = swis.invoke("Cirrus.PolicyReports", "AddPolicyRule",
                                     spec["rule"](rule))
                new_rule_id = _clean_id(result, rule["RuleId"])
                rule_ids.append(new_rule_id)
                all_rule_ids.append(new_rule_id)
                if i % 25 == 0:
                    _say(log, "import", f"  {i}/{len(rules)} rules created")

            pending = ("policy", policy["PolicyId"])
            result = swis.invoke("Cirrus.PolicyReports", "AddPolicy",
                                 spec["policy"](policy, rule_ids), False)
            policy_ids.append(_clean_id(result, policy["PolicyId"]))
            _say(log, "import",
                 f"created policy \"{policy['PolicyName']}\" with {len(rule_ids)} rules")

        pending = ("report", "")
        report_id = _clean_id(
            swis.invoke("Cirrus.PolicyReports", "AddPolicyReport",
                        spec["report"](report, policy_ids), False), "")
        pending = None
        if not report_id:
            raise SwisError("AddPolicyReport did not return the new report id")
        log_event("import", f"AddPolicyReport returned report id {report_id}")

        return _verify_report(swis, report_id, report, log)
    except Exception as exc:
        # Every failure (an HTTP error, a timeout, a read-back that is not a report
        # object, a mismatch) is logged and rolled back the same way, then re-raised
        # for import_ncm_reports to record.
        log_event("import", f"import of \"{report['Name']}\" failed: {type(exc).__name__}: {exc}",
                  "error")
        if pending and http_status(exc) is None and not isinstance(exc, NcmVerificationError):
            if pending[0] == "report":
                _say(log, "import", "warning: the outcome of the failed AddPolicyReport is "
                                    "unknown (no HTTP status); if the server created the report "
                                    f"anyway, look for \"{report['Name']}\" and remove it",
                     "warn")
            else:
                _warn_unknown_outcome(log, pending[0], pending[1], preexisting)
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
    and are still the caller's to cache or disable. Any exception counts as a
    failure here, as it does in the PowerShell edition's Import-NcmReports.
    """
    imported = []
    for index, report in enumerate(reports):
        n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
        _say(log, "import", f"importing \"{report['Name']}\" - {n_rules} rules ...")
        try:
            new_id, _n_pol, n_stored = import_ncm_report(swis, report, log=log,
                                                         rollback=rollback)
        except Exception as exc:
            log_event("import", f"stopping at \"{report['Name']}\": {len(imported)} of "
                                f"{len(reports)} report(s) imported, {len(reports) - index} "
                                f"not imported ({type(exc).__name__}: {exc})", "error")
            return imported, exc, list(reports[index:])
        imported.append((report, new_id, n_stored))
        _bump("imported")
        _say(log, "import", f"imported: \"{report['Name']}\" ({new_id}) - {n_stored} rules")
    return imported, None, []


def finish_ncm_imports(swis, new_ids, disabled=False, no_cache=False, log=print):
    """Disable or start caching the reports a run imported. Returns True when the
    requested end state was confirmed (or nothing was asked of the server).

    StartCaching and UpdateReportStatus need the WebUploader NCM role, one step above
    what the import itself needs, so an account can import successfully and then be
    refused here. That refusal is logged with the role it needs and the run carries
    on (the caller still writes any console files that are due); the return value is
    False so the caller can report the unconfirmed state.
    """
    if not new_ids:
        return True
    if disabled:
        # ReportStatus travels in the payload, but UpdateReportStatus is the verb
        # that owns the field, so say it explicitly rather than trusting the
        # import to have carried it, and read it back.
        try:
            swis.invoke("Cirrus.PolicyReports", "UpdateReportStatus", "Disabled", list(new_ids))
        except Exception as exc:
            _say(log, "verify", f"warning: UpdateReportStatus('Disabled') failed - "
                                f"{type(exc).__name__}: {exc}. It needs the WebUploader NCM role "
                                "(an Orion administrator when compliance is restricted to "
                                "administrators). The reports may still be Enabled, and the "
                                "nightly policy cache job would then evaluate them; disable them "
                                "in the console.", "error")
            return False
        stored = swis.query("SELECT Name, ReportStatus FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids",
                            {"ids": list(new_ids)})
        if not stored:
            _say(log, "verify", "warning: No data returned reading ReportStatus back after "
                                "UpdateReportStatus; confirm the reports are disabled in the "
                                "console", "warn")
            return False
        still_on = [_row_value(r, "Name") for r in stored if _row_value(r, "ReportStatus")]
        if still_on:
            _say(log, "verify", "warning: still enabled after UpdateReportStatus: "
                 + ", ".join(str(n) for n in still_on), "warn")
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
    try:
        started = swis.invoke("Cirrus.PolicyReports", "StartCaching", list(new_ids))
    except Exception as exc:
        _say(log, "import", f"warning: StartCaching failed - {type(exc).__name__}: {exc}. It "
                            "needs the WebUploader NCM role (an Orion administrator when "
                            "compliance is restricted to administrators). The reports are "
                            "imported and verified but show no data until they are cached: run "
                            "Update Violations in the console, or wait for the nightly policy "
                            "cache job if it is enabled.", "error")
        return False
    # The contract declares a boolean result; what false means is not documented.
    log_event("import", f"StartCaching returned {_summarize_value(started)}")
    if started is False:
        _say(log, "import", "warning: StartCaching returned false. Unverified: SolarWinds does "
                            "not document what false means; watch CacheStatus on "
                            "Cirrus.PolicyReports for these reports.", "warn")
        return False
    _say(log, "import", f"compliance caching started for {len(new_ids)} report(s). Watch them "
                        "under My Dashboards > Network Configuration > Compliance. The policy "
                        "cache also refreshes on its own at 11:55 PM daily when that job is "
                        "enabled.")
    return True


NIL_GUID = "00000000-0000-0000-0000-000000000000"
_DENIED_TEXT = re.compile(r"access (is )?denied|not authori[sz]ed|permission|forbidden|"
                          r"only for (orion )?admin", re.IGNORECASE)


def ncm_preflight(swis, log=print):
    """Before anything is written: can this account call the compliance verbs at all?

    Logs the role each verb needs, then calls GetPolicyReport (WebDownloader, like
    every write the import makes) for the nil GUID, which no report has. An answer of
    any kind confirms access; 401, 403, or a message that reads as a permission
    refusal stops the run before anything is created. Unverified: how a server
    answers GetPolicyReport for an id that does not exist is not documented, so any
    other error is logged as inconclusive and the import goes ahead (the per-report
    rollback still covers a later refusal). Returns "ok" or "inconclusive".
    """
    for role, verbs in NCM_VERB_ROLES:
        log_event("import", f"NCM role needed (2026.2 verb descriptions): {role} or higher for "
                            + ", ".join(verbs))
    log_event("import", "when the server's 'compliance only for administrators' option is on, "
                        "every one of those verbs is valid only for Orion administrators")
    try:
        result = swis.invoke("Cirrus.PolicyReports", "GetPolicyReport", NIL_GUID, False)
    except SwisError as exc:
        status = http_status(exc)
        if status in (401, 403) or (status is not None and _DENIED_TEXT.search(str(exc))):
            msg = (f"permission preflight: this account may not call Cirrus.PolicyReports "
                   f"GetPolicyReport (HTTP {status}): {str(exc).splitlines()[-1]}. The import "
                   "needs at least the WebDownloader NCM role (WebUploader to start caching or "
                   "change ReportStatus), or an Orion administrator when the server restricts "
                   "compliance to administrators. Nothing was created.")
            log_event("import", msg, "error")
            raise SwisError(msg) from exc
        if status is None:
            raise
        _say(log, "import", f"permission preflight inconclusive: GetPolicyReport for the nil "
                            f"GUID answered HTTP {status} (Unverified: the answer for an id that "
                            "does not exist is not documented); continuing", "warn")
        return "inconclusive"
    log_event("import", f"permission preflight ok: GetPolicyReport answered "
                        f"{_summarize_value(result)} for an id that does not exist, so the "
                        "account may call the compliance verbs")
    return "ok"


# ---------------------------------------------------------------------------
# Collision check: refuse before anything is written, and suggest the next suffix
# ---------------------------------------------------------------------------
#
# Every name and id the tool generates ends in (or is seeded with) the version
# suffix, so a collision means this STIG was already imported with that suffix. The
# run is refused before the first write, naming what collided, with the next free
# suffix found by listing the names that share the base (the base is the name with
# its _v<n> removed). The existing-id snapshot inside import_ncm_report stays as
# defense in depth: with this check in front of it, it normally finds nothing.

NAME_LIKE_QUERIES = {
    "Cirrus.PolicyReports": "SELECT TOP 200 Name FROM Cirrus.PolicyReports WHERE Name LIKE @p",
    "Cirrus.Policies": "SELECT TOP 200 Name FROM Cirrus.Policies WHERE Name LIKE @p",
    "Orion.PolicyEngine.Policy": "SELECT TOP 200 Name FROM Orion.PolicyEngine.Policy WHERE Name LIKE @p",
}


def like_prefix(text):
    """A LIKE pattern matching every name that starts with ``text``. It is cut at the
    first '[' (a character class in SQL Server LIKE; Unverified whether SWIS passes
    LIKE through unchanged), and _ and % stay wildcards: the pattern may match more
    than the prefix, never less, and callers filter the rows exactly."""
    return text.split("[", 1)[0] + "%"


def suffix_advice(swis, bases, current_suffix):
    """'re-run with --suffix _vN' text, N one above every _v<n> already used by a name
    with the same base. ``bases`` is [(entity in NAME_LIKE_QUERIES, base name)]."""
    names = []
    for entity, base in bases:
        try:
            rows = swis.query(NAME_LIKE_QUERIES[entity], {"p": like_prefix(base)}) or []
        except (SwisError, ValueError, TypeError) as exc:
            log_event("import", f"could not list {entity} names starting with \"{base}\": {exc}",
                      "warn")
            continue
        names += [(base, str(_row_value(r, "Name") or "")) for r in rows]
    highest = int(current_suffix[2:]) + 1
    for base in {b for _entity, b in bases}:
        candidate = next_free_suffix([n for b, n in names if b == base], base, current_suffix)
        highest = max(highest, int(candidate[2:]))
    suggestion = f"_v{highest}"
    used = sorted({n for _b, n in names})
    log_event("import", f"names already using these bases: {', '.join(used) or 'none listed'}; "
                        f"next free suffix {suggestion}")
    return (f"The next free suffix is {suggestion}: re-run with --suffix {suggestion} "
            f"(PowerShell: -Suffix {suggestion}) to import alongside, or remove the existing "
            "import first.")


class CollisionError(SwisError):
    """A name or generated id this run would create already exists; nothing was written."""


def ncm_collision_check(swis, reports, suffix=DEFAULT_SUFFIX, log=print):
    """Refuse before writing when any report name, policy name, PolicyId or RuleId the
    reports would create already exists (CollisionError, with the next free suffix)."""
    suffix = validate_suffix(suffix)
    hits = []
    for report in reports:
        found = swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                           {"n": report["Name"]})
        if found:
            hits.append(f"report \"{report['Name']}\" ({_row_value(found[0], 'PolicyReportID')})")
        for policy in report["AssignedPolicies"]:
            found = swis.query("SELECT PolicyID, Name FROM Cirrus.Policies WHERE Name = @n",
                               {"n": policy["PolicyName"]})
            if found:
                hits.append(f"policy \"{policy['PolicyName']}\" ({_row_value(found[0], 'PolicyID')})")
        existing = existing_ncm_ids(swis, report)
        if existing["policies"]:
            hits.append(f"{len(existing['policies'])} PolicyId(s) of \"{report['Name']}\" "
                        f"({', '.join(sorted(existing['policies'])[:3])})")
        if existing["rules"]:
            hits.append(f"{len(existing['rules'])} RuleId(s) of \"{report['Name']}\" "
                        f"({', '.join(sorted(existing['rules'])[:3])}"
                        + (", ..." if len(existing["rules"]) > 3 else "") + ")")
    if not hits:
        log_event("import", f"collision check: none of the {len(reports)} report(s), their "
                            f"policies or ids exist yet (suffix {suffix})")
        return
    bases = []
    for report in reports:
        bases.append(("Cirrus.PolicyReports", strip_suffix(report["Name"])[0]))
        bases += [("Cirrus.Policies", strip_suffix(p["PolicyName"])[0])
                  for p in report["AssignedPolicies"]]
    msg = ("already on the server with suffix " + suffix + ": " + "; ".join(hits)
           + ". Nothing was imported; this tool never overwrites. "
           + suffix_advice(swis, bases, suffix))
    log_event("import", "collision: " + msg, "error")
    raise CollisionError(msg)


IN_IDS_PROBES["scmrule"] = ("SELECT UniqueId FROM Orion.PolicyEngine.Rule WHERE UniqueId IN @ids",
                            "UniqueId")


def scm_collision_check(swis, benchmarks, suffix=DEFAULT_SUFFIX, log=print):
    """Refuse before importing any of these converted policies when a policy name, a
    policy uniqueId or any rule uniqueId already exists (CollisionError).

    SolarWinds documents rejecting a policy whose name or uniqueId exists; whether a
    rule uniqueId used by another policy is rejected is Unverified, and it is checked
    anyway so that a new suffix really means entirely fresh ids. The rule lookup is an
    IN @ids query over GUIDs, so it is preceded by the same sanity probe the NCM path
    uses (on one rule SELECT TOP 1 returns)."""
    suffix = validate_suffix(suffix)
    hits = []
    for b in benchmarks:
        name, uid = scm_policy_name(b, suffix), scm_policy_uid(b, suffix)
        found = swis.query("SELECT PolicyID, Name, UniqueId, BuiltIn FROM Orion.PolicyEngine.Policy "
                           "WHERE Name = @n OR UniqueId = @u", {"n": name, "u": uid})
        for row in found or []:
            hits.append(f"policy \"{_row_value(row, 'Name')}\" (PolicyID "
                        f"{_row_value(row, 'PolicyID')}, UniqueId {_row_value(row, 'UniqueId')})")
    rule_ids = [scm_rule_uid(r, suffix) for b in benchmarks for r in b["rules"]]
    if rule_ids:
        sample = swis.query("SELECT TOP 1 UniqueId FROM Orion.PolicyEngine.Rule")
        known = _row_value(sample[0], "UniqueId") if isinstance(sample, list) and sample else None
        if known:
            confirm_in_ids(swis, "scmrule", str(known), "the SCM rule uniqueId check", "scm")
            rows = _query_ids(swis, IN_IDS_PROBES["scmrule"][0], rule_ids)
            if rows:
                ids = sorted({_norm_id(_row_value(r, "UniqueId")) for r in rows})
                hits.append(f"{len(ids)} rule uniqueId(s) ({', '.join(ids[:3])}"
                            + (", ..." if len(ids) > 3 else "") + ")")
        else:
            log_event("scm", "the server returned no SCM rule rows, so none of the "
                             f"{len(rule_ids)} rule uniqueId(s) can already exist")
    if not hits:
        log_event("scm", f"collision check: none of the {len(benchmarks)} SCM policy name(s), "
                         f"uniqueId(s) or rule uniqueId(s) exist yet (suffix {suffix})")
        return
    bases = [("Orion.PolicyEngine.Policy", strip_suffix(scm_policy_name(b, suffix))[0])
             for b in benchmarks]
    msg = ("already on the server with suffix " + suffix + ": " + "; ".join(hits)
           + ". Nothing was imported; this tool never overwrites. "
           + suffix_advice(swis, bases, suffix))
    log_event("scm", "collision: " + msg, "error")
    raise CollisionError(msg)


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
    """Work out what removing these reports deletes and what it must keep.

    Every membership and sharing lookup below is an IN @ids query over GUIDs, so the
    sanity probe runs first on the first report, which is known to exist; when it
    fails, InIdsProbeError stops the removal before anything is deleted.
    """
    report_ids = list(report_ids)
    if report_ids:
        confirm_in_ids(swis, "report", report_ids[0], "planning the removal", component="remove")
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
        if not isinstance(tree, dict) or not tree:
            what = "No data returned" if not tree else \
                f"a result that is not a report object ({_summarize_value(tree)}) came back"
            _say(log, "remove", f"note: {what} from GetPolicyReport for {report_id}; "
                                "its policies and rules are taken from Cirrus.PolicyAssignment "
                                "alone", "warn")
            continue
        for pid in tree.get("AssignedPoliciesList") or []:
            add(policies, pid)
        for pol in tree.get("AssignedPolicies") or []:
            if not isinstance(pol, dict):
                continue
            add(policies, pol.get("PolicyId"), pol.get("PolicyName"))
            for rid in pol.get("AssignedRulesList") or []:
                add(rules, rid)
            for rule in pol.get("AssignedPolicyRules") or []:
                if isinstance(rule, dict):
                    add(rules, rule.get("RuleId"), rule.get("RuleName"))
    # The export tree is not documented to carry PolicyId, so the SWQL link
    # tables are read as well; together they give the report's full membership.
    for row in _query_ids(swis, "SELECT PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyReportID IN @ids",
                          list(report_ids)):
        add(policies, _row_value(row, "PolicyID"))
    for row in _query_ids(swis, "SELECT PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyID IN @ids",
                          list(policies.values())):
        add(rules, _row_value(row, "PolicyRuleID"))

    kept_policies = {}
    for row in _query_ids(swis, "SELECT PolicyReportID, PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyID IN @ids",
                          list(policies.values())):
        other = _norm_id(_row_value(row, "PolicyReportID"))
        key = _norm_id(_row_value(row, "PolicyID"))
        if key in policies and other and other not in report_keys:
            kept_policies.setdefault(key, []).append(str(_row_value(row, "PolicyReportID")))
    delete_policy_keys = set(policies) - set(kept_policies)

    kept_rules = {}
    for row in _query_ids(swis, "SELECT PolicyID, PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyRuleID IN @ids",
                          list(rules.values())):
        other = _norm_id(_row_value(row, "PolicyID"))
        key = _norm_id(_row_value(row, "PolicyRuleID"))
        if key in rules and other and other not in delete_policy_keys:
            kept_rules.setdefault(key, []).append(str(_row_value(row, "PolicyID")))

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

# keyword -> (display OS name, SWQL filter against Orion.Nodes for assignment, OS family
# for the SCM probe table SCM_PROBES)
SERVER_OSES = {
    "red hat": ("Red Hat Enterprise Linux", "MachineType LIKE '%Red Hat%'", "linux"),
    "rhel": ("Red Hat Enterprise Linux", "MachineType LIKE '%Red Hat%'", "linux"),
    "ubuntu": ("Ubuntu", "MachineType LIKE '%Ubuntu%'", "linux"),
    "debian": ("Debian", "MachineType LIKE '%Debian%'", "linux"),
    "centos": ("CentOS", "MachineType LIKE '%CentOS%'", "linux"),
    "linux": ("Linux", "MachineType LIKE '%Linux%'", "linux"),
    "windows": ("Windows", "MachineType LIKE '%Windows%'", "windows"),
    "sql server": ("Windows", "MachineType LIKE '%Windows%'", "windows"),
    "iis": ("Windows", "MachineType LIKE '%Windows%'", "windows"),
    "exchange": ("Windows", "MachineType LIKE '%Windows%'", "windows"),
}
UNKNOWN_SERVER_OS = ("(OS not recognized)", "MachineType LIKE '%'", "unknown")


def detect_target(benchmarks, source_name):
    """Return ('network', vendor_or_None) or ('server', (os, swql, family)) or (None, None).

    Vendor keywords win over OS keywords only when they appear and no OS does;
    a Windows/Linux match routes to SCM even if generic words like 'router'
    also appear somewhere.
    """
    text = " ".join([source_name or ""] + [b["title"] + " " + b["source"]
                                           for b in benchmarks]).lower()
    for kw, os_info in SERVER_OSES.items():
        if kw in text:
            log_event("route", f"server keyword '{kw}' matched in the file/benchmark names "
                               f"-> server ({os_info[0]}, OS family {os_info[2]})")
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


# ---------------------------------------------------------------------------
# NCM node scope: Vendor, and for Cisco the platform by MachineType
# ---------------------------------------------------------------------------
#
# Tentative: MachineType values to be verified against a live server. The patterns
# below are what Cisco nodes are expected to report in Orion.Nodes.MachineType; no
# export or schema in this repository records the actual strings. The platform is
# read from the package file name plus each benchmark's title and source member
# name, with -, _ and white space treated alike ("IOS-XE", "IOS_XE", "IOS XE" and
# "IOSXE" all match), and the specific platforms are tried before classic IOS. Note
# that '%IOS%' also matches a MachineType containing IOS-XE or IOS-XR; that overlap is
# part of what the live check has to settle. An import logs the MachineType values
# the vendor's nodes report, which is the check.
CISCO_PLATFORMS = (
    ("IOS-XE", re.compile(r"\bios ?xe\b"), "%IOS-XE%"),
    ("IOS-XR", re.compile(r"\bios ?xr\b"), "%IOS-XR%"),
    ("NX-OS", re.compile(r"\bnx ?os\b"), "%NX-OS%"),
    ("ASA", re.compile(r"\basa\b"), "%ASA%"),
    ("IOS", re.compile(r"\bios\b"), "%IOS%"),
)
TENTATIVE_NOTE = "Tentative: MachineType values to be verified against a live server"
SCOPE_VALUE_MAX = 200


class ScopeError(ValueError):
    """The NCM node scope cannot be decided (or selects no node); nothing is
    converted or imported."""


def sql_literal(value):
    """A single-quoted SQL/SWQL string literal (a ' inside is doubled)."""
    return "'" + str(value).replace("'", "''") + "'"


def check_scope_value(value, option):
    """--vendor / --machine-type: one line of printable text, at most 200 characters."""
    value = str(value).strip()
    if not value or len(value) > SCOPE_VALUE_MAX or re.search(r"[\x00-\x1f\x7f]", value):
        raise ScopeError(f"{option} must be 1 to {SCOPE_VALUE_MAX} printable characters "
                         f"(got {value[:40]!r})")
    return value


def platform_text(text):
    """Lower case, with every run of '-', '_' and white space made one space."""
    return re.sub(r"[\s_\-]+", " ", (text or "").lower())


def detect_cisco_platform(text):
    """(platform, MachineType pattern) for the first CISCO_PLATFORMS entry that
    matches, or (None, None)."""
    norm = platform_text(text)
    for platform_name, pattern, machine_type in CISCO_PLATFORMS:
        if pattern.search(norm):
            return platform_name, machine_type
    return None, None


def benchmark_platforms(benchmarks, source_name):
    """The Cisco platform each benchmark names, read from the package name plus its own
    title and source member, as [(benchmark id or title, platform, pattern)]."""
    out = []
    for b in benchmarks:
        platform_name, machine_type = detect_cisco_platform(
            " ".join((source_name or "", b["title"], b["source"])))
        out.append((b["benchmark_id"] or b["title"], platform_name, machine_type))
    return out


def node_where_for(vendor, machine_type=None):
    """The NCM SQL fragment (bare column names, as real console exports carry it)."""
    if machine_type:
        return f"(Vendor = {sql_literal(vendor)} AND MachineType LIKE {sql_literal(machine_type)})"
    return f"(Vendor = {sql_literal(vendor)})"


def scope_swql(scope):
    """(SWQL, parameters) counting the Orion.Nodes rows the scope selects.

    A generated scope is sent with bound parameters, never by splicing the values in.
    An explicit --node-where is the operator's own NCM SQL; it is used as written
    (with any Nodes. prefix dropped, as make_node_selection_string does) in a read-only
    query, and since NCM SQL is not always valid SWQL that count can fail."""
    if scope.get("vendor") and not scope.get("explicit"):
        if scope.get("machine_type"):
            return ("SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor AND MachineType LIKE @machineType",
                    {"vendor": scope["vendor"], "machineType": scope["machine_type"]})
        return ("SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor",
                {"vendor": scope["vendor"]})
    where = re.sub(r"\bNodes\.", "", scope["where"]).strip()
    return "SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE " + where, {}


def resolve_ncm_scope(benchmarks, source_name, node_where=None, vendor=None, machine_type=None,
                      detected_vendor=None):
    """Decide the NCM node scope, or raise ScopeError.

    An explicit --node-where is used as written. Otherwise the vendor is --vendor,
    else the detected one; with no vendor at all the STIG is refused (a Router or NDM
    SRG, ESXi or any unrecognized network STIG no longer defaults to Cisco). For Cisco
    the platform's MachineType pattern is added; --machine-type overrides it (and
    applies to any vendor when given). A Cisco STIG whose platform is not recognized,
    or a package whose benchmarks name different platforms, is refused.
    Returns {where, vendor, machine_type, platform, explicit, how}.
    """
    vendor, machine_type = vendor or None, machine_type or None
    explicit =bool(node_where) and not node_where.lower().startswith("auto") \
        and not node_where.startswith("(auto")
    if explicit:
        if vendor or machine_type:
            raise ScopeError("give either --node-where or --vendor/--machine-type, not both")
        log_event("scope", f"NCM node scope {node_where} (explicit --node-where)")
        return {"where": node_where, "vendor": picker_vendor(node_where), "machine_type": None,
                "platform": None, "explicit": True, "how": "explicit --node-where"}
    how = []
    if vendor:
        vendor = check_scope_value(vendor, "--vendor")
        how.append("--vendor")
    elif detected_vendor:
        vendor = detected_vendor
        how.append("vendor detected from the names")
    else:
        msg = (f"{source_name}: no network vendor was recognized in the file or benchmark names "
               "(an SRG such as the Router or NDM SRG, ESXi, or an unlisted product), so there is "
               "no safe node scope; the tool no longer assumes Cisco. Pass --vendor NAME (the "
               "Vendor value your nodes report, with --machine-type PATTERN for Cisco) or "
               "--node-where \"(...)\" (PowerShell: -Vendor, -MachineType, -NodeWhere).")
        log_event("scope", msg, "error")
        raise ScopeError(msg)
    platform_name = None
    if machine_type:
        machine_type = check_scope_value(machine_type, "--machine-type")
        how.append("--machine-type")
    elif vendor.lower() == "cisco":
        found = benchmark_platforms(benchmarks, source_name)
        for bid, name, pattern in found:
            log_event("scope", f"Cisco platform for {bid}: "
                               + (f"{name} -> MachineType LIKE '{pattern}' ({TENTATIVE_NOTE})"
                                  if name else "not recognized"))
        names = sorted({name or "not recognized" for _bid, name, _p in found})
        if len(names) > 1:
            listed = ", ".join(f"{bid}: {name or 'not recognized'}" for bid, name, _p in found)
            msg = (f"{source_name}: the benchmarks name different Cisco platforms ({listed}); one "
                   "run uses one node scope, so convert or import them separately, or pass "
                   "--machine-type PATTERN or --node-where \"(...)\".")
            log_event("scope", msg, "error")
            raise ScopeError(msg)
        platform_name = found[0][1] if found else None
        machine_type = found[0][2] if found else None
        if not platform_name:
            msg = (f"{source_name}: a Cisco STIG, but no platform (IOS-XE, IOS-XR, NX-OS, ASA, "
                   "IOS) was recognized in the file or benchmark names, so the node scope would be "
                   "every Cisco node. Pass --machine-type PATTERN (for example '%IOS-XE%', or '%' "
                   "for every Cisco node that reports a MachineType) or --node-where \"(...)\".")
            log_event("scope", msg, "error")
            raise ScopeError(msg)
        how.append(f"platform {platform_name} detected ({TENTATIVE_NOTE})")
    where = node_where_for(vendor, machine_type)
    log_event("scope", f"NCM node scope {where} ({', '.join(how)}); the console node picker "
                       "shows Vendor only, the MachineType condition is in the SQL part")
    return {"where": where, "vendor": vendor, "machine_type": machine_type,
            "platform": platform_name, "explicit": False, "how": ", ".join(how)}


SCOPE_SAMPLE_SWQL = ("SELECT TOP 25 Vendor, MachineType, COUNT(NodeID) AS N FROM Orion.Nodes "
                     "WHERE Vendor = @vendor GROUP BY Vendor, MachineType ORDER BY MachineType")


def scope_preflight(swis, scope, allow_empty=False, log=print):
    """Count the nodes the scope selects, before anything is written.

    Logs the NCM SQL and the SWQL form of the same condition, the count, and (when a
    vendor is known) up to 25 MachineType values that vendor's nodes report, which is
    how the Tentative platform table gets checked. Zero matching nodes refuses the
    import (ScopeError) unless ``allow_empty``. A count that cannot be run (an NCM SQL
    fragment that is not valid SWQL, a permission error) is logged as inconclusive
    and the import goes on. Returns the count, or None when it could not be taken.
    """
    swql, params = scope_swql(scope)
    log_event("scope", f"scope preflight: NCM SQL Where {scope['where']}; SWQL {swql}"
                       + (" params {" + ", ".join(f"{k}={v!r}" for k, v in params.items()) + "}"
                          if params else ""))
    try:
        rows = swis.query(swql, params or None)
        count = int(_row_value(rows[0], "N") or 0) if isinstance(rows, list) and rows else 0
    except (SwisError, ValueError, TypeError) as exc:
        _say(log, "scope", f"warning: the node scope could not be counted ({exc}); the import goes "
                           "on without the empty-scope check, so check the scope in the console",
             "warn")
        return None
    if scope.get("vendor"):
        try:
            sample = swis.query(SCOPE_SAMPLE_SWQL, {"vendor": scope["vendor"]}) or []
            seen = "; ".join(f"{_row_value(r, 'MachineType')} ({_row_value(r, 'N')})"
                             for r in sample if isinstance(r, dict))
            log_event("scope", f"MachineType values reported by Vendor '{scope['vendor']}' nodes "
                               f"(up to 25): {seen or 'none'}"
                               + (f" - {TENTATIVE_NOTE}" if scope.get("platform") else ""))
        except (SwisError, ValueError, TypeError) as exc:
            log_event("scope", f"could not sample MachineType values: {exc}", "warn")
    if count:
        _say(log, "scope", f"node scope selects {count} node(s): {scope['where']}")
        return count
    msg = (f"the node scope {scope['where']} matches no node on this server"
           + (f" ({TENTATIVE_NOTE}; the MachineType values Vendor '{scope['vendor']}' nodes "
              "report are in the run log)" if scope.get("platform") else "")
           + ". A report scoped to no node evaluates nothing, which reads like compliance.")
    if allow_empty:
        _say(log, "scope", f"warning: {msg} Importing anyway (--allow-empty-scope).", "warn")
        return 0
    log_event("scope", msg + " Refused; nothing was created.", "error")
    raise ScopeError(msg + " Nothing was created. Correct --machine-type, --vendor or "
                           "--node-where, or pass --allow-empty-scope (PowerShell: "
                           "-AllowEmptyScope) to import it anyway.")


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


def scm_policy_name(benchmark, suffix=DEFAULT_SUFFIX):
    return with_suffix(f"{benchmark['title']} V{benchmark['version']} ({benchmark['release']})",
                       suffix)


def scm_policy_uid(benchmark, suffix=DEFAULT_SUFFIX):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-scm:" + (benchmark["benchmark_id"]
                                                                 or benchmark["title"]) + suffix))


def scm_rule_uid(rule, suffix=DEFAULT_SUFFIX):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-scm-rule:" + rule["rule_id"] + suffix))


def xccdf_to_scm_yaml(benchmark, suffix=DEFAULT_SUFFIX, os_family="windows", probe_template=None):
    """Convert one XCCDF benchmark into an importable SCM compliance policy.

    ``suffix`` ends the policy name and is part of every uniqueId seed; ``os_family``
    picks the probe from SCM_PROBES (every family uses the same attestation today);
    ``probe_template`` (load_probe_template) replaces the probe's source block.
    """
    suffix = validate_suffix(suffix)
    name = scm_policy_name(benchmark, suffix)
    policy_uid = scm_policy_uid(benchmark, suffix)
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
        check = r["check_content"] or (
            f"Machine check (SCAP edition): OVAL definition {r['oval_ref']}. "
            "The manual STIG for this product carries the prose check text."
            if r.get("oval_ref") else "")
        # The probe runs as PowerShell on every assigned node: the id is validated
        # and the whole text is a single-quoted literal, so no STIG content can
        # expand ($(...), $var) or escape (` or ") inside the script source. A probe
        # template receives the same validated id, inside a quoted scalar only.
        probe_id = scm_probe_id(r["vuln_id"], r["rule_id"])
        lines += [
            f"- displayId: {_yq(r['vuln_id'])}",
            f"  uniqueId: {scm_rule_uid(r, suffix)}",
            f"  name: {_yq(r['title'][:250])}",
            f"  severity: {r['severity'].capitalize()}",
            f"  description: {_yq(r['discussion'])}",
            f"  remediationDescription: {_yq(r['fix_text'])}",
            f"  checkText: {_yq(check)}",
            "  condition: !matches",
            f"    expression: {_yq(probe_id + ' reviewed: True')}",
        ] + scm_probe_lines(probe_id, r["stig_id"], probe_template)
    log_event("build", f"SCM policy \"{name}\" uniqueId {policy_uid}: "
                       f"{len(benchmark['rules'])} manual-review rule(s), OS family {os_family}, "
                       f"probe {'template ' + probe_template[0] if probe_template else 'default'}")
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


def scm_policy_filename(benchmark, stem=None, suffix=DEFAULT_SUFFIX):
    """File name for a converted SCM policy (see SCM_POLICY_SUFFIX); the version
    suffix is part of it, so a _v2 conversion does not overwrite the _v1 file."""
    base = benchmark["benchmark_id"] or benchmark["title"]
    if stem:
        return safe_file_name(f"{stem}.{benchmark['benchmark_id'] or 'benchmark'}{suffix}",
                              SCM_POLICY_SUFFIX)
    return safe_file_name(base + suffix, SCM_POLICY_SUFFIX)


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
    print(resolve_route("auto", benchmarks, os.path.basename(args.path), strict=False)[2])
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


def resolve_route(target, benchmarks, source_name, node_where=None, vendor=None,
                  machine_type=None, strict=True):
    """Decide the destination module for parsed XCCDF benchmarks.

    target: 'auto' | 'network' | 'server' (the dropdown / --target choice).
    Returns ('network', scope, note) with the resolve_ncm_scope dict, or
    ('server', (os_name, swql, family), note). An NCM route whose node scope cannot
    be decided raises ScopeError; with ``strict`` False (parse only) it returns
    ('network', None, note) with the reason in the note instead.
    """
    detected, info = detect_target(benchmarks, source_name)
    if target == "server" or (target == "auto" and detected == "server"):
        os_info = info if detected == "server" else UNKNOWN_SERVER_OS
        why = "detected from the file/benchmark name" if detected == "server" \
            else "forced by the Server Compliance selection"
        note = f"target: Server Configuration Monitor — {os_info[0]} ({why})"
        log_event("route", f"decision: SCM for {source_name} (--target {target}, detected "
                           f"{detected or 'nothing'}); {note}; OS family {os_info[2]}")
        log_event("scope", f"SCM node filter suggested for assignment: {os_info[1]}")
        return "server", os_info, note
    detected_vendor = info if detected == "network" else None
    log_event("route", f"decision: NCM for {source_name} (--target {target}, detected "
                       f"{detected or 'nothing'})",
              "warn" if detected is None and target == "auto" else "info")
    try:
        scope = resolve_ncm_scope(benchmarks, source_name, node_where, vendor, machine_type,
                                  detected_vendor)
    except ScopeError as exc:
        if strict:
            raise
        return "network", None, f"target: NCM — node scope not decided: {exc}"
    where = scope["where"]
    if target == "network" and detected == "server":
        note = ("target: NCM (forced by the Network Compliance selection — the file "
                f"looks like a server STIG); node scope {where}")
    elif scope["explicit"]:
        note = f"target: NCM — node scope {where} (--node-where)"
    elif scope["platform"]:
        note = (f"target: NCM — vendor {scope['vendor']}, platform {scope['platform']} "
                f"detected, node scope {where} ({TENTATIVE_NOTE})")
    else:
        note = f"target: NCM — vendor {scope['vendor']}, node scope {where} ({scope['how']})"
    log_event("route", note)
    return "network", scope, note


def make_reports_from_args(args, benchmarks, scope):
    where = scope["where"] if isinstance(scope, dict) else scope
    return build_reports(
        benchmarks, name=args.name, grouping=args.grouping,
        node_where=where, config_type=args.config_type, mode=args.mode,
        source_path=args.path, enabled=not getattr(args, "disabled", False),
        suffix=getattr(args, "suffix", None),
    )


def route_from_args(args, benchmarks, strict=True):
    return resolve_route(args.target, benchmarks, os.path.basename(args.path),
                         args.node_where, getattr(args, "vendor", None),
                         getattr(args, "machine_type", None), strict=strict)


def probe_template_from_args(args):
    path = getattr(args, "scm_probe_template", None)
    return (load_probe_template(path), path) if path else (None, None)


def cmd_build(args):
    if is_scm_path(args.path):
        info = scan_scm_policy(load_scm_policy(args.path, log=print))
        print(f"\"{info['name']}\" is an SCM compliance policy: the YAML file itself is "
              "the import payload — nothing to build.\n"
              "Import it with:  disa_stig_tool.py import <file> …  "
              "(or POST [yamlText] to Invoke/Orion.PolicyEngine.Policy/ImportPolicy)")
        return
    suffix = validate_suffix(getattr(args, "suffix", None))
    template, template_path = probe_template_from_args(args)
    benchmarks = load_benchmarks(args.path)
    # Offline conversion refuses an undecidable NCM scope the same way an import does:
    # the console file carries the scope, and a guessed one would scope the wrong nodes.
    kind, info, note = route_from_args(args, benchmarks)
    print(note)
    stem = os.path.splitext(os.path.basename(args.path))[0]
    if kind == "server":
        family = os_family(info)
        log_scm_probe_plan(family, template, template_path, log=print)
        for b in benchmarks:
            out = args.output if args.output and len(benchmarks) == 1 else \
                scm_policy_filename(b, stem, suffix)
            write_text_file(out, xccdf_to_scm_yaml(b, suffix, family, template), newline=None)
            print(f"wrote {out}: SCM policy \"{scm_policy_name(b, suffix)}\" — "
                  f"{len(b['rules'])} rules")
        print("import with:  disa_stig_tool.py import <same source> --target server …")
        return
    warning = xml_config_warning(info["where"])
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


def import_scm_benchmarks(swis, benchmarks, os_info, log=print, suffix=DEFAULT_SUFFIX,
                          probe_template=None, template_path=None):
    """Convert each benchmark to an SCM policy and import it via ImportPolicy.

    Every policy's name, uniqueId and rule uniqueIds are checked first
    (scm_collision_check), so a collision refuses the run before anything is created.
    """
    os_name, swql, family = os_info[0], os_info[1], os_family(os_info)
    suffix = validate_suffix(suffix)
    log_scm_probe_plan(family, probe_template, template_path, log=log)
    scm_collision_check(swis, benchmarks, suffix, log=log)
    for b in benchmarks:
        yaml_text = xccdf_to_scm_yaml(b, suffix, family, probe_template)
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
    validate_suffix(getattr(args, "suffix", None))
    swis = logged(connect(args))
    benchmarks = load_benchmarks(args.path)
    kind, info, note = route_from_args(args, benchmarks)
    print(note)
    if kind == "server":
        sys.exit("error: this benchmark routes to SCM, which has no TestRule verb. "
                 "Force NCM with --target network if you meant to test it there.")
    reports = make_reports_from_args(args, benchmarks, info)
    test_reports(swis, reports, config_text=config_text, config_id=args.config_id,
                 limit=args.limit)


def similar_report_names(swis, name):
    """For a remove --name that matched nothing: the report names that start with it
    (typically the same name with its version suffix), as text to append."""
    try:
        rows = swis.query("SELECT TOP 50 PolicyReportID, Name FROM Cirrus.PolicyReports WHERE Name LIKE @p",
                          {"p": like_prefix(name)}) or []
    except (SwisError, ValueError, TypeError):
        return ""
    names = sorted({str(_row_value(r, "Name")) for r in rows
                    if str(_row_value(r, "Name") or "").startswith(name)})
    log_event("remove", f"no report named \"{name}\"; names starting with it: "
                        f"{', '.join(names) or 'none'}")
    if not names:
        return ""
    return ("; reports whose names start with it (since 2.0.0 every name ends in a version "
            "suffix such as _v1): " + ", ".join(f"\"{n}\"" for n in names[:10]))


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
        sys.exit(f"error: no policy report named \"{args.name}\" on this server"
                 + similar_report_names(swis, args.name))
    log_event("remove", f"{len(found)} report(s) named \"{args.name}\": "
                        + ", ".join(str(r.get("PolicyReportID")) for r in found))
    if getattr(args, "delete_children", False):
        print("note: --delete-children is deprecated and ignored. remove now deletes the "
              "report's policies and rules itself, skipping any another report or policy "
              "still uses, and never passes deleteChildren=true.")
    ids = [r["PolicyReportID"] for r in found]
    if not args.dry_run:
        ncm_preflight(swis)
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

    suffix = validate_suffix(getattr(args, "suffix", None))
    template, template_path = probe_template_from_args(args)
    benchmarks = load_benchmarks(args.path)
    kind, info, note = route_from_args(args, benchmarks)
    print(note)
    if kind == "server":
        import_scm_benchmarks(swis, benchmarks, info, suffix=suffix, probe_template=template,
                              template_path=template_path)
        return

    warning = xml_config_warning(info["where"])
    if warning:
        print(warning)
    reports = make_reports_from_args(args, benchmarks, info)
    ncm_preflight(swis)
    # Before the first write: the scope must select nodes, and nothing this run would
    # create (names, PolicyIds, RuleIds) may exist already.
    scope_preflight(swis, info, allow_empty=getattr(args, "allow_empty_scope", False))
    ncm_collision_check(swis, reports, suffix)

    imported, failure, remaining = import_ncm_reports(
        swis, reports, log=print, rollback=not args.no_rollback)
    new_ids = [new_id for _rep, new_id, _n in imported]
    # Reports that completed before a failure are real, verified imports: they
    # get the same caching / disabling as a fully successful run. A refused
    # StartCaching / UpdateReportStatus does not stop the run: the console files
    # that are due below are still written.
    confirmed = finish_ncm_imports(swis, new_ids, disabled=args.disabled,
                                   no_cache=args.no_cache, log=print)
    if failure is None:
        if not confirmed:
            sys.exit("error: the reports were imported and verified, but the requested "
                     + ("disabled state" if args.disabled else "caching")
                     + " could not be confirmed; see the warning above")
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
                        "Default auto: derived from the detected vendor (and, for Cisco, the "
                        "platform's MachineType); an unrecognized network STIG is refused "
                        "unless --vendor or --node-where is given.")
    p.add_argument("--vendor", metavar="NAME",
                   help="the Vendor value the target nodes report (overrides detection; "
                        "needed for an SRG or any unrecognized network STIG)")
    p.add_argument("--machine-type", metavar="PATTERN",
                   help="MachineType LIKE pattern added to the scope, e.g. '%%IOS-XE%%' "
                        "(overrides the Cisco platform table, which is Tentative: its "
                        "MachineType values are still to be verified against a live server)")
    p.add_argument("--suffix", default=DEFAULT_SUFFIX,
                   help="version suffix (_v1 by default, _v<digits>) ending every report, "
                        "policy and SCM policy name and seeding every generated id, so a "
                        "new release can be imported alongside with --suffix _v2")
    p.add_argument("--scm-probe-template", metavar="FILE",
                   help="SCM only: a YAML fragment (an !scm.<type> source tag, then its "
                        "key: value lines) replacing the attestation probe's source; {id} "
                        "inside a quoted value becomes the validated vuln id. See README "
                        "'Testing Linux STIGs in SCM'.")
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
        try:
            resp = self.session.post(f"{self.base}/{path}", json=body, timeout=300)
        except TRANSPORT_ERRORS as exc:   # requests' exceptions derive from OSError
            raise transport_error(exc, path) from exc
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("Message", resp.text)
            except (ValueError, AttributeError):
                detail = resp.text
            raise SwisError(f"HTTP {resp.status_code} from {path}\n{detail}")
        try:
            return resp.json() if resp.text.strip() else None
        except ValueError as exc:         # a body that is not JSON
            raise transport_error(exc, path) from exc

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
        ttk.Label(opts, text="Name suffix").grid(row=4, column=0, sticky="w", **pad)
        self.suffix = tk.StringVar(value=DEFAULT_SUFFIX)
        ttk.Entry(opts, textvariable=self.suffix, width=10).grid(row=4, column=1, sticky="w", **pad)
        self.allow_empty_scope = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, variable=self.allow_empty_scope,
            text="Import even when the NCM node scope matches no node"
        ).grid(row=5, column=1, sticky="w", **pad)

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

    def _resolve_ncm_scope(self, benchmarks, source_name):
        """The NCM scope for the GUI: the node-scope box is --node-where ('auto' derives
        it); an undecidable scope raises ScopeError, which fails that file."""
        target = self._target_choice()
        kind, info, note = resolve_route("network" if target == "server" else target,
                                         benchmarks, source_name, self.node_where.get().strip())
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
        suffix = validate_suffix(self.suffix.get().strip())
        benchmarks = load_benchmarks(path)
        kind, os_info = detect_target(benchmarks, os.path.basename(path))
        family = os_family(os_info if kind == "server" else UNKNOWN_SERVER_OS)
        log_scm_probe_plan(family, log=self._log)
        if not offline:
            scm_collision_check(swis, benchmarks, suffix, log=self._log)
        for b in benchmarks:
            if offline:
                out = os.path.join(folder, scm_policy_filename(b, suffix=suffix))
                write_text_file(out, xccdf_to_scm_yaml(b, suffix, family), newline=None)
                self._summary_line(f"SUCCESS {prefix} wrote {os.path.basename(out)} — "
                                   f"{len(b['rules'])} rules", "success")
            else:
                policy_id, name = import_scm_policy(swis, xccdf_to_scm_yaml(b, suffix, family),
                                                    log=self._log)
                self._summary_line(f"SUCCESS {prefix} \"{name}\" "
                                   f"(PolicyID {policy_id}) — {len(b['rules'])} "
                                   "manual-review rules", "success")
        if family == "linux":
            self._summary_line(f"{prefix} Linux: the SCM probe is Unverified on Linux nodes; "
                               "see README 'Testing Linux STIGs in SCM'", "warn")
        return True

    def _do_ncm(self, swis, path, offline, prefix):
        suffix = validate_suffix(self.suffix.get().strip())
        benchmarks = load_benchmarks(path)
        scope = self._resolve_ncm_scope(benchmarks, os.path.basename(path))
        warning = xml_config_warning(scope["where"])
        if warning:
            self._summary_line(f"{prefix} {warning}", "warn")
            self._show_issue()
        mode = "heuristic" if self.mode.get().startswith("heuristic") else "manual"
        enabled = not self.import_disabled.get()
        reports = build_reports(benchmarks, node_where=scope["where"], mode=mode,
                                source_path=os.path.basename(path), enabled=enabled,
                                suffix=suffix)
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
        ncm_preflight(swis, log=self._log)
        scope_preflight(swis, scope, allow_empty=self.allow_empty_scope.get(), log=self._log)
        ncm_collision_check(swis, reports, suffix, log=self._log)
        imported, failure, remaining = import_ncm_reports(swis, reports, log=self._log)
        for report, _new_id, n_rul in imported:
            self._summary_line(f"SUCCESS {prefix} \"{report['Name']}\" — {n_rul} rules",
                               "success")
        # Reports verified before a failure are still cached or disabled.
        confirmed = finish_ncm_imports(swis, [i for _r, i, _n in imported],
                                       disabled=not enabled,
                                       log=lambda m: self._log(f"{prefix} {m}"))
        if not confirmed:
            state = "Disabled" if not enabled else "cached (StartCaching)"
            self._summary_line(f"{prefix} the imported reports could not be confirmed as "
                               f"{state}; see the detailed log", "warn")
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
    imp.add_argument("--allow-empty-scope", action="store_true",
                     help="import even when the NCM node scope matches no node "
                          "(refused by default, since such a report evaluates nothing)")
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
    rm.add_argument("--name", required=True,
                    help="exact report name, version suffix included (e.g. "
                         "'<zip name> - <benchmark id>_v1')")
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
    """Print the log path (stderr keeps stdout exactly as it was).

    stdout is flushed first: when both streams go to one pipe or file (2>&1), a
    buffered stdout would otherwise land after both announcements, so the end-of-run
    line looked like a second start-of-run line.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError, ValueError):
            pass
    print(f"log file: {path}", file=sys.stderr, flush=True)


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
