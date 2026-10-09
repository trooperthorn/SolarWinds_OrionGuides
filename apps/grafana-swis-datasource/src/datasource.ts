import { CoreApp, DataSourceInstanceSettings, ScopedVars } from '@grafana/data';
import { DataSourceWithBackend, getTemplateSrv } from '@grafana/runtime';

import { bindVariables, templateResolver } from './bindVariables';
import { DEFAULT_QUERY, SwisDataSourceOptions, SwisQuery } from './types';
import { SwisVariableSupport } from './variables';

export class DataSource extends DataSourceWithBackend<SwisQuery, SwisDataSourceOptions> {
  constructor(instanceSettings: DataSourceInstanceSettings<SwisDataSourceOptions>) {
    super(instanceSettings);
    this.variables = new SwisVariableSupport();
  }

  getDefaultQuery(_: CoreApp): Partial<SwisQuery> {
    return DEFAULT_QUERY;
  }

  /**
   * Dashboard variables become bound parameters here, in the browser: each reference is
   * rewritten to `@name` and its current value travels in `parameters`, so a value is never
   * pasted into the statement as text (see bindVariables.ts). `${var:raw}` is the explicit
   * exception. The Grafana time macros are left alone: the backend turns them into bound
   * parameters too.
   */
  applyTemplateVariables(query: SwisQuery, scopedVars: ScopedVars): SwisQuery {
    const bound = bindVariables(
      query.swql ?? '',
      templateResolver(getTemplateSrv(), scopedVars),
      query.parameters ?? {}
    );
    return {
      ...query,
      swql: bound.swql,
      parameters: Object.keys(bound.parameters).length > 0 ? bound.parameters : undefined,
    };
  }

  filterQuery(query: SwisQuery): boolean {
    return !!query.swql?.trim();
  }

  /**
   * Call a SWIS verb through the backend. Arguments are positional: the order is the
   * verb's declared parameter order and nothing else. Look it up first with
   * `python3 tools/schema_query.py verb <Entity> <Verb>` in OrionGuides. The backend
   * refuses any verb that is not on the data source's allowlist, and any caller who is
   * not an Editor or Admin.
   */
  async invoke<T = unknown>(entity: string, verb: string, args: unknown[] = []): Promise<T> {
    return this.postResource<T>(`invoke/${encodeURIComponent(entity)}/${encodeURIComponent(verb)}`, args);
  }

  /** The Entity.Verb names this data source is allowed to invoke. */
  async allowedVerbs(): Promise<string[]> {
    const res = await this.getResource<{ invokeAllow: string[] }>('verbs');
    return res.invokeAllow ?? [];
  }
}
