# curl examples

| Script | Does |
| --- | --- |
| [swis-rest-examples.sh](swis-rest-examples.sh) | The SWIS REST surface on the wire: query, invoke, CRUD, bulk, introspection |

Every other client is a wrapper around these calls, so this is the fastest way to prove a
problem is in your code rather than in the platform. If curl works and your code does not,
the problem is your code.

```bash
export SWIS_HOST=orion.example.com
export SWIS_USER=admin
export SWIS_PASSWORD='...'      # exported, never inline, so it stays out of shell history

./swis-rest-examples.sh query-basic
./swis-rest-examples.sh query-parameterized
./swis-rest-examples.sh describe-verb Orion.Nodes Unmanage
./swis-rest-examples.sh invoke-pollnow 42
```

Run it with no arguments for the full command list.

## Endpoint facts

| Setting | Value |
| --- | --- |
| Base path | `/SolarWinds/InformationService/v3/Json` |
| Port | 17774 from platform release 2023.1 (17778 deprecated, 17777 is SOAP) |
| Transport | HTTPS only |
| Auth | HTTP Basic with an Orion account |

## TLS

SWIS presents a self-signed certificate, so the first connection fails verification. Trust
it rather than switching verification off:

```bash
openssl s_client -connect "$SWIS_HOST:17774" -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > orion-ca.pem
export SWIS_CACERT=orion-ca.pem
```

`SWIS_INSECURE=1` disables verification instead. That is fine in a lab and nowhere else:
it lets anything on the network path read the credentials you are sending.
