/**
 * Dashboard variables become bound SWQL parameters, not text pasted into the statement.
 *
 * OrionGuides asks every integration to bind its values (docs/guides/building-integrations.md,
 * section 5) and documents multi-valued parameters as `IN @ids`, with no parentheses
 * (docs/swis/rest-api.md). This module rewrites each reference to a dashboard variable into
 * `@name` and returns the value to bind under that name, so a value containing an apostrophe
 * or a comment marker is data and never SWQL.
 *
 * What is rewritten, outside comments and string literals:
 *
 * - `$var`, `${var}`, `${var:format}`, `[[var]]` and `[[var:format]]` become `@var`.
 * - `IN (${var})` and `IN $var`, in any of those forms, become `IN @var` and bind an
 *   array, even when one value is selected.
 * - `${var:raw}` (or `[[var:raw]]`) is the one exception: it is text substitution, for a
 *   position SWQL cannot take a parameter in (an entity or column name). It is the caller's
 *   responsibility, exactly as text substitution always was.
 *
 * Inside a string literal, a literal that is exactly one reference (`'$var'`) becomes `@var`
 * bound as a string. Any other reference inside a literal is left as written, except
 * `:raw`, which is substituted. References inside `--` comments are left alone, so they bind
 * nothing.
 *
 * Names starting with `__` are Grafana built-ins and the backend's time macros
 * (`$__timeFilter` and friends); they are never bound. The exception is the three numeric
 * built-ins `$__interval_ms`, `$__range_s` and `$__range_ms`, which are substituted as text
 * when, and only when, their value is all digits. A name that is not a dashboard
 * variable is left as written too, so SWIS reports it rather than this code guessing.
 */

import type { ScopedVars } from '@grafana/data';
import type { TemplateSrv } from '@grafana/runtime';

/** Looks up dashboard variables. The data source wires this to Grafana's TemplateSrv. */
export interface VariableResolver {
  /** True when `name` is a dashboard variable or a scoped (repeated panel) variable. */
  has(name: string): boolean;
  /** The current value: a string, or an array for a multi-value or All selection. */
  value(name: string): string | string[];
  /** Grafana's own text substitution, used only for the explicit `:raw` escape hatch. */
  raw(name: string): string;
  /** The rendered value of a Grafana built-in such as `__interval_ms`, or '' if unknown. */
  builtin(name: string): string;
}

/** The only Grafana built-ins substituted, and only when their value is all digits. */
export const NUMERIC_BUILTINS = new Set(['__interval_ms', '__range_s', '__range_ms']);

export interface BoundQuery {
  swql: string;
  parameters: Record<string, unknown>;
}

// One reference in any of Grafana's three syntaxes. Groups: 1-2 ${name:format},
// 3-4 [[name:format]], 5 $name.
const REF = String.raw`\$\{(\w+)(?::(\w+))?\}|\[\[(\w+)(?::(\w+))?\]\]|\$(\w+)`;
// A reference, optionally the whole of an IN list. Groups: 1 "IN (" or "IN ", 2-6 the
// reference, 7 a closing parenthesis.
const CODE_RE = new RegExp(String.raw`(\bIN(?:\s*\(\s*|\s+))?(?:${REF})(\s*\))?`, 'gi');
const REF_RE = new RegExp(REF, 'g');
const WHOLE_REF_RE = new RegExp(String.raw`^(?:${REF})$`);

// Formats that quoted the value as a string literal under text substitution, so the
// value is bound as a string rather than inferred.
const STRING_FORMATS = new Set(['singlequote', 'doublequote', 'sqlstring']);
// A canonical decimal number: what an unquoted reference produced as a numeric literal.
const NUMBER_RE = /^-?(0|[1-9]\d*)(\.\d+)?$/;

interface Ref {
  name: string;
  format?: string;
}

function refFrom(m: RegExpExecArray | string[], offset: number): Ref {
  const name = m[offset] ?? m[offset + 2] ?? m[offset + 4];
  const format = m[offset + 1] ?? m[offset + 3];
  return { name, format };
}

/** A SWQL parameter name for a variable name. Grafana names are already word characters. */
export function paramName(variable: string): string {
  const cleaned = variable.replace(/\W/g, '_');
  return /^\d/.test(cleaned) ? `_${cleaned}` : cleaned;
}

function typed(v: string, asString: boolean): string | number {
  return !asString && NUMBER_RE.test(v) ? Number(v) : v;
}

