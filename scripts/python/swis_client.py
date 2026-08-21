#!/usr/bin/env python3
"""A dependency-light SWIS REST client, plus a CLI for ad hoc queries and verb calls.

The official Python client is `orionsdk` (``pip install orionsdk``) and you should
prefer it in production. This file exists because the raw REST contract is small
enough to show in full, and seeing it makes the other clients easier to reason about.

    Query:
        python swis_client.py --host orion.example.com --user admin \\
            query "SELECT TOP 5 Caption, IPAddress FROM Orion.Nodes"

    Query with bound parameters (always prefer this over string formatting):
        python swis_client.py --host orion.example.com --user admin \\
            query "SELECT Caption FROM Orion.Nodes WHERE Status = @s" --param s=2

    Invoke a verb (arguments are POSITIONAL and order matters):
        python swis_client.py --host orion.example.com --user admin \\
            invoke Orion.Nodes PollNow N:42

    Read an entity by URI:
        python swis_client.py --host orion.example.com --user admin \\
            read "swis://orion./Orion/Orion.Nodes/NodeID=42"

The password is read from the SWIS_PASSWORD environment variable, or prompted for.
Never hard-code it and never pass it on the command line, where it lands in shell
history and in the process table.

Endpoint notes, verified against SolarWinds Platform 2026.2:
  base path  /SolarWinds/InformationService/v3/Json
  port       17774 from platform release 2023.1 onward
             17778 was the REST port through 2022.4.1 and is deprecated
             17777 is the SOAP/net.tcp endpoint, not used here
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request

DEFAULT_PORT = 17774
BASE_PATH = "/SolarWinds/InformationService/v3/Json"


class SwisError(RuntimeError):
    """A SWIS request failed. Carries the server's message where one was returned."""


class SwisClient:
    def __init__(self, host, username, password, port=DEFAULT_PORT, verify=True, ca_file=None):
        self.base = f"https://{host}:{port}{BASE_PATH}"
        self.username = username
        self.password = password

        if verify:
            # ca_file lets you trust the server's certificate properly. That is the
            # right fix for the self-signed certificate SWIS ships with: export it once
            # and point at it, rather than turning verification off everywhere.
            self.ctx = ssl.create_default_context(cafile=ca_file)
        else:
            # Only for a lab. This accepts any certificate, so anything on the path can
            # read the credentials you are about to send.
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def _request(self, method, path, body=None):
        url = f"{self.base}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        # Basic auth. SWIS accepts an Orion local account this way.
        import base64

        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")

        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=120) as resp:
                payload = resp.read().decode("utf-8", "replace")
                return json.loads(payload) if payload.strip() else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                # SWIS returns its error text in a JSON "Message" field.
                detail = json.loads(detail).get("Message", detail)
            except (ValueError, AttributeError):
                pass
            raise SwisError(f"HTTP {exc.code} from {url}\n{detail}") from exc
        except urllib.error.URLError as exc:
            raise SwisError(
                f"could not reach {url}: {exc.reason}\n"
                f"check the host, that port {urllib.parse.urlsplit(self.base).port} is open, "
                f"and that you are not pointing at the deprecated 17778 port"
            ) from exc

    def query(self, swql, parameters=None):
        """Run a SWQL query. Returns the list of result rows.

        POST is used rather than GET because it carries bound parameters. Binding
        values is not only safer, it lets SQL Server reuse the execution plan.
        """
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        return (self._request("POST", "Query", body) or {}).get("results", [])

    def invoke(self, entity, verb, *args):
        """Invoke a verb. Arguments are positional; order is the contract.

        Discover the correct order with tools/schema_query.py verb <Entity> <Verb>,
        or on a live server from Metadata.VerbArgument ordered by Position.
        """
        return self._request("POST", f"Invoke/{entity}/{verb}", list(args))

    def read(self, uri):
        """Read one entity by SWIS URI."""
        return self._request("GET", urllib.parse.quote(uri, safe=""))

    def create(self, entity, properties):
        """Create an entity. Returns the URI of the new instance."""
        return self._request("POST", f"Create/{entity}", properties)

    def update(self, uri, properties):
        """Update properties on one entity."""
        return self._request("POST", urllib.parse.quote(uri, safe=""), properties)

    def delete(self, uri):
        """Delete one entity."""
        return self._request("DELETE", urllib.parse.quote(uri, safe=""))

    def bulk_update(self, uris, properties):
        return self._request("POST", "BulkUpdate", {"uris": uris, "properties": properties})

    def bulk_delete(self, uris):
        return self._request("POST", "BulkDelete", {"uris": uris})


def parse_param(raw):
    """Parse a --param name=value pair, coercing JSON values where possible.

    This lets `--param ids=[1,2,3]` bind a multi-valued parameter for `WHERE x IN @ids`
    while `--param name=core-sw-01` still binds a plain string.
    """
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"expected name=value, got {raw!r}")
    name, _, value = raw.partition("=")
    try:
        return name, json.loads(value)
    except ValueError:
        return name, value


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--ca-file", help="PEM bundle trusting the Orion server certificate")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (lab only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("query")
    p.add_argument("swql")
    p.add_argument("--param", action="append", type=parse_param, default=[])

    p = sub.add_parser("invoke")
    p.add_argument("entity")
    p.add_argument("verb")
    p.add_argument("args", nargs="*")

    p = sub.add_parser("read")
    p.add_argument("uri")

    args = ap.parse_args()

    password = os.environ.get("SWIS_PASSWORD") or getpass.getpass(f"Password for {args.user}@{args.host}: ")
    client = SwisClient(
        args.host, args.user, password, port=args.port, verify=not args.insecure, ca_file=args.ca_file
    )

    try:
        if args.cmd == "query":
            result = client.query(args.swql, dict(args.param) or None)
        elif args.cmd == "invoke":
            # Coerce JSON-looking arguments so booleans and numbers arrive with the
            # right type rather than as strings.
            coerced = []
            for a in args.args:
                try:
                    coerced.append(json.loads(a))
                except ValueError:
                    coerced.append(a)
            result = client.invoke(args.entity, args.verb, *coerced)
        else:
            result = client.read(args.uri)
    except SwisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
