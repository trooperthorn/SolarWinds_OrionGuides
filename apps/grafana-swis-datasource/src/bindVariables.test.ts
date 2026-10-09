import type { TemplateSrv } from '@grafana/runtime';

import { bindVariables, paramName, templateResolver, VariableResolver } from './bindVariables';

function resolver(vars: Record<string, string | string[]>, builtins: Record<string, string> = {}): VariableResolver {
  return {
    has: (name) => name in vars,
    value: (name) => vars[name],
    raw: (name) => {
      const v = vars[name];
      return Array.isArray(v) ? v.join(',') : v;
    },
    builtin: (name) => builtins[name] ?? '${' + name + '}',
  };
}

const vars = resolver({
  node: '42',
  nodes: ['1', '2', '3'],
  caption: "O'Brien-DC1",
  vendor: 'Cisco',
  entity: 'Orion.Nodes',
  version: '007',
  '1st': 'x',
});

describe('bindVariables', () => {
  it('binds every reference syntax as a parameter of the same name', () => {
    for (const ref of ['$node', '${node}', '${node:csv}', '[[node]]', '[[node:csv]]']) {
      const out = bindVariables(`SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID = ${ref}`, vars);
      expect(out.swql).toBe('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID = @node');
      expect(out.parameters).toEqual({ node: 42 });
    }
  });

  it('turns an IN list into IN @name with an array, without parentheses', () => {
    const out = bindVariables('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID IN (${nodes:csv})', vars);
    expect(out.swql).toBe('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID IN @nodes');
    expect(out.parameters).toEqual({ nodes: [1, 2, 3] });

    // A single selection in an IN list is still bound as a one-element array.
    const one = bindVariables('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID in ( $node )', vars);
    expect(one.swql).toBe('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID in @node');
    expect(one.parameters).toEqual({ node: [42] });

    const bare = bindVariables('SELECT n.Caption FROM Orion.Nodes n WHERE (n.NodeID IN $node)', vars);
    expect(bare.swql).toBe('SELECT n.Caption FROM Orion.Nodes n WHERE (n.NodeID IN @node)');
    expect(bare.parameters).toEqual({ node: [42] });

    const tight = bindVariables('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID IN(${nodes})', vars);
    expect(tight.swql).toBe('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID IN @nodes');

    // Two references in one list are not the whole list, so each is bound as a scalar.
    const pair = bindVariables('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID IN ($node, $version)', vars);
    expect(pair.swql).toBe('SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID IN (@node, @version)');
    expect(pair.parameters).toEqual({ node: 42, version: '007' });
  });

  it('keeps a value with quotes and comment markers out of the statement text', () => {
    const out = bindVariables("SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption = '${caption}'", vars);
    expect(out.swql).toBe('SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption = @caption');
    expect(out.parameters).toEqual({ caption: "O'Brien-DC1" });
    expect(out.swql).not.toContain('Brien');
  });

  it('binds a quoted reference as a string and an unquoted canonical number as a number', () => {
    const quoted = bindVariables("SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption = '$node'", vars);
    expect(quoted.parameters).toEqual({ node: '42' });
    const leadingZero = bindVariables('SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption = $version', vars);
    expect(leadingZero.parameters).toEqual({ version: '007' });
    const forced = bindVariables('SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption IN (${nodes:singlequote})', vars);
    expect(forced.parameters).toEqual({ nodes: ['1', '2', '3'] });
  });

  it('substitutes text only for the explicit :raw format', () => {
    const out = bindVariables('SELECT TOP 10 e.Caption FROM ${entity:raw} e WHERE e.Vendor = $vendor', vars);
    expect(out.swql).toBe('SELECT TOP 10 e.Caption FROM Orion.Nodes e WHERE e.Vendor = @vendor');
    expect(out.parameters).toEqual({ vendor: 'Cisco' });
  });

  it('leaves built-ins, time macros, unknown names and comments alone', () => {
    const swql = [
      'SELECT c.DateTime FROM Orion.CPULoad c',
      'WHERE $__timeFilter(c.DateTime) AND c.NodeID = $node AND c.AvgLoad > $unknown',
      "  AND c.Node.Caption LIKE '%$vendor%' -- $nodes is commented out",
    ].join('\n');
    const out = bindVariables(swql, vars);
    expect(out.swql).toBe(
      [
        'SELECT c.DateTime FROM Orion.CPULoad c',
        'WHERE $__timeFilter(c.DateTime) AND c.NodeID = @node AND c.AvgLoad > $unknown',
        "  AND c.Node.Caption LIKE '%$vendor%' -- $nodes is commented out",
      ].join('\n')
    );
    expect(out.parameters).toEqual({ node: 42 });
  });

  it('never overwrites a parameter set on the query, and reuses names for identical values', () => {
    const out = bindVariables(
      'SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID = $node OR n.NodeID = ${node} OR n.NodeID IN ($node)',
      vars,
      { node: 7 }
    );
    expect(out.swql).toBe(
      'SELECT n.Caption FROM Orion.Nodes n WHERE n.NodeID = @node_2 OR n.NodeID = @node_2 OR n.NodeID IN @node_3'
    );
    expect(out.parameters).toEqual({ node: 7, node_2: 42, node_3: [42] });
  });

  it('makes a parameter name SWQL can take', () => {
    expect(paramName('node')).toBe('node');
    expect(paramName('1st')).toBe('_1st');
    expect(bindVariables('SELECT n.Caption FROM Orion.Nodes n WHERE n.Caption = $1st', vars).swql).toBe(
      'SELECT n.Caption FROM Orion.Nodes n WHERE n.Caption = @_1st'
    );
  });

  it('respects escaped quotes inside literals', () => {
    const out = bindVariables(
      "SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption = 'it''s $node' AND n.NodeID = $node",
      vars
    );
    expect(out.swql).toBe("SELECT n.NodeID FROM Orion.Nodes n WHERE n.Caption = 'it''s $node' AND n.NodeID = @node");
  });
});

