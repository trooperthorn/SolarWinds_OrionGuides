# Device poller field mappings

Generated from the twelve supplied exports. OIDs and expressions below are source observations, not live-device validation.

## Fortigate E.poller

PollerID: `9d109dc6-6bb1-42da-bb74-7a2ea796b6f5`. SHA-256: `19dd99e49eba0000c157a96c20e2ac4c0768906db08eb4eaf26736bfc2d2a6a9`.

| Source | Method | OID | Table |
|---|---|---|---|
| fgProcessorUsage | SnmpGetTable | 1.3.6.1.4.1.12356.101.4.4.2.1.2 | fgProcessorTable |
| fgSysMemUsage | SnmpGetNext | 1.3.6.1.4.1.12356.101.4.1.4 |  |
| fgSysMemCapacity | SnmpGetNext | 1.3.6.1.4.1.12356.101.4.1.5 |  |

| Transform | Expression |
|---|---|
| UsedMemoryFormula1 | `Truncate(([fgSysMemCapacity] * 1024) * ([fgSysMemUsage] / 100))` |
| FreeMemoryFormula1 | `Truncate(([fgSysMemCapacity] * 1024) * (1 - ([fgSysMemUsage] / 100)))` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Used Memory | UsedMemoryFormula1 | Double | (absent) |
| Free Memory | FreeMemoryFormula1 | Double | (absent) |
| CPU Load | fgProcessorUsage | Integer | (absent) |

## Ubiquiti Wireless APs.poller

PollerID: `d8916856-b1ee-43a3-b66e-4665495f0ef8`. SHA-256: `db844a9da4171edb50034df86e46b4d5c99de4c3e9e20953aff475d57c9b83cc`.

| Source | Method | OID | Table |
|---|---|---|---|
| Vendor - Ubiquiti APs | SnmpGet | 1.2.840.10036.3.1.2.1.2.3 |  |
| Software Version - Ubiquiti APs | SnmpGet | 1.3.6.1.4.1.41112.1.6.3.6.0 |  |
| sysName | SnmpGetNext | 1.3.6.1.2.1.1.5 |  |
| sysLocation | SnmpGetNext | 1.3.6.1.2.1.1.6 |  |
| sysContact | SnmpGetNext | 1.3.6.1.2.1.1.4 |  |
| sysDescr | SnmpGetNext | 1.3.6.1.2.1.1.1 |  |
| sysObjectID | SnmpGetNext | 1.3.6.1.2.1.1.2 |  |
| MachineType - Ubiquiti APs | SnmpGetNext | 1.2.840.10036.3.1.2.1.3 |  |
| unifiApSystemVersion | SnmpGetNext | 1.3.6.1.4.1.41112.1.6.3.6 |  |

| Transform | Expression |
|---|---|
| SoftwareImageFormula1 | `[MachineType - Ubiquiti APs]+' '+[unifiApSystemVersion]` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | Vendor - Ubiquiti APs | String | true |
| MachineType | MachineType - Ubiquiti APs | String | true |
| IOSVersion | Software Version - Ubiquiti APs | String | true |
| IOSImage | SoftwareImageFormula1 | String | true |
| Contact | sysContact | String | true |
| Location | sysLocation | String | true |
| SysName | sysName | String | true |
| SysObjectId | sysObjectID | String | (absent) |
| Description | sysDescr | String | true |

## Synology NAS.poller

PollerID: `46430070-dd86-4f36-8a8b-b0f06491c8a9`. SHA-256: `77b9e03d79ad6585b870e3da6762c1b59d2c533b92e9ea8ebe60d2e40ada5069`.

