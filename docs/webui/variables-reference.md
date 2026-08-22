# Variable reference

The variables SolarWinds publishes, by context. [variables.md](variables.md) explains the
syntax and how the `M=` half resolves; this page is the tables.

**Every name here comes from SolarWinds' documentation.** Where a variable maps onto a SWIS
property, this repository has checked it against the 2026.2 schema and says so. Where it does
not — the `Alerting`, `Generic` and `OrionGroup` contexts, and the syslog and trap lists — the
name is reported as published and **cannot be verified here**.

For members that exist in the schema but appear in no published table, see
[variables-undocumented.md](variables-undocumented.md).

## `N=Alerting` — the alert itself

Properties of the alert, not of the thing it fired on.

| Variable | Description |
| --- | --- |
| `${N=Alerting;M=AlertID}` | The ID of the alert |
| `${N=Alerting;M=AlertName}` | The name of the alert, from **Name of alert definition** in Alert Properties |
| `${N=Alerting;M=AlertDescription}` | The description, from **Description of alert definition** |
| `${N=Alerting;M=AlertDetailsURL}` | URL for more information about the triggered alert |
| `${N=Alerting;M=AlertMessage}` | The message, from **Message displayed when this alert is triggered** in Trigger Actions |
| `${N=Alerting;M=DownTime}` | How long the alert has been active |
| `${N=Alerting;M=ObjectType}` | The object type the alert is monitoring |
| `${N=Alerting;M=Severity}` | The severity, from **Severity of Alert** in Alert Properties |
| `${N=Alerting;M=LastEdit}` | When the alert definition was last edited |
| `${N=Alerting;M=Acknowledged}` | Acknowledged status |
| `${N=Alerting;M=AcknowledgedBy}` | Who acknowledged it |
| `${N=Alerting;M=AcknowledgedTime}` | When it was acknowledged |
| `${N=Alerting;M=Notes}` | The Notes field entered when acknowledging through the Web Console |
| `${N=Alerting;M=AlertTriggerCount}` | Count of triggers |
| `${N=Alerting;M=AlertTriggerTime}` | Date and time of the last event for this alert (Windows Short Date and Short Time) |

Several of these have obvious counterparts on `Orion.AlertConfigurations` (`AlertID`, `Name`,
`Description`, `AlertMessage`, `Severity`, `LastEdit`) and on `Orion.AlertActive`
(`Acknowledged`, `AcknowledgedBy`) — see [../automation/alerts.md](../automation/alerts.md).
Whether the context reads those entities or its own state is **not documented and unverified
here**; the names line up but the mapping is not stated.

## `N=Generic` — the installation and the clock

### Application

| Variable | Description |
| --- | --- |
| `${N=Generic;M=Application}` | SolarWinds application information |
| `${N=Generic;M=Copyright}` | Copyright information |
| `${N=Generic;M=Release}` | Release information |
| `${N=Generic;M=Version}` | Version of the SolarWinds software package |

### Date and time

| Variable | Description |
| --- | --- |
| `${N=Generic;M=AMPM}` | AM/PM indicator |
| `${N=Generic;M=AbreviatedDOW}` | Current day of week, three-character abbreviation |
| `${N=Generic;M=Day}` | Current day of the month |
| `${N=Generic;M=Date;F=Date}` | Current date (Short Date) |
| `${N=Generic;M=DateTime;F=DateTime}` | Current date and time (Long Date and Long Time) |
| `${N=Generic;M=DayOfWeek}` | Current day of the week |
| `${N=Generic;M=DayOfYear}` | Numeric day of the year |
| `${N=Generic;M=Hour}` | Current hour |
| `${N=Generic;M=HH}` | Current hour, two digits, zero padded |
| `${N=Generic;M=Past2Hours}` | Last two hours |
| `${N=Generic;M=Past24Hours}` | Last 24 hours |
| `${N=Generic;M=Last7Days;F=Date}` | Last seven days (Short Date) |
| `${N=Generic;M=PastHour}` | Last hour |
| `${N=Generic;M=LocalDOW}` | Current day of week, localized |
| `${N=Generic;M=LocalMonthName}` | Current month name, localized |
| `${N=Generic;M=LongDate}` | Current date (Long Date) |
| `${N=Generic;M=Month}` | Current numeric month |
| `${N=Generic;M=MM}` | Current month, two digits, zero padded |
| `${N=Generic;M=AbbreviatedMonth}` | Current month, three-character abbreviation |
| `${N=Generic;M=MonthName}` | Full name of the current month |
| `${N=Generic;M=MediumDate}` | Current date (Medium Date) |
| `${N=Generic;M=Minute}` | Current minute, two digits, zero padded |
| `${N=Generic;M=Second}` | Current second, two digits, zero padded |
| `${N=Generic;M=Time}` | Current time (Short Time) |
| `${N=Generic;M=Today;F=Date}` | Today (Short Date) |
| `${N=Generic;M=Year}` | Four-digit year |
| `${N=Generic;M=Year2}` | Two-digit year |
| `${N=Generic;M=Yesterday;F=Date}` | Yesterday (Short Date) |

