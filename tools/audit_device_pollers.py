"""Inert, read-only inventory of Device Studio XML exports.

Usage: python audit_device_pollers.py FILE.poller [FILE.poller ...] > evidence.json
Does not import pollers, query devices, or evaluate expressions. Exit 2 on malformed
input. Review notes are evidence prompts, not a certification of runtime behavior.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

NS = 'http://schemas.solarwinds.com/2008/DeviceStudio'
XSI = '{http://www.w3.org/2001/XMLSchema-instance}type'
N = {'d': NS}

def local(name):
    return name.rsplit('}', 1)[-1]

def parse_xml(text):
    if re.search(r'<!\s*(DOCTYPE|ENTITY)\b', text, re.I):
        raise ValueError('DTD/entity declarations are not accepted')
    return ET.fromstring(text)

def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    return data.decode('utf-8-sig')

def val(node, name):
    child = node.find('d:' + name, N)
    return None if child is None else child.text

def tree(node):
    # Preserve namespace URIs, attributes, element order and text; formatting tails
    # are not part of this structural view. Raw nested XML is retained separately.
    return {'tag': node.tag, 'attributes': dict(node.attrib), 'text': node.text,
            'children': [tree(c) for c in node]}

def output_property(node):
    t = node.find('d:Type', N)
    return {'name': val(node, 'Name'), 'mapping': val(node, 'Mapping'),
            'optional': val(node, 'Optional'),
            'type': None if t is None else t.attrib.get(XSI)}

def audit(path):
    data = path.read_bytes()
    if len(data) > 10_000_000:
        raise ValueError('File exceeds 10 MB audit limit')
    root = parse_xml(decode(data))
    if root.tag != '{' + NS + '}Poller':
        raise ValueError('Not a Device Studio Poller document')
    metadata = {}
    for node in root:
        if local(node.tag) != 'Configs':
            if local(node.tag) in metadata:
                raise ValueError('Duplicate metadata element')
            metadata[local(node.tag)] = (node.text or '').strip()
    configs = {}
    for node in root.iter():
        if local(node.tag) != 'KeyValueOfanyTypeanyType':
            continue
        parts = {local(c.tag): c for c in node}
        key = parts['Key'].text
        if key in configs:
            raise ValueError('Duplicate config key: ' + str(key))
        raw = parts['Value'].text
        config = parse_xml(raw)
        configs[key] = {'raw_xml': raw, 'tree': tree(config)}
    if not {'inventory', 'polling'} <= configs.keys():
        raise ValueError('Missing inventory/polling configuration')
    inv = parse_xml(configs['inventory']['raw_xml'])
    poll = parse_xml(configs['polling']['raw_xml'])
    checks = []
    for node in inv.findall('d:Operations/*', N):
        oid = node.find('d:Oid', N)
        checks.append({'operation': node.attrib.get(XSI), 'method': val(node, 'Method'),
                       'oid': None if oid is None else val(oid, 'OID')})
    sources = []
    tables = []
    for node in poll.findall('d:DataSourceCreateConfig/d:Operations/*', N):
        table = val(node, 'Table')
        if table:
            tables.append(table)
        for oid in node.findall('.//d:Oid', N):
            sources.append({'operation': node.attrib.get(XSI), 'table': table,
                            'name': val(oid, 'Name'), 'oid': val(oid, 'OID')})
    transforms = []
    for node in poll.findall('d:DataSourceTransformConfig/d:Operations/*', N):
        expr = val(node, 'Expression')
        output = node.find('d:Output', N)
        transforms.append({'operation': node.attrib.get(XSI),
                           'output': None if output is None else val(output, 'Property'),
                           'expression': expr,
                           'references': re.findall(r'\[([^\]]+)\]', expr or '')})
    outputs = [output_property(n) for n in poll.findall('.//d:OutputProperty', N)]
    output_tables = [{'name': val(n, 'Name'), 'mapping': val(n, 'Mapping')}
                     for n in poll.findall('.//d:OutputTable', N)]
    names = [s['name'] for s in sources] + [t['output'] for t in transforms]
    defined = set(names)
    unresolved = sorted({ref for t in transforms for ref in t['references'] if ref not in defined}
                        | {o['mapping'] for o in outputs if o['mapping'] and o['mapping'] not in defined})
    undefined_tables = [t['mapping'] for t in output_tables if t['mapping'] not in tables]
    duplicate_names = [k for k, v in collections.Counter(names).items() if v > 1]
    notes = []
    if checks and all(c['operation'] == 'OidExists' for c in checks):
        notes.append('Inventory contains existence checks only; no explicit value comparison is present.')
    transform_map = {t['output']: t['expression'] for t in transforms}
    for out in outputs:
        expr = transform_map.get(out['mapping'])
        if out['name'] == 'SysObjectId' and expr and re.fullmatch(r"\s*'[^']*'\s*", expr):
            notes.append('SysObjectId is supplied by a constant string; verify OID semantics, not just output type.')
        if out['name'] in ('Used Memory', 'Free Memory') and expr == '0':
            notes.append(out['name'] + ' is synthetic zero, not a measurement.')
    return {'file': path.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'metadata': metadata, 'outer_tree': tree(root), 'configs': configs,
            'inventory_checks': checks, 'sources': sources, 'transforms': transforms,
            'outputs': outputs, 'output_tables': output_tables,
            'unresolved_references': unresolved, 'undefined_output_tables': undefined_tables,
            'duplicate_source_or_transform_names': duplicate_names,
            'review_notes': notes}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        records = [audit(p) for p in args.files]
        groups = collections.defaultdict(list)
        for r in records:
            groups[r['metadata'].get('PollerID')].append(r)
        duplicates = [{'poller_id': key, 'files': [r['file'] for r in rows],
                       'byte_identical': len({r['sha256'] for r in rows}) == 1}
                      for key, rows in groups.items() if len(rows) > 1]
        report = {'method': 'Offline XML parsing; no SNMP, formula evaluation, or import',
                  'file_count': len(records), 'distinct_poller_ids': len(groups),
                  'inventory_check_count': sum(len(r['inventory_checks']) for r in records),
                  'distinct_source_oids': sorted({s['oid'] for r in records for s in r['sources']}),
                  'duplicate_poller_ids': duplicates, 'pollers': records}
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        print()
    except (ValueError, OSError, ET.ParseError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')

if __name__ == '__main__':
    main()
