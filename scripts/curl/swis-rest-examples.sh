#!/usr/bin/env bash
#
# The SWIS REST surface, on the wire, with nothing in between.
#
# Every other client (PowerShell, Python, C#) is a wrapper around these calls, so this
# is the fastest way to prove a problem is in your code rather than in the platform.
#
# Endpoint facts, verified against SolarWinds Platform 2026.2:
#   base path  /SolarWinds/InformationService/v3/Json
#   port       17774 from platform release 2023.1 onward.
#              17778 was the REST port through 2022.4.1 and is deprecated.
#              17777 is the SOAP/net.tcp endpoint and does not serve these routes.
#   auth       HTTP Basic with an Orion account.
#   transport  HTTPS only.
#
# Usage:
#   export SWIS_HOST=orion.example.com
#   export SWIS_USER=admin
#   export SWIS_PASSWORD='...'        # exported, never inline, so it stays out of history
#   ./swis-rest-examples.sh query-basic
#
# SWIS ships with a self-signed certificate. The right fix is to trust it:
#   openssl s_client -connect "$SWIS_HOST:17774" -showcerts </dev/null 2>/dev/null \
#     | openssl x509 -outform PEM > orion-ca.pem
#   export SWIS_CACERT=orion-ca.pem
# Setting SWIS_INSECURE=1 disables verification instead, which is acceptable in a lab
# and nowhere else: it lets anything on the path read the credentials you are sending.

set -euo pipefail

: "${SWIS_HOST:?set SWIS_HOST to the Orion server hostname}"
: "${SWIS_USER:?set SWIS_USER to an Orion account}"
: "${SWIS_PASSWORD:?set SWIS_PASSWORD (export it; do not inline it)}"

PORT="${SWIS_PORT:-17774}"
BASE="https://${SWIS_HOST}:${PORT}/SolarWinds/InformationService/v3/Json"

curl_args=(--silent --show-error --fail-with-body --user "${SWIS_USER}:${SWIS_PASSWORD}")
if [[ -n "${SWIS_CACERT:-}" ]]; then
  curl_args+=(--cacert "${SWIS_CACERT}")
elif [[ "${SWIS_INSECURE:-0}" == "1" ]]; then
  curl_args+=(--insecure)
fi

pretty() { if command -v jq >/dev/null 2>&1; then jq .; else cat; fi; }

# ---------------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------------

# GET /Query with the SWQL url-encoded. Fine for a quick read, but it cannot carry
# bound parameters, so prefer POST for anything with a variable in it.
query_basic() {
  curl "${curl_args[@]}" --get "${BASE}/Query" \
    --data-urlencode "query=SELECT TOP 5 NodeID, Caption, IPAddress, Status FROM Orion.Nodes ORDER BY Caption" \
    | pretty
}

# POST /Query with bound parameters. This is the form to reach for by default:
# values stay out of the query text, plans get reused, and a whole class of
# injection bugs disappears.
query_parameterized() {
  curl "${curl_args[@]}" -X POST "${BASE}/Query" \
    -H 'Content-Type: application/json' \
    -d '{
          "query": "SELECT NodeID, Caption, IPAddress FROM Orion.Nodes WHERE Status = @status ORDER BY Caption",
          "parameters": { "status": 2 }
        }' \
    | pretty
}

# A multi-valued parameter for WHERE x IN @name. Encode the value as a JSON array;
# do not build a comma-separated string yourself.
query_multivalue() {
  curl "${curl_args[@]}" -X POST "${BASE}/Query" \
    -H 'Content-Type: application/json' \
    -d '{
          "query": "SELECT NodeID, Caption FROM Orion.Nodes WHERE NodeID IN @ids",
          "parameters": { "ids": [1, 2, 3] }
        }' \
    | pretty
}

# Paging. WITH ROWS a TO b is one-based and inclusive; WITH TOTALROWS makes the
# response carry the unpaged count so you know how many pages there are.
query_paged() {
  curl "${curl_args[@]}" -X POST "${BASE}/Query" \
    -H 'Content-Type: application/json' \
    -d '{
          "query": "SELECT NodeID, Caption FROM Orion.Nodes ORDER BY NodeID WITH ROWS 1 TO 25 WITH TOTALROWS"
        }' \
    | pretty
}

# ---------------------------------------------------------------------------------
# Invoke
# ---------------------------------------------------------------------------------

# The body is a POSITIONAL JSON array. Names never appear on the wire, so argument
# order is the entire contract. Confirm it with:
#     python3 tools/schema_query.py verb Orion.Nodes PollNow
# or, on a live server, from Metadata.VerbArgument ordered by Position.
invoke_pollnow() {
  local node_id="${1:?usage: invoke_pollnow <NodeID>}"
  curl "${curl_args[@]}" -X POST "${BASE}/Invoke/Orion.Nodes/PollNow" \
    -H 'Content-Type: application/json' \
    -d "[\"N:${node_id}\"]" \
    | pretty
}

# Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)
# Times are absolute when isRelative is false, so send UTC.
invoke_unmanage() {
  local node_id="${1:?usage: invoke_unmanage <NodeID> [hours]}"
  local hours="${2:-1}"
  local start end
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  end="$(date -u -d "+${hours} hours" +%Y-%m-%dT%H:%M:%SZ)"
  curl "${curl_args[@]}" -X POST "${BASE}/Invoke/Orion.Nodes/Unmanage" \
    -H 'Content-Type: application/json' \
    -d "[\"N:${node_id}\", \"${start}\", \"${end}\", false, false]" \
    | pretty
}

invoke_remanage() {
  local node_id="${1:?usage: invoke_remanage <NodeID>}"
  curl "${curl_args[@]}" -X POST "${BASE}/Invoke/Orion.Nodes/Remanage" \
    -H 'Content-Type: application/json' \
    -d "[\"N:${node_id}\"]" \
    | pretty
}

# ---------------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------------

# Read one entity by URI. The URI must be url-encoded into the path; --get with
# --data-urlencode will not do it, so encode it yourself.
read_entity() {
  local uri="${1:?usage: read_entity <swis-uri>}"
  local encoded
  encoded="$(printf '%s' "$uri" | jq -sRr @uri)"
  curl "${curl_args[@]}" "${BASE}/${encoded}" | pretty
}

# Update properties on one entity. Only the properties you send are changed.
update_entity() {
  local uri="${1:?usage: update_entity <swis-uri> <json>}"
  local body="${2:?usage: update_entity <swis-uri> <json>}"
  local encoded
  encoded="$(printf '%s' "$uri" | jq -sRr @uri)"
  curl "${curl_args[@]}" -X POST "${BASE}/${encoded}" \
    -H 'Content-Type: application/json' -d "$body" | pretty
}

# Update many entities in one call. Cheaper and more consistent than a loop.
bulk_update() {
  curl "${curl_args[@]}" -X POST "${BASE}/BulkUpdate" \
    -H 'Content-Type: application/json' \
    -d '{
          "uris": [
            "swis://orion./Orion/Orion.Nodes/NodeID=1",
            "swis://orion./Orion/Orion.Nodes/NodeID=2"
          ],
          "properties": { "Location": "Datacentre B" }
        }' \
    | pretty
}

# ---------------------------------------------------------------------------------
# Introspection: ask the server what it supports, rather than guessing
# ---------------------------------------------------------------------------------

# The arguments of a verb, in the order Invoke expects them.
describe_verb() {
  local entity="${1:?usage: describe_verb <Entity> <Verb>}"
  local verb="${2:?usage: describe_verb <Entity> <Verb>}"
  curl "${curl_args[@]}" -X POST "${BASE}/Query" \
    -H 'Content-Type: application/json' \
    -d "{
          \"query\": \"SELECT Position, Name, Type, IsOptional, Summary FROM Metadata.VerbArgument WHERE EntityName = @e AND VerbName = @v ORDER BY Position\",
          \"parameters\": { \"e\": \"${entity}\", \"v\": \"${verb}\" }
        }" \
    | pretty
}

# The key properties of an entity, which you need to build a URI.
describe_keys() {
  local entity="${1:?usage: describe_keys <Entity>}"
  curl "${curl_args[@]}" -X POST "${BASE}/Query" \
    -H 'Content-Type: application/json' \
    -d "{
          \"query\": \"SELECT Name, Type FROM Metadata.Property WHERE Entity.FullName = @e AND IsKey = true\",
          \"parameters\": { \"e\": \"${entity}\" }
        }" \
    | pretty
}

usage() {
  cat <<'EOF'
Commands:
  query-basic                        GET /Query
  query-parameterized                POST /Query with bound parameters
  query-multivalue                   IN @ids with a JSON array
  query-paged                        WITH ROWS / WITH TOTALROWS
  invoke-pollnow <NodeID>            force an immediate poll
  invoke-unmanage <NodeID> [hours]   open a maintenance window
  invoke-remanage <NodeID>           close it early
  read-entity <uri>                  GET one entity
  update-entity <uri> <json>         POST property changes
  bulk-update                        BulkUpdate example
  describe-verb <Entity> <Verb>      a verb's arguments in order
  describe-keys <Entity>             an entity's key properties
EOF
}

cmd="${1:-usage}"
shift || true
case "$cmd" in
  query-basic)         query_basic ;;
  query-parameterized) query_parameterized ;;
  query-multivalue)    query_multivalue ;;
  query-paged)         query_paged ;;
  invoke-pollnow)      invoke_pollnow "$@" ;;
  invoke-unmanage)     invoke_unmanage "$@" ;;
  invoke-remanage)     invoke_remanage "$@" ;;
  read-entity)         read_entity "$@" ;;
  update-entity)       update_entity "$@" ;;
  bulk-update)         bulk_update ;;
  describe-verb)       describe_verb "$@" ;;
  describe-keys)       describe_keys "$@" ;;
  *)                   usage ;;
esac
