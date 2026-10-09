# Sectra SaaS Latency Monitoring via SolarWinds Orion — Research Findings

**Date:** 2026-09-21
**Context:** Customer monitoring Sectra Medical (medical.sectra.com, PACS/VNA imaging) SaaS latency/connectivity via SolarWinds Orion. Compiled for future AI/session reference — do not treat as re-verified after this date; re-check facts that are time-sensitive (versions, DNS, PDF availability) before acting on them again.

---

## 1. Sectra facts (target application)

- **Sectra** (medical.sectra.com) is a Swedish medical imaging vendor — PACS/VNA for radiology, pathology, cardiology, orthopaedics. Not to be confused with "Spectra" (initial misname corrected mid-investigation).
- **No public developer API / self-service API portal.** Integration is via standard healthcare interoperability protocols only: DICOM/DICOMweb, HL7, IHE XDS/XDS-I, FHIR/FHIRcast, and a proprietary "Web Content API" for embedding third-party content in the viewer. All gated per customer/partner deployment.
  - Source: [github.com/api-evangelist/sectra-imaging](https://github.com/api-evangelist/sectra-imaging)
- **Status page exists but is gated.** `sectra.statuspage.io` resolves and 302-redirects to a Microsoft Entra ID / SAML login — private, customer/partner-authenticated only. Not publicly scrapable or pollable.
- **github.com/sectra-medical** — six public repos, all dev SDKs/format libraries (pydicomutils, SectraUrlLaunchSdk, dpat_imageanalysisapi_sdk, opentile, wsidicomizer, wsidicom). Nothing operational/health-related.
- **Sectra RapidConnect** — proprietary image transport protocol (not plain DICOM-over-TCP for the viewer path). Uses volume-based representation and dynamic data reduction to adapt to poor networks rather than relying on plain TCP retransmission. Implication: classic TCP retransmit counters at the network layer may not correlate cleanly with perceived image-load slowness, since RapidConnect compensates for loss at the app layer.
  - Source: [ITN — Sectra RIS/PACS with RapidConnect](https://www.itnonline.com/content/sectra-rispacs-rapidconnect)
- **Sectra One Cloud (the actual SaaS/managed offering):**
  - Connects via **Microsoft Azure ExpressRoute** — a private circuit through a connectivity provider, NOT plain public internet. Critical for path-tracing tools (see NetPath caveat below).
  - 99.99% uptime (E3-E4 subscriptions), 99.90% (E1-E2).
  - Sectra explicitly states: *"Sectra will assist you with connection requirements and with testing and validation when connecting"* — i.e., no public port/firewall documentation exists; this is a customer-specific conversation with Sectra, not a published spec.
  - Sectra uses Azure Monitor internally for their own telemetry (not customer-exposed).
  - Source: [Sectra One Cloud SaaS brochure (PDF)](https://medical.sectra.com/wp-content/uploads/sites/3/2023/06/sectra-one-cloud-saas-brochure-2.0.pdf)

### On-prem Sectra ports (if hybrid/on-prem components exist — confirm with customer)
From the [Loadbalancer.org Sectra deployment guide](https://pdfs.loadbalancer.org/sectra-medical-systems-deployment-guide-loadbalancer.pdf):

| Port | Protocol | Service |
|---|---|---|
| 80 | TCP/HTTP | Sectra Healthcare Server (SHS), UniView, IDS7, Digital Pathology |
| 443 | TCP/HTTPS | Same services, HTTPS |

- Sectra RIS DICOM AE default: TCP **4007**, AE title `SECTRA_RIS` (configurable — confirm actual value with customer, do not assume default).
- Standard DICOM association ports (industry-wide, not Sectra-confirmed): 104 or 11112.

**Action item before building any monitoring:** confirm with the customer (1) ExpressRoute vs. internet/VPN connection model, (2) exact client-facing FQDN(s), (3) actual configured DICOM AE port if applicable, (4) whether any component is on-prem/hybrid vs. pure SaaS.

---

## 2. SolarWinds Orion monitoring options (from SolarWinds_OrionGuides repo research)

Repo: [trooperthorn/SolarWinds_OrionGuides](https://github.com/trooperthorn/SolarWinds_OrionGuides)

### WPM (Web Performance Monitor) — `Orion.SEUM.*` in schema
- Synthetic transaction monitoring: records a browser session, replays on schedule from one or more Locations (`Orion.SEUM.Agents`).
- Nested measurement: **Transaction → Step → Request**, each with its own timing — lets you drill from "workflow is slow" down to which specific HTTP request is the bottleneck.
- Recommended for Sectra: record an actual diagnostic workflow (login → open study → load image series), with image retrieval isolated as its own step, since image/series load time is what radiologists actually care about.
- `Orion.SEUM.Agents` (WPM Locations) are NOT the same as `Orion.AgentManagement.Agent` (Orion polling agents) despite similar-looking fields (`AgentId`, `AgentGuid`, `Hostname`, etc.) — no direct join, only a two-hop detour via `Engine.Agents`.
- Doc: [docs/modules/wpm.md](https://github.com/trooperthorn/SolarWinds_OrionGuides/blob/main/docs/modules/wpm.md)

### API Poller — `Orion.APIPoller.*`
- Calls a REST endpoint, extracts values via JSONPath (`Path` type) or response headers (`Header` type).
- **Not usable for Sectra** — no public API/health endpoint exists (see Section 1). Skip this module for this customer unless Sectra later provides a monitoring endpoint under a support agreement.
- Doc: [docs/polling/api-pollers.md](https://github.com/trooperthorn/SolarWinds_OrionGuides/blob/main/docs/polling/api-pollers.md)

### NetPath
- Hop-by-hop path latency tracing to a specific IP/FQDN.
- **Caveat:** if Sectra One Cloud connection is ExpressRoute, NetPath's visibility into the private peering path is limited — Azure doesn't expose ExpressRoute's internal path to ICMP/TCP probes the way public internet hops are exposed. Confirm connection type before promising full-path visibility.
- Point NetPath at the DICOM AE port/IP as well as the HTTP(S) web endpoint for separate path views.

### SAM (Server & Application Monitor) — `Orion.APM.*`
- **TCP Port Monitor** on DICOM AE port: connect success/fail + connect-time as a latency proxy. Does not decode DICOM PDU content — transport layer only.
- **HTTP/HTTPS response-time monitor** on port 80/443 against Sectra web endpoints (UniView/IDS7).
- **Script/WMI/SSH monitor** reading Sectra's own SHS/RIS logs (if Sectra exposes association success/failure counts, retry counts, or timing in local logs/perf counters) — the only way to get true DICOM-association-level detail from SAM; depends entirely on what Sectra's local system exposes.
- Doc: [docs/modules/sam.md](https://github.com/trooperthorn/SolarWinds_OrionGuides/blob/main/docs/modules/sam.md)

### NTA (NetFlow Traffic Analyzer) — `Orion.Netflow.*`
- Flow-record based (router/firewall exports NetFlow/IPFIX), NOT packet-content inspection.
- Gives conversation pairs, volume, duration for traffic on the DICOM port if flow export is configured on the perimeter device.
- Cannot see DICOM PDU types, association-reject reasons, or any payload detail — metadata about the flow only.
- Doc: [docs/modules/nta.md](https://github.com/trooperthorn/SolarWinds_OrionGuides/blob/main/docs/modules/nta.md)

### QoE (Quality of Experience) — `Orion.DPI.*` — **best fit for "app vs. network" latency split**
- True deep packet inspection via a deployed probe (packet capture, not flow export).
- Every measured application reports **ART** (Application Response Time) and **NRT** (Network Response Time) with independent thresholds — lets you separate "slow server" from "slow network" for the same conversation. This is the module's core reason to exist.
- Note: `ART`/`NRT` are NOT formally documented in the SolarWinds schema (no description field, no SDK page for QoE at all) — names are inferred from product convention, not schema-verified.
- **Deployment modes:**
  - `DeployLocalTrafficProbe` — probe on the node itself, sniffing its own NIC traffic.
  - `DeploySpanPortProbe` — probe on a machine receiving mirrored traffic from a switch SPAN/mirror port.
- Both require `admin` rights (not `manageNodes`) and take plain-text machine credentials as positional SWIS verb args — HTTPS only, never commit credentials in scripts.
- **Applications are recognized via a `Filter` expression** on `Orion.DPI.Applications`, matched against a built-in signature catalogue (see Section 3 below — NOT Wireshark syntax for the catalogued/built-in ones).
- Live catalogue confirmed to include:
  | GUID | Name | Category | Risk | Productivity | Relevant? |
  |---|---|---|---|---|---|
  | 21 | ACR-NEMA | File Transfer | Minimal Risk | Mostly | **Yes — DICOM predecessor standard, likely covers DICOM traffic** |
  | 449 | HL7 | Collaboration | No Risk | All Business | Yes, if customer also does HL7 order/result messaging |
  | (many others, e.g. 050Plus, 12306.cn, 123movies — general internet app catalogue, not healthcare-relevant) | | | | | No |
- Doc: [docs/modules/qoe.md](https://github.com/trooperthorn/SolarWinds_OrionGuides/blob/main/docs/modules/qoe.md)

**Recommended layered approach for this customer:**
1. WPM synthetic transaction (image-load workflow) from 2-3 representative sites — primary "is it slow for users" signal.
2. QoE with ACR-NEMA (and HL7 if applicable) assigned to the Sectra-facing node — ART/NRT split to isolate app vs. network cause.
3. SAM TCP Port Monitor on the DICOM AE port — basic reachability/connect-time.
4. NetPath to both the web and DICOM endpoints — path tracing, with the ExpressRoute caveat in mind.
5. NTA on the perimeter device if flow export is available — volume/conversation trending, supporting evidence only.
6. Push customer toward Sectra's own SHS/RIS logs (via SAM script monitor) if true DICOM-association-level diagnosis is needed — SolarWinds cannot decode DICOM PDUs itself.

---

## 3. How SolarWinds DPI/QoE actually works under the hood (live system findings)

Investigated directly on a local machine with both Npcap and a SolarWinds Agent installed (`C:\Program Files\Npcap`, `C:\Program Files (x86)\SolarWinds\Agent`).

### Three-layer architecture
```
Npcap (driver, v1.86)        → raw packet capture off the NIC. Zero application awareness.
navl.dll (NAVL engine)        → application/protocol classification against a signature database.
SolarWinds.DPI.Probe*         → SolarWinds glue: calls NAVL, applies Orion.DPI.Applications
                                 assignments/filters, reports ART/NRT back to Orion server.
```

### Npcap
- GitHub: [nmap/npcap](https://github.com/nmap/npcap)
- Pure packet-capture driver (WinPcap-compatible API). **No application signature database of any kind** — confirmed by inspecting the repo tree directly.
- Local install found: `npcap.sys`, `npcap.inf`, `npcap.cat`, `NPFInstall.exe`, driver install/diagnostic tooling only.
- No VM-specific documentation exists in Npcap's own guide (confirmed via fetch of official guide — no VMXNET3/Hyper-V/virtualization content).
- Known issue: Npcap can spontaneously stop capturing (packets routed to `ps_drop`), requiring capture handle close/reopen — [nmap/npcap#119](https://github.com/nmap/npcap/issues/119).

### NAVL (Network Application Visibility Library) — the actual signature engine
- File: `navl.dll`, found in `C:\Program Files (x86)\SolarWinds\Agent\Plugins\DPIProbe\`
- **Vendor: AppLogic Networks** (rebrand of Qosmos, a well-known commercial DPI/app-recognition SDK vendor)
- Version at time of check: 4.7.0.229 (2025), copyright 2025 AppLogic Networks
- This is a licensed third-party engine — SolarWinds does not write its own classification logic. NAVL holds the actual signature catalogue (ACR-NEMA, HL7, 050Plus, 123movies, everything in `Orion.DPI.Applications`) and performs the pattern matching against captured traffic.
- This explains the source of the app catalogue referenced in Section 2 — cross-referenced entries (050plus, 12306.cn, 123movies) also independently found in Cisco Firepower's Application Detector Reference, consistent with this being a standard commercial DPI signature category, not something custom-built by SolarWinds.

### Live probe config file — `SolarWinds.DPI.ProbeService.apps.config`
Location: `C:\Program Files (x86)\SolarWinds\Agent\Plugins\DPIProbe\SolarWinds.DPI.ProbeService.apps.config`

This is the **live, per-probe application-assignment file** — JSON, hash-versioned, contains `Applications[]` (ID + Filter), `Nodes[]` (node ID + host/IP filter), `Assignments[]` (which app IDs are watched on which node IDs).

**Two distinct filter formats observed, confirmed by direct inspection:**

1. **NAVL internal protocol mnemonics** (bare tokens) — used for built-in/catalogued applications:
   ```
   REDDIT, GITHUB, YOUTUBE, GOOGLE, GOOGPLUS, GOOGADS, GOOGANAL, GOOGAPIS,
   GOOGAPP, GOOGDNS, GOOGMAPS, GTALK, GOOGTRAN, GOOGVIDO, GOOGLBT,
   CLDRDNSH, CMMNCDN, DNS, MDNS, GMAIL
   ```
   These are NOT Wireshark display-filter syntax — they're short-code lookup keys into NAVL's own compiled signature/pattern classifier. Cannot be pasted into Wireshark's filter bar and expected to work the same way.

2. **Wireshark-style display-filter syntax** — used for hand-authored/custom application definitions:
   ```
   HTTP and http.request.url eq "*"
   HTTP and http.request.host eq "*truenas-svr*"
   ```
   Real Wireshark field syntax (`http.request.url`, `http.request.host`, `eq`, wildcards) layered on a protocol match. This is the format to use when building a **custom** application definition that isn't natively in NAVL's catalogue.

**Open question / next verification step:** whether `ACR-NEMA` (GUID 21) resolves to a bare NAVL mnemonic (e.g., `ACRNEMA`) when assigned to a node, or requires a hand-built Wireshark-style filter. A bare mnemonic would confirm NAVL has native protocol-aware DICOM classification (stronger/more accurate than port matching); a Wireshark-style filter would mean it's port/host-based and needs to be scoped manually to the customer's actual DICOM AE port. **Verify by assigning ACR-NEMA to the Sectra-facing NodeID and re-reading `SolarWinds.DPI.ProbeService.apps.config`.**

---

## 4. Open action items / unresolved questions

- [ ] Confirm with customer: Sectra One Cloud connection type (ExpressRoute vs. internet/VPN) — determines NetPath's usefulness.
- [ ] Confirm exact client-facing FQDN(s) used to reach Sectra (for NetPath/WPM/SAM targets).
- [ ] Confirm actual configured DICOM AE port (do not assume 4007/104/11112 — Sectra's is explicitly configurable).
- [ ] Confirm whether deployment is pure SaaS or hybrid (any on-prem SHS/UniView/Pathology components) — changes what "the endpoint" is.
- [ ] Assign ACR-NEMA (and HL7 if relevant) to the Sectra-facing node in QoE, verify filter format and confirm real traffic is being classified (don't assume the built-in definition matches out of the box).
- [ ] If probe host is virtualized: verify vNIC type (VMXNET3/Hyper-V synthetic), tune Rx buffers if VMXNET3, confirm per-port promiscuous mode if Hyper-V, consider physical SPAN port instead of virtual mirroring for reliability.
- [ ] If DICOM-association-level diagnosis (not just reachability) is needed, this requires Sectra's own SHS/RIS logs or third-party DICOM packet decode (e.g., Wireshark's DICOM dissector) — out of scope for what Orion can natively provide.

---

## 5. Key corrections made during this session
- Customer's application is **Sectra**, not "Spectra" (typo in original request).
- QoE's underlying app-classification is **NAVL/AppLogic Networks**, not Npcap — Npcap is capture-only. Initial framing implied SolarWinds did its own classification; the real chain is Npcap → NAVL → SolarWinds glue.
