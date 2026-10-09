# Changelog

## 1.1.0

Brings the plugin back in line with the OrionGuides documentation it is built from.

- **Dashboard variables are bound, not pasted.** `$var`, `${var}`, `${var:format}` and
  `[[var]]` become `@var` with the value in the query's parameters, and
  `IN (${var:csv})` becomes `IN @var` with an array, the documented multi-value form. An
  unquoted plain number is bound as a number and a quoted reference as a string.
  `${var:raw}` is the explicit text-substitution escape hatch for entity and column names.
  References inside a longer string literal or a comment are no longer expanded. Of
  Grafana's built-ins, only the numeric `$__interval_ms`, `$__range_s` and `$__range_ms`
  (`$__x` or `${__x}`) are still substituted, and only when the value is all digits;
  others such as `$__interval` are no longer substituted, and the backend refuses them
  with an error that names the supported macros and built-ins.
- **Parameter names starting with `__` are reserved** for the time macros, and a query
  that sets one is refused.
- **`$__timeFilter` is half open**: `>= @__timeFrom AND < @__timeTo`, so consecutive
  windows neither double count nor drop a boundary row. It was `<=`.
- **Server time basis setting.** UTC stays the default and behaves as before. Server
  local, by IANA zone or fixed offset, binds the time range as zoneless wall-clock time in
  that zone and reads zoneless result timestamps in it. Result timestamps are now always
  normalised to UTC instants.
- **Documentation and messages corrected against the guides.** The UTC claims are now
  labelled as a working hypothesis, with the column time basis and ISO 8601 acceptance
  marked unverified. Port 17778 is described as deprecated in 2023.1, with its default
  listener stopping in 2024.2. The claim that the stock SWIS certificate has no subject
  alternative names is marked unverified. The health check reports the engine version
  rather than calling it the platform version. The README states the Node version CI
  builds with, that Grafana 13.1.0 is the only build and development target, and that the
  scaffold's development Dockerfile pins an older Go than `go.mod`.
- Jest tests for the variable binding, and Go tests for both time bases and the reserved
  parameter names.

## 1.0.0

First release. SWQL queries with time-range macros bound as parameters, table and time
series formats, SWQL-driven variables, a health check against `Orion.Engines`, and verb
invocation gated by a per-data-source allowlist and the Grafana role.
