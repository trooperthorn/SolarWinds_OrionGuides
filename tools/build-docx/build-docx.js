const fs = require("fs");
const path = require("path");
const d = require("docx");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType, LevelFormat, BorderStyle, PageBreak } = d;

const SRC = process.argv[2] || path.join(__dirname, "..", "..", "docs", "webui", "custom-query-call-queries.md");
const OUT = process.argv[3] || "CUCM-CDR-Widgets-Customer-Guide.docx";
const md = fs.readFileSync(SRC, "utf8");
const widgets = [];
const secRe = /^## (\d)\. (.+)$/gm;
let m; const idx = [];
while ((m = secRe.exec(md))) idx.push({ n: m[1], title: m[2], start: m.index });
idx.forEach((s, i) => {
  const end = i + 1 < idx.length ? idx[i + 1].start : md.indexOf("\n---\n", s.start);
  const body = md.slice(s.start, end);
  const q = {};
  for (const k of ["Auto-hide query", "Main query", "Search query"]) {
    const label = body.indexOf(k);
    if (label === -1) { q[k] = ""; } else {
      const open = body.indexOf("```sql", label);
      const close = open === -1 ? -1 : body.indexOf("```", open + 6);
      q[k] = (open === -1 || close === -1) ? "" : body.slice(open + 7, close).trimEnd();
    }
  }
  const descM = body.match(/^## .*\n\n(?!###)([^\n]+(?:\n[^\n#]+)*)/);
  widgets.push({ ...s, desc: descM ? descM[1].replace(/\n/g, " ") : "", q });
});

const FONT = "Calibri";
const R = (t) => new TextRun({ text: t, font: FONT, size: 22 });
const B = (t) => new TextRun({ text: t, bold: true, font: FONT, size: 22 });
const C = (t) => new TextRun({ text: t, font: "Consolas", size: 19 });
const P = (t, o = {}) => new Paragraph({ spacing: { after: 120 }, ...o, children: Array.isArray(t) ? t : [R(t)] });
const H = (lvl, t) => new Paragraph({ heading: lvl, spacing: { before: lvl === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 }, children: [new TextRun({ text: t, font: FONT })] });
const H1 = (t) => H(HeadingLevel.HEADING_1, t), H2 = (t) => H(HeadingLevel.HEADING_2, t), H3 = (t) => H(HeadingLevel.HEADING_3, t);
const bullet = (runs) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 80 }, children: Array.isArray(runs) ? runs : [R(runs)] });
const step = (runs) => new Paragraph({ numbering: { reference: "steps", level: 0 }, spacing: { after: 80 }, children: runs });
const code = (text) => {
  const lines = text.split("\n");
  return lines.map((l, i) => new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" }, spacing: { after: 0, before: 0 }, indent: { left: 200 },
    border: i === 0 ? { top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" } } : (i === lines.length - 1 ? { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" } } : undefined),
    children: [new TextRun({ text: l.replace(/\t/g, "    ") || " ", font: "Consolas", size: 18 })],
  }));
};
const W = 9360;
const cell = (t, w, hdr) => new TableCell({
  width: { size: w, type: WidthType.DXA }, shading: hdr ? { type: ShadingType.CLEAR, fill: "D9E2F3" } : undefined,
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [new Paragraph({ children: [new TextRun({ text: t, bold: !!hdr, font: FONT, size: 20 })] })],
});
const table = (rows, widths) => new Table({
  width: { size: W, type: WidthType.DXA }, columnWidths: widths,
  rows: rows.map((r, i) => new TableRow({ tableHeader: i === 0, children: r.map((c, j) => cell(c, widths[j], i === 0)) })),
});