| Source | Method | OID | Table |
|---|---|---|---|
| Model | SnmpGetNext | 1.3.6.1.4.1.6574.1.5.1 |  |
| Software | SnmpGetNext | 1.3.6.1.4.1.6574.1.5.3 |  |
| SysName | SnmpGet | 1.3.6.1.2.1.1.5.0 |  |
| Location | SnmpGetNext | 1.3.6.1.2.1.1.6 |  |
| Contact | SnmpGetNext | 1.3.6.1.2.1.1.4 |  |
| SysObjectID | SnmpGetNext | 1.3.6.1.2.1.1.2 |  |
| upGrade | SnmpGetNext | 1.3.6.1.4.1.6574.1.5.4 |  |

| Transform | Expression |
|---|---|
| VendorFormula1 | `'Synology Inc.'` |
| SoftwareImageFormula1 | `SubString([Software],3,Length([Software])-3)` |
| DescriptionFormula1 | `If([upGrade]=1,'DSM Upgrade Available','Running Latest Version of DSM')` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | VendorFormula1 | String | true |
| MachineType | Model | String | true |
| IOSVersion | Software | String | true |
| IOSImage | SoftwareImageFormula1 | String | true |
| Contact | Contact | String | true |
| Location | Location | String | true |
| SysName | SysName | String | true |
| SysObjectId | SysObjectID | String | (absent) |
| Description | DescriptionFormula1 | String | true |

## Juniper J2320.poller

PollerID: `5d2405b7-83f8-4654-9408-8096820282fe`. SHA-256: `af0bfeca1baa9a4302541a98f0af0feaed242766c2d451642fa5fa668497013d`.

| Source | Method | OID | Table |
|---|---|---|---|
| Vendor | SnmpGet | 1.3.6.1.2.1.54.1.1.1.1.2.2 |  |
| sysContact | SnmpGetNext | 1.3.6.1.2.1.1.4 |  |
| sysLocation | SnmpGetNext | 1.3.6.1.2.1.1.6 |  |
| sysName | SnmpGetNext | 1.3.6.1.2.1.1.5 |  |
| sysObjectID | SnmpGetNext | 1.3.6.1.2.1.1.2 |  |
| sysDescr | SnmpGetNext | 1.3.6.1.2.1.1.1 |  |
| jnxBoxDescr | SnmpGetNext | 1.3.6.1.4.1.2636.3.1.2 |  |
| Software Image | SnmpGet | 1.3.6.1.2.1.54.1.1.1.1.3.2 |  |
| Software Version | SnmpGet | 1.3.6.1.2.1.54.1.1.1.1.4.2 |  |

| Transform | Expression |
|---|---|

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | Vendor | String | true |
| MachineType | jnxBoxDescr | String | true |
| IOSVersion | Software Version | String | true |
| IOSImage | Software Image | String | true |
| Contact | sysContact | String | true |
| Location | sysLocation | String | true |
| SysName | sysName | String | true |
| SysObjectId | sysObjectID | String | (absent) |
| Description | sysDescr | String | true |

## Brocade VDX 6940.poller

PollerID: `aac3637a-c846-4931-a43a-abb65b7df688`. SHA-256: `3f8c049f2239e4423cd12464782b4a6a2271913b85babdf52ed51f1c0a56ef3f`.

| Source | Method | OID | Table |
|---|---|---|---|
| swCpuUsage | SnmpGetNext | 1.3.6.1.4.1.1588.2.1.1.1.26.1 |  |
| swMemUsage | SnmpGetNext | 1.3.6.1.4.1.1588.2.1.1.1.26.6 |  |

| Transform | Expression |
|---|---|
| UsedMemoryFormula1 | `(6701156/100)*[swMemUsage]` |
| FreeMemoryFormula1 | `(6701156/100)*(100-[swMemUsage])` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Used Memory | UsedMemoryFormula1 | Double | (absent) |
| Free Memory | FreeMemoryFormula1 | Double | (absent) |
| CPU Load | swCpuUsage | Integer | (absent) |

## Socomec-UPS.poller