**`AbreviatedDOW` is spelled with one `b`.** That is how SolarWinds publishes it, beside
`AbbreviatedMonth` with two. Copy it exactly rather than correcting it; a misspelled variable
does not error, it renders empty.

Note also that `Day` and `DayOfWeek` are here while the syslog and trap lists spell the same
ideas `${D}` and `${DayOfWeek}` — the two systems overlap in meaning and not in spelling.

## `N=OrionGroup` — groups

| Variable | Description |
| --- | --- |
| `${N=OrionGroup;M=GroupDetailsURL}` | URL of the Group Details view |
| `${N=OrionGroup;M=GroupFrequency}` | Interval on which membership is evaluated and snapshots taken |
| `${N=OrionGroup;M=GroupID}` | Identifier for the group |
| `${N=OrionGroup;M=GroupMemberDisplayName}` | Display name of the member type: Node, Volume, Component, Application |
| `${N=OrionGroup;M=GroupMemberDisplayNamePlural}` | Plural form: Nodes, Components, Applications |
| `${N=OrionGroup;M=GroupMemberFullName}` | Full name of a member, including location |
| `${N=OrionGroup;M=GroupMemberName}` | Name of a member |
| `${N=OrionGroup;M=GroupMemberPercentAvailability}` | Percent availability when member status is Up, Warning or Critical; 0% otherwise |
| `${N=OrionGroup;M=GroupMemberSnapshotID}` | Identifier of the member snapshot |
| `${N=OrionGroup;M=GroupMemberStatusID}` | Member status identifier |
| `${N=OrionGroup;M=GroupMemberStatusName}` | Member status name |
| `${N=OrionGroup;M=GroupMemberUri}` | SWIS URI of the member |
| `${N=OrionGroup;M=GroupName}` | Name of the group |
| `${N=OrionGroup;M=GroupOwner}` | Product appropriate to the group type |
| `${N=OrionGroup;M=GroupPercentAvailability}` | 100% when group status is Up, Warning or Critical; 0% otherwise |
| `${N=OrionGroup;M=GroupStatusCalculatorID}` | Roll-up calculator: 0 = Mixed, 1 = Worst, 2 = Best |
| `${N=OrionGroup;M=GroupStatusCalculatorName}` | Roll-up calculator name: Mixed, Worst, Best |
| `${N=OrionGroup;M=GroupStatusID}` | Group status identifier |
| `${N=OrionGroup;M=GroupStatus}` | Group status name |
| `${N=OrionGroup;M=GroupStatusRootCause}` | A list of all members that are not Up |

Status identifiers resolve through
[../schema/status-codes.md](../schema/status-codes.md). The two availability variables are
worth reading twice: both report 100% or 0% and neither is a real availability percentage —
`GroupPercentAvailability` is 100 whenever the group is Up, Warning **or** Critical.

## `N=SwisEntity` — node variables

These resolve against `Orion.Nodes` when the alert's `ObjectType` is a node.