describe('numeric Grafana built-ins', () => {
  const withBuiltins = resolver(
    { node: '42' },
    { __interval_ms: '60000', __range_s: '86400', __range_ms: '86400000', __interval: '1m' }
  );

  it('substitutes $__interval_ms, $__range_s and $__range_ms as integer text', () => {
    const out = bindVariables(
      'SELECT c.DateTime FROM Orion.CPULoad c WHERE c.NodeID = $node AND x = $__interval_ms AND y = ${__range_s} AND z = $__range_ms',
      withBuiltins
    );
    expect(out.swql).toBe(
      'SELECT c.DateTime FROM Orion.CPULoad c WHERE c.NodeID = @node AND x = 60000 AND y = 86400 AND z = 86400000'
    );
    expect(out.parameters).toEqual({ node: 42 });
  });

  it('leaves a non-numeric or unresolved value, other built-ins, and other forms alone', () => {
    const odd = resolver({}, { __interval_ms: '60000; DROP', __range_s: '1.5' });
    const swql =
      'SELECT c.DateTime FROM Orion.CPULoad c WHERE a = $__interval_ms AND b = $__range_s AND c = $__range_ms';
    expect(bindVariables(swql, odd).swql).toBe(swql);

    const others =
      'SELECT c.DateTime FROM Orion.CPULoad c WHERE a = $__interval AND b = [[__interval_ms]] AND c = ${__range_s:raw}';
    expect(bindVariables(others, withBuiltins).swql).toBe(others);

    const inLiteral = "SELECT c.DateTime FROM Orion.CPULoad c WHERE c.Note = '$__interval_ms' -- $__range_s";
    expect(bindVariables(inLiteral, withBuiltins).swql).toBe(inLiteral);
  });

  it('never touches the backend time macros', () => {
    const swql =
      'SELECT c.DateTime FROM Orion.CPULoad c WHERE $__timeFilter(c.DateTime) AND c.DateTime > $__timeFrom() AND c.DateTime < $__timeTo()';
    const out = bindVariables(swql, withBuiltins);
    expect(out.swql).toBe(swql);
    expect(out.parameters).toEqual({});
  });
});

describe('templateResolver', () => {
  // A stand-in for Grafana's TemplateSrv: replace() hands a format function the unformatted
  // value, which is what the resolver relies on.
  const values: Record<string, string | string[]> = { node: '42', nodes: ['1', '2'], all: '*' };
  const srv = {
    getVariables: () => [{ name: 'node' }, { name: 'nodes' }, { name: 'all' }],
    replace: (target: string, _scoped: unknown, format?: unknown) => {
      const m = /^\$\{(\w+)(?::(\w+))?\}$/.exec(target ?? '');
      if (!m) {
        return target;
      }
      const v = values[m[1]] ?? (_scoped as Record<string, { value: string }>)[m[1]]?.value;
      if (v === undefined) {
        return target; // Grafana leaves an unknown reference as written
      }
      if (m[1] === 'all') {
        return '*'; // a custom All value is returned as text, without calling the formatter
      }
      if (typeof format === 'function') {
        return format(v);
      }
      return Array.isArray(v) ? v.join(',') : v;
    },
  } as unknown as TemplateSrv;

  it('reads values, arrays, scoped variables and custom All values', () => {
    const r = templateResolver(srv, { repeated: { text: 'r', value: '9' } });
    expect(r.has('node')).toBe(true);
    expect(r.has('repeated')).toBe(true);
    expect(r.has('missing')).toBe(false);
    expect(r.value('node')).toBe('42');
    expect(r.value('nodes')).toEqual(['1', '2']);
    expect(r.value('repeated')).toBe('9');
    expect(r.value('all')).toBe('*');
    expect(r.raw('nodes')).toBe('1,2');
  });

  it('reads built-ins from the scoped variables Grafana passes with the request', () => {
    const r = templateResolver(srv, { __interval_ms: { text: '60000', value: '60000' } });
    expect(r.builtin('__interval_ms')).toBe('60000');
    expect(r.builtin('__range_s')).toBe('${__range_s}');
  });
});