export function bindVariables(
  swql: string,
  resolver: VariableResolver,
  explicit: Record<string, unknown> = {}
): BoundQuery {
  const parameters: Record<string, unknown> = { ...explicit };

  const bindable = (ref: Ref) => !!ref.name && !ref.name.startsWith('__') && resolver.has(ref.name);

  // Reuse a name for an identical value; otherwise take the next free suffix, so a
  // variable never overwrites a parameter set explicitly on the query or bound in
  // another shape (an array in one place, a scalar in another).
  const bind = (variable: string, value: unknown): string => {
    const base = paramName(variable);
    const encoded = JSON.stringify(value);
    for (let n = 1; ; n++) {
      const name = n === 1 ? base : `${base}_${n}`;
      if (!(name in parameters)) {
        parameters[name] = value;
        return `@${name}`;
      }
      if (JSON.stringify(parameters[name]) === encoded) {
        return `@${name}`;
      }
    }
  };

  const valueOf = (ref: Ref, opts: { list: boolean; asString: boolean }): unknown => {
    const raw = resolver.value(ref.name);
    const values = (Array.isArray(raw) ? raw : [raw]).map((v) => typed(String(v), opts.asString));
    if (opts.list) {
      return values;
    }
    return values.length === 1 ? values[0] : values;
  };

  const rewriteCode = (code: string): string =>
    code.replace(CODE_RE, (match: string, ...groups: string[]) => {
      const ref = refFrom(groups, 1);
      const open = groups[0] ?? '';
      const close = groups[6] ?? '';
      // $__interval_ms, $__range_s, $__range_ms (or ${...} without a format): Grafana's
      // numeric built-ins, substituted as text only when the value is all digits, so the
      // statement can only ever gain an integer literal. Anything else is left for the
      // backend to refuse. [[...]] and formats are not accepted for these.
      const plainForm = (groups[1] !== undefined && groups[2] === undefined) || groups[5] !== undefined;
      if (plainForm && NUMERIC_BUILTINS.has(ref.name)) {
        const value = resolver.builtin(ref.name);
        return /^\d+$/.test(value) ? open + value + close : match;
      }
      if (!bindable(ref)) {
        return match;
      }
      if (ref.format === 'raw') {
        return open + resolver.raw(ref.name) + close;
      }
      const asString = STRING_FORMATS.has(ref.format ?? '');
      const paren = open.includes('(');
      if (open && (!paren || close)) {
        // IN @ids, with no parentheses: the array supplies the whole list. A closing
        // parenthesis without an opening one here belongs to the surrounding statement.
        const list = bind(ref.name, valueOf(ref, { list: true, asString }));
        return `${open.slice(0, 2)} ${list}${paren ? '' : close}`;
      }
      return open + bind(ref.name, valueOf(ref, { list: false, asString })) + close;
    });

  const rewriteLiteral = (literal: string): string => {
    const inner = literal.slice(1, -1);
    const whole = WHOLE_REF_RE.exec(inner);
    if (whole) {
      const ref = refFrom(whole, 1);
      if (bindable(ref) && ref.format !== 'raw') {
        return bind(ref.name, valueOf(ref, { list: false, asString: true }));
      }
    }
    return literal.replace(REF_RE, (match: string, ...groups: string[]) => {
      const ref = refFrom(groups, 0);
      return bindable(ref) && ref.format === 'raw' ? resolver.raw(ref.name) : match;
    });
  };

  // Split into code, -- comments and '...' literals ('' is an escaped quote), and rewrite
  // only the code and the literals.
  let out = '';
  let code = '';
  let i = 0;
  while (i < swql.length) {
    if (swql.startsWith('--', i)) {
      const end = swql.indexOf('\n', i);
      const stop = end < 0 ? swql.length : end;
      out += rewriteCode(code) + swql.slice(i, stop);
      code = '';
      i = stop;
    } else if (swql[i] === "'") {
      let j = i + 1;
      while (j < swql.length) {
        if (swql[j] === "'" && swql[j + 1] === "'") {
          j += 2;
        } else if (swql[j] === "'") {
          break;
        } else {
          j++;
        }
      }
      if (j >= swql.length) {
        // Unterminated literal: leave the rest as written and let SWIS report it.
        out += rewriteCode(code) + swql.slice(i);
        code = '';
        i = swql.length;
      } else {
        out += rewriteCode(code) + rewriteLiteral(swql.slice(i, j + 1));
        code = '';
        i = j + 1;
      }
    } else {
      code += swql[i];
      i++;
    }
  }
  out += rewriteCode(code);
  return { swql: out, parameters };
}

/** Adapts Grafana's TemplateSrv to the resolver bindVariables needs. */
export function templateResolver(srv: TemplateSrv, scopedVars: ScopedVars = {}): VariableResolver {
  const names = new Set(srv.getVariables().map((v) => v.name));
  return {
    has: (name) => names.has(name) || Object.prototype.hasOwnProperty.call(scopedVars, name),
    value: (name) => {
      // A format function receives the variable's value before any formatting: a string,
      // or an array for a multi-value or All selection. Grafana skips the function for a
      // custom All value and returns that value as text, which is then bound as a string.
      let captured: unknown;
      const text = srv.replace('${' + name + '}', scopedVars, (value: unknown) => {
        captured = value;
        return '';
      });
      if (captured === undefined) {
        return text;
      }
      return Array.isArray(captured) ? captured.map(String) : String(captured);
    },
    raw: (name) => srv.replace('${' + name + ':raw}', scopedVars),
    // An unresolved built-in comes back as the reference text, which fails the digits test.
    builtin: (name) => srv.replace('${' + name + '}', scopedVars),
  };
}