PollerID: `4e6b791a-20a4-4f34-a3dc-e11f4ad2d24f`. SHA-256: `514fc2f4bfb58ad9fa0cc0bb9bcb7b99efa418c6ae54df2f5f33da532368d38c`.

| Source | Method | OID | Table |
|---|---|---|---|
| upsIdentManufacturer | SnmpGetNext | 1.3.6.1.2.1.33.1.1.1 |  |
| upsTrapAlarmEntryRemoved | SnmpGetNext | 1.3.6.1.2.1.33.2.4 |  |

| Transform | Expression |
|---|---|

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | (absent) | String | true |
| MachineType | upsIdentManufacturer | String | true |
| IOSVersion | (absent) | String | true |
| IOSImage | (absent) | String | true |
| Contact | (absent) | String | true |
| Location | (absent) | String | true |
| SysName | (absent) | String | true |
| SysObjectId | upsTrapAlarmEntryRemoved | String | (absent) |
| Description | (absent) | String | true |

## Ubiquiti Vendor Name (1).poller

PollerID: `03c50328-2821-4b38-82b7-09714846aebf`. SHA-256: `ee765bc1773a982c37cd268b0671fa209b92b9e1d5e39369c9625f43a901b43c`.

| Source | Method | OID | Table |
|---|---|---|---|
| Ubuquiti | SnmpGet | 1.2.840.10036.3.1.2.1.2.7 |  |

| Transform | Expression |
|---|---|
| SysObjectIdFormula1 | `'Ubiquiti'` |
| VendorFormula1 | `'Ubiquiti'` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | VendorFormula1 | String | true |
| MachineType | Ubuquiti | String | true |
| IOSVersion | (absent) | String | true |
| IOSImage | (absent) | String | true |
| Contact | (absent) | String | true |
| Location | (absent) | String | true |
| SysName | (absent) | String | true |
| SysObjectId | SysObjectIdFormula1 | String | (absent) |
| Description | (absent) | String | true |

## Ubiquiti Vendor Name.poller

PollerID: `03c50328-2821-4b38-82b7-09714846aebf`. SHA-256: `ee765bc1773a982c37cd268b0671fa209b92b9e1d5e39369c9625f43a901b43c`.

| Source | Method | OID | Table |
|---|---|---|---|
| Ubuquiti | SnmpGet | 1.2.840.10036.3.1.2.1.2.7 |  |

| Transform | Expression |
|---|---|
| SysObjectIdFormula1 | `'Ubiquiti'` |
| VendorFormula1 | `'Ubiquiti'` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | VendorFormula1 | String | true |
| MachineType | Ubuquiti | String | true |
| IOSVersion | (absent) | String | true |
| IOSImage | (absent) | String | true |
| Contact | (absent) | String | true |
| Location | (absent) | String | true |
| SysName | (absent) | String | true |
| SysObjectId | SysObjectIdFormula1 | String | (absent) |
| Description | (absent) | String | true |

## APRESIA_AEOS.poller

PollerID: `7dec53ec-2392-4cbc-93b6-4fce4a62c9ea`. SHA-256: `f5df3c1f9b0c4876187ed3d5a83a40374888af0950e6300116623c6ddf1eeac2`.

| Source | Method | OID | Table |
|---|---|---|---|
| hclAeosCpuUtilization | SnmpGet | 1.3.6.1.4.1.278.2.27.1.1.1.1.3.3 |  |
| hclAeosMemoryAvm | SnmpGet | 1.3.6.1.4.1.278.2.27.1.9.1.0 |  |
| hclAeosMemoryFre | SnmpGet | 1.3.6.1.4.1.278.2.27.1.9.2.0 |  |

| Transform | Expression |
|---|---|
| UsedMemoryFormula1 | `KiloToByte([hclAeosMemoryAvm])` |
| FreeMemoryFormula1 | `KiloToByte([hclAeosMemoryFre])` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Used Memory | UsedMemoryFormula1 | Double | (absent) |
| Free Memory | FreeMemoryFormula1 | Double | (absent) |
| CPU Load | hclAeosCpuUtilization | Integer | (absent) |