**All 60 are declared properties of `Orion.Nodes` in 2026.2**, checked against the extracted
schema. That correspondence is what makes the whole `SwisEntity` context enumerable — see
[variables.md](variables.md#the-member-list-is-the-property-list).

| Variable | Description |
| --- | --- |
| `${N=SwisEntity;M=AgentPort}` | Node SNMP port number |
| `${N=SwisEntity;M=Allow64BitCounters}` | Node allows 64-bit counters (1) or not (0) |
| `${N=SwisEntity;M=AvgResponseTime}` | Average response time to ICMP, in ms |
| `${N=SwisEntity;M=BlockUntil}` | Day, date and time until which polling is blocked |
| `${N=SwisEntity;M=BufferBgMissThisHour}` | Big buffer misses this hour, MIB 1.3.6.1.4.9.2.1.30 |
| `${N=SwisEntity;M=BufferBgMissToday}` | Big buffer misses today |
| `${N=SwisEntity;M=BufferHgMissThisHour}` | Huge buffer misses this hour, MIB 1.3.6.1.4.9.2.1.62 |
| `${N=SwisEntity;M=BufferHgMissToday}` | Huge buffer misses today |
| `${N=SwisEntity;M=BufferLgMissThisHour}` | Large buffer misses this hour, MIB 1.3.6.1.4.9.2.1.38 |
| `${N=SwisEntity;M=BufferLgMissToday}` | Large buffer misses today |
| `${N=SwisEntity;M=BufferMdMissThisHour}` | Medium buffer misses this hour, MIB 1.3.6.1.4.9.2.1.22 |
| `${N=SwisEntity;M=BufferMdMissToday}` | Medium buffer misses today |
| `${N=SwisEntity;M=BufferNoMemThisHour}` | Buffer errors from low memory this hour |
| `${N=SwisEntity;M=BufferNoMemToday}` | Buffer errors from low memory today |
| `${N=SwisEntity;M=BufferSmMissThisHour}` | Small buffer misses this hour, MIB 1.3.6.1.4.9.2.1.14 |
| `${N=SwisEntity;M=BufferSmMissToday}` | Small buffer misses today |
| `${N=SwisEntity;M=Caption}` | User friendly node name |
| `${N=SwisEntity;M=Community}` | Node community string |
| `${N=SwisEntity;M=Contact}` | Contact for the person or group responsible |
| `${N=SwisEntity;M=CPULoad}` | CPU utilization at last poll |
| `${N=SwisEntity;M=CustomPollerLastStatisticsPoll}` | Last poll attempt |
| `${N=SwisEntity;M=CustomPollerLastStatisticsPollSuccess}` | Last successful poll |
| `${N=SwisEntity;M=NodeDescription}` | Node hardware and software |
| `${N=SwisEntity;M=DNS}` | Fully qualified node name |
| `${N=SwisEntity;M=DynamicIP}` | Supports BOOTP/DHCP (1); static (0) |
| `${N=SwisEntity;M=EngineID}` | Polling engine the node is assigned to |
| `${N=SwisEntity;M=GroupStatus}` | Filename of the status icon for the node and its interfaces |
| `${N=SwisEntity;M=IOSImage}` | Family name of Cisco IOS |
| `${N=SwisEntity;M=IOSVersion}` | Cisco IOS version |
| `${N=SwisEntity;M=IP_Address}` | Node IP address |
| `${N=SwisEntity;M=IPAddressType}` | IPv4 or IPv6 |
| `${N=SwisEntity;M=LastBoot}` | Day, date and time of last boot |
| `${N=SwisEntity;M=LastSync}` | Last database and memory synchronization |
| `${N=SwisEntity;M=Location}` | Physical location |
| `${N=SwisEntity;M=MachineType}` | Manufacturer and family or version |
| `${N=SwisEntity;M=MaxResponseTime}` | Maximum ICMP response time, in ms |
| `${N=SwisEntity;M=MemoryUsed}` | Total memory used over the polling interval |
| `${N=SwisEntity;M=NextPoll}` | Next scheduled poll |
| `${N=SwisEntity;M=NextRediscovery}` | Next rediscovery |
| `${N=SwisEntity;M=NodeID}` | Internal unique identifier |
| `${N=SwisEntity;M=PercentLoss}` | ICMP packet loss percentage at last poll |
| `${N=SwisEntity;M=PercentMemoryUsed}` | Percentage of memory used over the polling interval |
| `${N=SwisEntity;M=PollInterval}` | Polling interval, in seconds |
| `${N=SwisEntity;M=RediscoveryInterval}` | Rediscovery interval, in minutes |
| `${N=SwisEntity;M=ResponseTime}` | Response time to the last ICMP request, in ms |
| `${N=SwisEntity;M=Severity}` | Network health score, scored additively (see below) |
| `${N=SwisEntity;M=SNMPVersion}` | SNMP version used by the node |
| `${N=SwisEntity;M=StatCollection}` | Statistics collection frequency, in minutes |
| `${N=SwisEntity;M=Status;F=Status}` | Numerical node status |
| `${N=SwisEntity;M=StatusDescription}` | User friendly status |
| `${N=SwisEntity;M=StatusLED}` | Filename of the status icon |
| `${N=SwisEntity;M=SysName}` | Reply to the SNMP SYS_NAME OID |
| `${N=SwisEntity;M=SysObjectID}` | Vendor OID identifying the node type |
| `${N=SwisEntity;M=SystemUpTime}` | Hundredths of a second since monitoring started (WMI) or since reboot (SNMP) |
| `${N=SwisEntity;M=TotalMemory}` | Total memory available |
| `${N=SwisEntity;M=UnManaged}` | Whether the node is currently unmanaged |
| `${N=SwisEntity;M=UnManageFrom}` | When the node was set unmanaged |
| `${N=SwisEntity;M=UnManageUntil}` | When it is scheduled to be managed again |
| `${N=SwisEntity;M=Vendor}` | Manufacturer or distributor |
| `${N=SwisEntity;M=VendorIcon}` | Filename of the vendor logo |

**`Severity` is a score, not a level.** SolarWinds documents it as additive: in NPM, 1 point
for an interface in a warning state, 1,000 for a down interface and 1,000,000 for a down node;
in SAM, 100 for an application in warning, 200 for critical, 500 for unknown and 1,000 for a
down application. Note that the syslog `${Severity}` below publishes a **different** scale for
the same idea, so the two are not interchangeable.

**SolarWinds publishes `Node.Allow64BitCounters` with a `Node.` prefix.** In 2026.2
`Allow64BitCounters` is a directly declared property of `Orion.Nodes` and `Node` is **not**
one of its 162 navigation properties, so the prefixed form has nothing to resolve through.
The unprefixed form is written above. This is a **discrepancy between the published table and
the schema**, not a verified correction — test both if you need that value.

### Node variables that walk a navigation property

Three published node variables use a dotted `M=`, and all three resolve through a real
navigation property on `Orion.Nodes`. This is the proof that navigation works inside a
variable.

| Variable | Navigates to | Verified |
| --- | --- | --- |
| `${N=SwisEntity;M=Stats.MinResponseTime}` | `Orion.NodesStats` | Property declared |
| `${N=SwisEntity;M=SNMPv3Credentials.…}` | `Orion.SNMPv3Credentials` | All 16 members declared |
| `${N=SwisEntity;M=PCUs.…}` | `Cortex.Orion.PowerControlUnit` | All 16 members declared |

`MinResponseTime` is also a directly declared property of `Orion.Nodes`, so
`${N=SwisEntity;M=MinResponseTime}` and `${N=SwisEntity;M=Stats.MinResponseTime}` are two
paths to the same idea. Which one the engine prefers is **unverified here**.

### SNMPv3 credential variables

**These put credential material into whatever renders them.** SolarWinds publishes all
sixteen, and all sixteen are declared members of `Orion.SNMPv3Credentials`:

| Read variables | Read/write variables |
| --- | --- |
| `${N=SwisEntity;M=SNMPv3Credentials.AuthenticationKey}` | `${N=SwisEntity;M=SNMPv3Credentials.RWAuthenticationKey}` |
| `${N=SwisEntity;M=SNMPv3Credentials.AuthenticationKeyIsPassword}` | `${N=SwisEntity;M=SNMPv3Credentials.RWAuthenticationKeyIsPassword}` |
| `${N=SwisEntity;M=SNMPv3Credentials.AuthenticationMethod}` | `${N=SwisEntity;M=SNMPv3Credentials.RWAuthenticationMethod}` |
| `${N=SwisEntity;M=SNMPv3Credentials.Context}` | `${N=SwisEntity;M=SNMPv3Credentials.RWContext}` |
| `${N=SwisEntity;M=SNMPv3Credentials.PrivacyKey}` | `${N=SwisEntity;M=SNMPv3Credentials.RWPrivacyKey}` |
| `${N=SwisEntity;M=SNMPv3Credentials.PrivacyKeyIsPassword}` | `${N=SwisEntity;M=SNMPv3Credentials.RWPrivacyKeyIsPassword}` |
| `${N=SwisEntity;M=SNMPv3Credentials.PrivacyMethod}` | `${N=SwisEntity;M=SNMPv3Credentials.RWPrivacyMethod}` |
| `${N=SwisEntity;M=SNMPv3Credentials.Username}` | `${N=SwisEntity;M=SNMPv3Credentials.RWUsername}` |

An alert email is not a secret channel. `${N=SwisEntity;M=Community}` is in the same
position — the SNMP community string is a credential and is a published node variable. Whether
the platform redacts any of these at render time is **not documented and is unverified here**;
assume it does not. See [../automation/credentials.md](../automation/credentials.md).

### UPS variables

`PCUs` navigates from `Orion.Nodes` to `Cortex.Orion.PowerControlUnit`. All sixteen published
members are declared there.

| Variable | Description |
| --- | --- |
| `${N=SwisEntity;M=PCUs.BasicBatteryStatus}` | Basic battery status |
| `${N=SwisEntity;M=PCUs.BatteryTemperature}` | Battery temperature |
| `${N=SwisEntity;M=PCUs.BatteryCapacity}` | Battery capacity |
| `${N=SwisEntity;M=PCUs.BatteryPackCount}` | Battery pack count |
| `${N=SwisEntity;M=PCUs.ReplaceIndicator}` | Replace indicator |
| `${N=SwisEntity;M=PCUs.Description}` | Description |
| `${N=SwisEntity;M=PCUs.StatusDescription}` | Status description |
| `${N=SwisEntity;M=PCUs.DetailsUrl}` | Details URL |
| `${N=SwisEntity;M=PCUs.DisplayName}` | Display name |
| `${N=SwisEntity;M=PCUs.Name}` | Name |
| `${N=SwisEntity;M=PCUs.Model}` | Model |
| `${N=SwisEntity;M=PCUs.FirmwareVersion}` | Firmware version |
| `${N=SwisEntity;M=PCUs.OrionNodeId}` | Orion node ID |
| `${N=SwisEntity;M=PCUs.SerialNumber}` | Serial number |
| `${N=SwisEntity;M=PCUs.OutputStatus}` | Output status |
| `${N=SwisEntity;M=PCUs.TimeOnBattery}` | Time on battery |

## Volume variables

SolarWinds publishes these in the **previous-generation form**, without a context. **All
twenty-three are members of `Orion.Volumes` in 2026.2**, checked against the extracted schema
— the same correspondence the node variables show, even though these are written without an
`N=SwisEntity` context.

| Variable | Description |
| --- | --- |
| `${Caption}` | User friendly volume name |
| `${FullName}` | Volume name including parent node and interface captions |
| `${LastSync}` | Last synchronization in database and memory models |
| `${NextPoll}` | Next scheduled poll |
| `${NextRediscovery}` | Next rediscovery |
| `${NodeID}` | Internal identifier of the parent node |
| `${PollInterval}` | Status polling interval, in seconds |
| `${RediscoveryInterval}` | Rediscovery interval, in minutes |
| `${StatCollection}` | Statistics collection frequency, in minutes |
| `${Status}` | Numerical status: 0 Unknown, 1 Up, 2 Shut down, 3 Testing |
| `${StatusLED}` | Filename of the status icon |
| `${VolumeAllocationFailuresThisHour}` | Allocation errors this hour |
| `${VolumeAllocationFailuresToday}` | Allocation errors today |
| `${VolumeDescription}` | User friendly description |
| `${VolumeID}` | Internal identifier |
| `${VolumeIndex}` | Index within the parent node |
| `${VolumePercentUsed}` | Percentage currently in use |
| `${VolumeResponding}` | `Y` when responding to SNMP |
| `${VolumeSize}` | Size, in bytes |
| `${VolumeSpaceAvailable}` | Space available, in bytes |
| `${VolumeSpaceUsed}` | Space used, in bytes |
| `${VolumeType}` | Type as reported by the `hrStorageType` OID |
| `${VolumeTypeIcon}` | Filename of the type icon |

The `${Status}` values here are a **volume-specific** four-value list and are not the
platform status codes in [../schema/status-codes.md](../schema/status-codes.md). Read the
description on the variable, not the general table.

## Syslog alert variables

Previous-generation form, no context. These apply to **DPAIM, NAM, NCM, NPM, NTA, SAM, SRM
and VNQM**, and only when you are **not** using the Orion Log Viewer for syslog. Syslog alerts
also accept any node variable.

### Date and time

| Variable | Description |
| --- | --- |
| `${AbbreviatedDOW}` | Day of week, three-character abbreviation |
| `${AMPM}` | AM or PM |
| `${D}` | Day of the month |
| `${DD}` | Day of the month, two digits, zero padded |
| `${Date}` | Current date (Short Date) |
| `${DateTime}` | Current date and time (Short Date and Short Time) |
| `${DayOfWeek}` | Day of the week |
| `${DayOfYear}` | Numeric day of the year |
| `${H}` | Current hour |
| `${HH}` | Current hour, two digits, zero padded |
| `${Hour}` | Current hour, 24-hour format |
| `${LocalDOW}` | Day of week, localized |
| `${LongDate}` | Current date (Long Date) |
| `${LocalMonthName}` | Month name, localized |
| `${LongTime}` | Current time (Long Time) |
| `${M}` | Current numeric month |
| `${MM}` | Month, two digits, zero padded |
| `${MMM}` | Month, three-character abbreviation |
| `${MediumDate}` | Current date (Medium Date) |
| `${Minute}` | Minute, two digits, zero padded |
| `${Month}` | Full name of the current month |
| `${N}` | Current month and day |
| `${S}` | Current second |
| `${Second}` | Second, two digits, zero padded |
| `${Time}` | Current time (Short Time) |
| `${Year2}` | Two-digit year |
| `${Year}` | Four-digit year |

**`${N}` means "month and day" here.** In the current form `N=` is the context selector. The
two are unrelated and the collision is real, which is one more reason not to mix the forms in
one message.

### Other syslog variables

| Variable | Description |
| --- | --- |
| `${Application}` | SolarWinds application information |
| `${Copyright}` | Copyright information |
| `${DNS}` | Fully qualified node name |
| `${Hostname}` | Host name of the device triggering the alert |
| `${IP_Address}` | IP address of the device triggering the alert |
| `${Message}` | Content of the syslog message |
| `${MessageType}` | The name of the triggered alert |
| `${Severity}` | Network health score (see below) |
| `${Version}` | Version of the SolarWinds software package |

Syslog `${Severity}` publishes this scale: `INTERFACE_UNKNOWN` 1, `INTERFACE_WARNING` 1,
`INTERFACE_DOWN` 1000, `NODE_UNKNOWN` 1000000, `NODE_WARNING` 1000000, `NODE_DOWN` 100000000.
Up scores zero for both nodes and interfaces. **That is a different scale from the node
`Severity` variable above**, which puts a down node at 1,000,000 rather than 100,000,000.
Both are as published; the discrepancy is SolarWinds', not this repository's.

## Trap alert variables

Previous-generation form. These apply to **IPAM, NAM, NCM, NPM, NTA, SAM, SRM and VNQM** with
the Orion Trap Server, and only when you are **not** using the Orion Log Viewer for traps.
Trap alerts also accept any node variable.

### Date and time

The trap list repeats the syslog date and time variables and adds `${AbbreviatedMonth}`,
`${Day}`, `${MMMM}`, `${MediumTime}` and `${MonthName}`, and drops `${N}`. Its format notes
are more specific: `${Date}` is `MM/DD/YYYY`, `${DateTime}` is `MM/DD/YYYY HH:MM`,
`${LongDate}` is `DAY NAME, MONTH DAY, YEAR`, `${LongTime}` is `HH:MM:SS AM/PM`,
`${MediumDate}` is `DD-MMM-YY`, `${MediumTime}` is `HH:MM AM/PM` and `${Time}` is `HH:MM`.

| Variable | Description |
| --- | --- |
| `${AbbreviatedDOW}` | Day of week, three-character abbreviation |
| `${AbbreviatedMonth}` | Month, three-character abbreviation |
| `${AMPM}` | AM or PM |
| `${D}` | Day of the month |
| `${DD}` | Day of the month, two digits, zero padded |
| `${Date}` | Current date, `MM/DD/YYYY` |
| `${DateTime}` | Current date and time, `MM/DD/YYYY HH:MM` |
| `${Day}` | Day of the month |
| `${DayOfWeek}` | Day of the week |
| `${DayOfYear}` | Numeric day of the year |
| `${H}` | Current hour |
| `${HH}` | Current hour, two digits, zero padded |
| `${Hour}` | Current hour, 24-hour format |
| `${LocalDOW}` | Day of week, localized |
| `${LongDate}` | Current date, `DAY NAME, MONTH DAY, YEAR` |
| `${LongTime}` | Current time, `HH:MM:SS AM/PM` |
| `${M}` | Current numeric month |
| `${MM}` | Month, two digits, zero padded |
| `${MMM}` | Month, three-character abbreviation |
| `${MMMM}` | Full name of the current month |
| `${MediumDate}` | Current date, `DD-MMM-YY` |
| `${MediumTime}` | Current time, `HH:MM AM/PM` |
| `${Minute}` | Minute, two digits, zero padded |
| `${MonthName}` | Full name of the current month |
| `${S}` | Current second |
| `${Second}` | Second, two digits, zero padded |
| `${Time}` | Current time, `HH:MM` |
| `${Year}` | Four-digit year |
| `${Year2}` | Two-digit year |

`${MMMM}` and `${MonthName}` are published with the same description. `${Day}` and `${D}`
likewise.

### Other trap variables

| Variable | Description |
| --- | --- |
| `${Application}` | SolarWinds application information |
| `${Community}` | Node community string |
| `${Copyright}` | Copyright information |
| `${DNS}` | Fully qualified node name |
| `${Hostname}` | Host name of the device triggering the trap |
| `${IP_Address}` | IP address of the device triggering the alert |
| `${Message}` | Message sent with the trap, shown in Trap Details in Trap Viewer |
| `${MessageType}` | Name or type of trap triggered |
| `${Raw}` | Raw numerical values for properties sent in the incoming trap |
| `${RawValue}` | The same as `${Raw}` |
| `${vbData1}` | Trap variable binding value |
| `${vbName1}` | Trap variable binding name |

`${vbName1}` and `${vbData1}` are published with a `1` suffix and no statement of how to reach
the second and later bindings. Whether `${vbName2}` and beyond exist is **not documented and
is unverified here**.

## See also

- [variables.md](variables.md) — the syntax, the contexts, `${SQL:…}`, and how to enumerate
- [variables-undocumented.md](variables-undocumented.md) — members that exist in the schema
  and appear in no published table
- [../automation/alerts.md](../automation/alerts.md) — where these are stored and how alerts
  are driven through the API
- [../schema/status-codes.md](../schema/status-codes.md) — the status integers