const ch = [];
ch.push(new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Cisco Unified Communications Manager", font: FONT, size: 44, bold: true })] }));
ch.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Call Detail Report Widgets for the SolarWinds Platform", font: FONT, size: 32 })] }));
ch.push(P("Six Custom Query widgets for VoIP & Network Quality Manager (VNQM), each showing the top 25 results with links to the phone, the call and the Call Manager."));
ch.push(P([B("Prepared: "), R("September 17, 2026")]));
ch.push(P([B("Applies to: "), R("SolarWinds Platform 2024.x and later with VNQM monitoring one or more Cisco Unified CM clusters. Queries were checked against the 2026.2 schema.")]));

ch.push(H1("1. Overview"));
ch.push(P("These widgets are built with the SolarWinds Custom Query widget and read the call detail records (CDRs) that VNQM collects from Cisco Unified CM. Each one is limited to 25 rows, can hide itself when there is nothing to show, and has a search box."));
ch.push(table([["#", "Widget", "What it shows"],
  ["1", "Calls placed to 911", "The 25 most recent emergency calls, with caller, device, region and whether the call connected."],
  ["2", "Top 25 longest calls", "Calls ranked by duration, with the MOS score of both call legs."],
  ["3", "Top 25 originating phone numbers", "Calling numbers ranked by call count, with total talk time and failed calls."],
  ["4", "Calls from non-7-digit originating numbers", "The 25 most recent calls whose calling number is not seven digits."],
  ["5", "Top 25 non-7-digit calling numbers", "The same calls as widget 4, rolled up by calling number."],
  ["6", "Top 25 phones placing 911 calls", "Phones ranked by the number of emergency calls placed."]], [500, 3200, 5660]));
ch.push(P(""));
ch.push(H2("Links in the tables"));
ch.push(P("Several columns are clickable. The links go to the standard VNQM detail pages, so they behave exactly like links elsewhere in the SolarWinds web console."));
ch.push(table([["Column", "Opens"],
  ["Call Time", "The VoIP Call Details page for that call"],
  ["Calling Number, Originating Device", "The VoIP Phone page for the originating phone"],
  ["Called Number", "The VoIP Phone page for the destination phone"],
  ["Call Manager", "The VoIP CallManager page for the cluster node that recorded the call"]], [3400, 5960]));
ch.push(P(""));
ch.push(P("A call that originates on a gateway or trunk rather than a registered phone has no phone to link to, so on those rows the number is shown as plain text."));

ch.push(H1("2. Before you begin"));
ch.push(P([B("Permissions. "), R("You need a SolarWinds account that is allowed to customize views. Users viewing the widgets see only the data their account limitations allow.")]));
ch.push(P([B("Data source. "), R("VNQM must be collecting CDRs from the Cisco Unified CM cluster. If the VoIP Call Details pages in the console are empty, these widgets will be empty too.")]));
ch.push(P([B("Emergency dial strings. "), R("The queries treat 911 and 9911 as emergency calls. If your dial plan uses other patterns (for example 8911 or +1911), add them to every IN ('911', '9911') list in widgets 1 and 6 before pasting. Each of those widgets has three queries and all three must be changed.")]));
ch.push(P([B("Time window. "), R("All queries look back 30 days. To change this, edit AddDay(-30, GetDate()) in every query of the widget, keeping the three queries in step.")]));
ch.push(P([B("Copy the queries exactly. "), R("Column names such as _LinkFor_Call Time are case-sensitive and must match the visible column name character for character. If they do not, the query still runs but the link column appears as a plain column of web addresses.")]));
ch.push(P([B("Do not add comments to the end of a query. "), R("SolarWinds appends clauses to your query when the widget runs. A trailing comment swallows those clauses and the widget stops working.")]));

ch.push(H1("3. Adding a widget"));
ch.push(P("Repeat these steps once for each of the six widgets. Each widget has three queries: the Main query, the Auto-hide query and the Search query. They are listed in section 4."));
[
  [B("Open the view. "), R("Go to the summary or details view where the widget should appear.")],
  [B("Enter customization. "), R("Click Customize Page in the top right of the view.")],
  [B("Add the widget. "), R("Click Add Widgets, search for Custom Query, drag it into a column, then click Done Adding Widgets and Done Editing.")],
  [B("Edit the widget. "), R("Click Edit in the widget's title bar.")],
  [B("Title. "), R("Enter the widget name from section 4 as the Title. The Subtitle is optional.")],
  [B("Custom SWQL Query. "), R("Paste the widget's Main query into this box.")],
  [B("Auto-hide. "), R("Tick Auto-hide the resource if there is no data to display. In the Auto-hide SWQL Query box that appears, paste the widget's Auto-hide query. Do not use Add Query to copy the main query in; the supplied query is much cheaper to run.")],
  [B("Search. "), R("Tick Enable search. In the Search SWQL Query box, paste the widget's Search query.")],
  [B("Rows per page. "), R("Set Number of Rows Per Page to 25.")],
  [B("Save. "), R("Click Submit. The widget renders immediately.")],
].forEach((r) => ch.push(step(r)));
ch.push(H2("Checking the result"));
ch.push(bullet("Column headings should match the names in section 4 and there should be no column showing web addresses. If there is, the _LinkFor_ name in that query does not match the visible column name."));
ch.push(bullet("Widgets 1, 4, 5 and 6 may be hidden. That is expected when there have been no emergency calls or no non-7-digit callers in the last 30 days. To confirm the widget is configured, temporarily widen the time window in the Auto-hide query."));
ch.push(bullet("Type a phone extension or a region name into the search box. The table should narrow to matching calls and the links should still work."));
ch.push(H2("Which widgets to auto-hide"));
ch.push(P("Auto-hide is supplied for all six, but it suits some better than others. On widgets 1, 4, 5 and 6 an empty table is the normal, healthy state, so the widget disappearing is the right signal. On widgets 2 and 3 an empty table would mean CDR collection has stopped, which is worth seeing, so you may prefer to leave auto-hide unticked on those two."));
ch.push(H2("Using the search box"));
ch.push(bullet("The search matches the calling number, the called number, the originating phone or device name, the region and the Call Manager name."));
ch.push(bullet("The percent sign is a wildcard: typing 55% finds every number that starts with 55."));
ch.push(bullet("On the ranked widgets (3, 5 and 6) the counts are recalculated for the matching calls only."));
ch.push(bullet("A single quote in the search box produces a query error. Clear the box to return to the normal view."));

ch.push(new Paragraph({ children: [new PageBreak()] }));
ch.push(H1("4. Widget definitions"));
ch.push(P("For each widget, paste the three queries into the boxes named in section 3. The Main query populates the table, the Auto-hide query decides whether the widget is shown, and the Search query runs when text is entered in the search box."));
for (const w of widgets) {
  ch.push(H2(`Widget ${w.n}: ${w.title}`));
  if (w.desc) ch.push(P(w.desc));
  ch.push(H3("Main query (Custom SWQL Query box)")); ch.push(...code(w.q["Main query"])); ch.push(P(""));
  ch.push(H3("Auto-hide query (Auto-hide SWQL Query box)")); ch.push(...code(w.q["Auto-hide query"])); ch.push(P(""));
  ch.push(H3("Search query (Search SWQL Query box)")); ch.push(...code(w.q["Search query"])); ch.push(P(""));
}

ch.push(H1("5. Troubleshooting"));
ch.push(table([["Symptom", "Cause and fix"],
  ["A column shows web addresses instead of links", "The _LinkFor_ name does not exactly match the visible column name. Compare both, including spaces and capital letters."],
  ["Links work normally but disappear while searching", "The Search query's column list differs from the Main query's. Re-paste the Search query from section 4."],
  ["The widget is hidden even though calls exist", "The Auto-hide query's WHERE clause differs from the Main query's, usually after editing the dial strings or time window in one but not the other."],
  ["The widget shows an error after typing in the search box", "The search text contained a single quote. Clear the search box."],
  ["The widget is empty on every view", "VNQM is not receiving CDRs. Check the Call Manager's CDR settings in VNQM and the VoIP Call Details page."],
  ["Older calls have vanished", "VNQM moves calls out of the live call table after its retention period. These widgets show live calls only."],
], [3400, 5960]));
ch.push(P(""));
ch.push(H1("6. Reference"));
ch.push(bullet([R("Data source: the "), C("Orion.IpSla.VoipCallDetails"), R(" entity, one row per call, including its links to the originating phone, destination phone and Call Manager.")]));
ch.push(bullet([R("Custom Query widget documentation: "), R("https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-custom-query-widget.htm")]));
ch.push(bullet([R("Using SWQL: "), R("https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-using-swql--semantic-web-query-language--sw3110.htm")]));
ch.push(bullet([R("SWQL functions: "), R("https://github.com/solarwinds/OrionSDK/wiki/SWQL-Functions")]));
ch.push(P(""));
ch.push(P([B("Disclaimer. "), new TextRun({ text: "These queries are custom content and are not covered by SolarWinds support. They are provided as is, without warranty of any kind. Test them on a non-production view first and review the results before relying on them.", font: FONT, size: 20, italics: true })]));

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: "1F3864", font: FONT } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, color: "2F5496", font: FONT } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 22, bold: true, color: "404040", font: FONT } },
    ],
  },
  numbering: {
    config: [
      { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
      { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    ],
  },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: ch }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync("CUCM-CDR-Widgets-Customer-Guide.docx", b); console.log("ok", widgets.length, "widgets"); });