## APRESIA_AMIOS.poller

PollerID: `829828ec-bc91-4ffb-bf20-c0df1857c8a0`. SHA-256: `68bbe3d9f6e493714693362eeda3602dd44de257f16a45c07ff4b579d0d993ff`.

| Source | Method | OID | Table |
|---|---|---|---|
| hclCpuUtilization | SnmpGetNext | 1.3.6.1.4.1.278.2.1.8.8.1.1 |  |

| Transform | Expression |
|---|---|
| FreeMemoryFormula1 | `0` |
| UsedMemoryFormula1 | `0` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Used Memory | UsedMemoryFormula1 | Double | (absent) |
| Free Memory | FreeMemoryFormula1 | Double | (absent) |
| CPU Load | hclCpuUtilization | Integer | (absent) |

## ApresiaLight.poller

PollerID: `3c790d3c-0520-49cf-806b-6528e7c33696`. SHA-256: `0999dcfac347b614d17e5501a6df4d39a0bd1a96a6b16e5ac6c0c04883168f1d`.

| Source | Method | OID | Table |
|---|---|---|---|
| cpuUtilizationIn5min | SnmpGet | 1.3.6.1.4.1.278.102.0.5.2.1.3.0 |  |
| dramUtilizationUsedDRAM | SnmpGet | 1.3.6.1.4.1.278.102.0.5.2.2.2.0 |  |
| dramUtilizationTotalDRAM | SnmpGet | 1.3.6.1.4.1.278.102.0.5.2.2.1.0 |  |

| Transform | Expression |
|---|---|
| UsedMemoryFormula1 | `KiloToByte([dramUtilizationUsedDRAM])` |
| FreeMemoryFormula1 | `KiloToByte([dramUtilizationTotalDRAM])-KiloToByte([dramUtilizationUsedDRAM])` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Used Memory | UsedMemoryFormula1 | Double | (absent) |
| Free Memory | FreeMemoryFormula1 | Double | (absent) |
| CPU Load | cpuUtilizationIn5min | Integer | (absent) |

## Sonicwall Details.poller

PollerID: `3b4f2ac1-43a2-4e30-9704-c15c8ba602dd`. SHA-256: `fd57243c5ff37ed082274f5b247cda6364daf427cc0bd3f307138cff7c06ff02`.

| Source | Method | OID | Table |
|---|---|---|---|
| snwlSysModel | SnmpGetNext | 1.3.6.1.4.1.8741.2.1.1.1 |  |
| sysObjectID | SnmpGetNext | 1.3.6.1.2.1.1.2 |  |
| sysName | SnmpGetNext | 1.3.6.1.2.1.1.5 |  |
| snwlSysFirmwareVersion | SnmpGetNext | 1.3.6.1.4.1.8741.2.1.1.3 |  |
| sysDescr | SnmpGetNext | 1.3.6.1.2.1.1.1 |  |
| sysLocation | SnmpGetNext | 1.3.6.1.2.1.1.6 |  |
| sysContact | SnmpGetNext | 1.3.6.1.2.1.1.4 |  |

| Transform | Expression |
|---|---|
| MachineTypeFormula1 | `'SonicWALL ' + [snwlSysModel]` |
| VendorFormula1 | `'SonicWALL'` |

| Output | Mapping | Type | Optional |
|---|---|---|---|
| Vendor | VendorFormula1 | String | true |
| MachineType | MachineTypeFormula1 | String | true |
| IOSVersion | snwlSysFirmwareVersion | String | true |
| IOSImage | (absent) | String | true |
| Contact | sysContact | String | true |
| Location | sysLocation | String | true |
| SysName | sysName | String | true |
| SysObjectId | sysObjectID | String | (absent) |
| Description | sysDescr | String | true |
