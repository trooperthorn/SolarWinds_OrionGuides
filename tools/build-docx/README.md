# build-docx

Generates the customer-facing Word guide for the VNQM / CUCM call-detail
widgets from their documentation page, so the `.docx` never drifts from the
published doc.

Source of truth: [`docs/webui/custom-query-call-queries.md`](../../docs/webui/custom-query-call-queries.md).

```bash
cd tools/build-docx
npm install
node build-docx.js                      # writes CUCM-CDR-Widgets-Customer-Guide.docx
node build-docx.js <input.md> <out.docx> # explicit paths
```

It parses the six `## N. <title>` widget sections and, within each, the
`Main query`, `Auto-hide query` and `Search query` fenced `sql` blocks. It
prints the widget count; if that is not `6`, or a query renders empty, the
headings in the source doc changed and the parser needs updating.

The generated `.docx` and `node_modules/` are not committed — the document is
a build output, rebuilt on demand.
