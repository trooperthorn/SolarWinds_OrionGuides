import { DataSourceJsonData } from '@grafana/data';
import { DataQuery } from '@grafana/schema';

export type SwisFormat = 'table' | 'timeseries';

/** The clock assumed for zoneless timestamps: bound time-range values and result columns. */
export type SwisTimeBasis = 'utc' | 'serverLocal';

/**
 * What a panel stores for one query. Before it is sent, each dashboard variable `swql`
 * references is rewritten to `@name` and its value added to `parameters`.
 */
export interface SwisQuery extends DataQuery {
  swql?: string;
  format?: SwisFormat;
  /** Bound parameters (name -> value) referenced as @name. Names starting with __ are reserved. */
  parameters?: Record<string, unknown>;
}

export const DEFAULT_QUERY: Partial<SwisQuery> = {
  swql: '',
  format: 'table',
};

/** Data source settings stored in Grafana's jsonData. Nothing here is secret. */
export interface SwisDataSourceOptions extends DataSourceJsonData {
  host?: string;
  port?: number;
  username?: string;
  tlsSkipVerify?: boolean;
  /** Verify the chain against the pasted certificate but not the name. */
  tlsIgnoreHostname?: boolean;
  maxRows?: number;
  timeoutSeconds?: number;
  /** Entity.Verb names the Invoke resource may call, for example "Orion.Nodes.PollNow". */
  invokeAllow?: string[];
  /** Default 'utc'. 'serverLocal' uses serverTimeZone, or serverUtcOffsetMinutes when no zone is set. */
  timeBasis?: SwisTimeBasis;
  /** IANA zone name, for example America/Chicago. Follows daylight saving. */
  serverTimeZone?: string;
  /** Fixed offset east of UTC in minutes, for example -300 for UTC-05:00. */
  serverUtcOffsetMinutes?: number;
}

/** Encrypted by Grafana, sent to the backend only, never returned to the browser. */
export interface SwisSecureJsonData {
  password?: string;
  caCert?: string;
}
