#!/usr/bin/env python3
"""Tests for the parts of the toolchain where being wrong is expensive.

Run with the standard library only:

    python3 tools/test_tools.py
    python3 -m unittest discover -s tools -p 'test_*.py'

The tools are mostly straightforward parsing, and straightforward parsing does not need
tests. What is tested here is the judgement encoded in them, because each of these rules
was arrived at by getting it wrong first:

  - inheritance resolution, which is what lets Orion.Nodes.Uri validate
  - navigation in both relationship directions, which is what lets
    Orion.NPM.Interfaces.Node resolve as one hop
  - the difference between a breaking verb change and a cosmetic one, which turns on
    Invoke arguments being positional
  - rename detection, which has to pair Orion.NPM.UCSBlades with Orion.UCS.Blades
    without pairing Firewall.Statistics with GkePodStatistics
  - determinism, since a non-reproducible build makes "regenerate and commit" useless
"""

from __future__ import annotations

import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_reference_data
import check_dashboards
import diff_schema
import validate_swql
from schema_query import Schema

VERSION = "2026.2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "schema", VERSION)
HAVE_DATA = os.path.isdir(DATA)
requires_data = unittest.skipUnless(HAVE_DATA, f"no extracted schema at {DATA}; run make data")


@requires_data
class TestSchemaResolution(unittest.TestCase):
    """Members must resolve through the inheritance chain and both relationship lists."""

    @classmethod
    def setUpClass(cls):
        cls.schema = validate_swql.SchemaIndex(VERSION)

    def test_declared_property_resolves(self):
        props, _ = self.schema.members("Orion.Nodes")
        self.assertIn("caption", props)
        self.assertIn("nodeid", props)

    def test_inherited_property_resolves(self):
        # Uri is declared on System.Entity, UnManaged on System.ManagedEntity. Both are
        # queryable on Orion.Nodes, and a validator that only reads the entity's own page
        # would reject them.
        props, _ = self.schema.members("Orion.Nodes")
        for inherited in ("uri", "instancetype", "unmanaged", "unmanagefrom"):
            self.assertIn(inherited, props, f"{inherited} should resolve through inheritance")

    def test_property_is_not_declared_on_the_entity_itself(self):
        # Guards the reason the previous test exists: if extraction ever starts inlining
        # inherited members, the inheritance walk becomes untested rather than unnecessary.
        rec = self.schema.entities["Orion.Nodes"]
        self.assertNotIn("Uri", {p["name"] for p in rec["properties"]})

    def test_navigation_from_source_relationship(self):
        _, navs = self.schema.members("Orion.Nodes")
        self.assertEqual(navs.get("interfaces"), "Orion.NPM.Interfaces")

    def test_navigation_from_target_relationship(self):
        # Orion.NPM.Interfaces is the target end of the relationship, and Node is still a
        # navigation property usable from it. Treating only source relationships as
        # navigable is the bug this catches.
        _, navs = self.schema.members("Orion.NPM.Interfaces")
        self.assertEqual(navs.get("node"), "Orion.Nodes")


@requires_data
class TestValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = validate_swql.SchemaIndex(VERSION)

    def errors(self, query):
        return [f for f in validate_swql.validate(query, self.schema) if f.level == "ERROR"]

    def warnings(self, query):
        return [f for f in validate_swql.validate(query, self.schema) if f.level == "WARN"]

    def test_valid_query_passes(self):
        self.assertEqual(self.errors("SELECT TOP 5 n.Caption FROM Orion.Nodes n"), [])

    def test_inherited_property_passes(self):
        self.assertEqual(self.errors("SELECT n.Uri, n.UnManaged FROM Orion.Nodes n"), [])

    def test_single_hop_navigation_passes(self):
        self.assertEqual(
            self.errors("SELECT i.Node.Caption FROM Orion.NPM.Interfaces i"), []
        )

    def test_deep_navigation_passes(self):
        self.assertEqual(
            self.errors("SELECT c.Application.Node.Caption FROM Orion.APM.Component c"), []
        )

    def test_unknown_entity_is_an_error(self):
        errs = self.errors("SELECT x.Caption FROM Orion.NodesX x")
        self.assertTrue(errs)
        self.assertIn("unknown entity", errs[0].message)

    def test_unknown_property_is_an_error(self):
        errs = self.errors("SELECT n.Captionn FROM Orion.Nodes n")
        self.assertTrue(errs)
        self.assertIn("Captionn", errs[0].message)

    def test_navigating_through_a_scalar_is_an_error(self):
        errs = self.errors("SELECT n.Caption.Length FROM Orion.Nodes n")
        self.assertTrue(errs)
        self.assertIn("cannot be navigated", errs[0].message)

    def test_real_function_is_not_warned_about(self):
        self.assertEqual(self.warnings("SELECT ToUpper(n.Caption) FROM Orion.Nodes n"), [])

    def test_unknown_function_warns(self):
        self.assertTrue(self.warnings("SELECT Frobnicate(n.Caption) FROM Orion.Nodes n"))

    def test_string_literals_are_not_parsed_as_identifiers(self):
        # 'Orion.Nope.Nope' inside quotes is data, not an entity reference.
        self.assertEqual(
            self.errors("SELECT n.Caption FROM Orion.Nodes n WHERE n.Caption = 'Orion.Nope.Nope'"),
            [],
        )

    def test_comments_are_ignored(self):
        query = "-- n.Bogus is not real\nSELECT n.Caption FROM Orion.Nodes n"
        self.assertEqual(self.errors(query), [])

    def test_unqualified_column_is_checked_against_a_single_source(self):
        # This exact query shipped in two module pages. Metadata.Verb names the verb in
        # Name and reaches its owner through the Entity navigation; it has neither of the
        # flat columns written here, and nothing caught it.
        errs = self.errors(
            "SELECT VerbName FROM Metadata.Verb WHERE EntityName = 'IPAM.SubnetManagement'")
        self.assertEqual(len(errs), 2)
        self.assertTrue(any("VerbName" in e.message for e in errs))
        self.assertTrue(any("EntityName" in e.message for e in errs))

    def test_the_corrected_form_passes(self):
        self.assertEqual(
            self.errors("SELECT Name FROM Metadata.Verb WHERE Entity.FullName = 'X'"), [])

    def test_verbargument_really_does_have_the_flat_columns(self):
        # The asymmetry that makes the mistake so easy: the sibling entity has them.
        self.assertEqual(
            self.errors("SELECT Position, Name FROM Metadata.VerbArgument "
                        "WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'"), [])

    def test_unqualified_columns_are_left_alone_when_sources_are_ambiguous(self):
        # With more than one source a bare name genuinely could belong to either, so
        # reporting it would be guessing.
        query = ("SELECT Caption, Frobnicate FROM Orion.Nodes n "
                 "JOIN Orion.NPM.Interfaces i ON n.NodeID = i.NodeID")
        self.assertEqual(self.errors(query), [])

    def test_bracket_quoted_identifiers_do_not_strand_their_qualifier(self):
        query = ("SELECT t.LimitationTypeID, t.[Table] AS SourceTable "
                 "FROM Orion.LimitationTypes t")
        self.assertEqual(self.errors(query), [])

    def test_bound_parameters_and_literals_are_not_columns(self):
        query = ("SELECT TOP 5 Caption FROM Orion.Nodes "
                 "WHERE NodeID IN @ids AND Status = 2")
        self.assertEqual(self.errors(query), [])


class TestTableHints(unittest.TestCase):
    """A table hint written against the entity name must not be read as an alias.

    Orion.Nodes(nolock=true) n appears throughout SolarWinds' community material, and the
    console widget examples use it on every source. Without the hint in the source pattern
    the parser stopped at the entity name, took "nolock" for the alias, and then reported
    every column qualified by the real alias as an unknown member -- a wall of errors on a
    query that is correct.
    """

    @classmethod
    def setUpClass(cls):
        import validate_swql

        cls.mod = validate_swql
        cls.schema = validate_swql.SchemaIndex(VERSION)

    def test_a_hinted_source_resolves_its_alias(self):
        q = "SELECT n.Caption, n.NodeID FROM Orion.Nodes(nolock=true) n"
        self.assertEqual([f for f in self.mod.validate(q, self.schema) if f.level == "ERROR"], [])

    def test_every_source_in_a_join_may_carry_a_hint(self):
        q = ("SELECT c.ComponentName, n.Caption "
             "FROM Orion.APM.Component(nolock=true) c "
             "JOIN Orion.Nodes(nolock=true) n ON n.NodeID = c.ApplicationID")
        self.assertEqual([f for f in self.mod.validate(q, self.schema) if f.level == "ERROR"], [])

    def test_the_hint_does_not_become_the_alias(self):
        q = "SELECT n.Caption FROM Orion.Nodes(nolock=true) n"
        m = self.mod.SOURCE_RE.search(q)
        self.assertEqual(m.group("entity"), "Orion.Nodes")
        self.assertEqual(m.group("alias"), "n")
        self.assertEqual(m.group("hint"), "nolock=true")

    def test_an_unhinted_source_is_unaffected(self):
        m = self.mod.SOURCE_RE.search("SELECT n.Caption FROM Orion.Nodes n")
        self.assertEqual(m.group("entity"), "Orion.Nodes")
        self.assertEqual(m.group("alias"), "n")
        self.assertIsNone(m.group("hint"))

    def test_a_bad_column_is_still_caught_through_a_hint(self):
        # The hint must widen the parse, not weaken the check.
        q = "SELECT n.Nonesuch FROM Orion.Nodes(nolock=true) n"
        errors = [f for f in self.mod.validate(q, self.schema) if f.level == "ERROR"]
        self.assertTrue(errors)


class TestEmbeddedExtraction(unittest.TestCase):
    """SWQL inside client scripts has to be found without swallowing surrounding prose."""

    def extract(self, text, suffix):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        try:
            return [q for _, q in validate_swql.queries_from_source(path)]
        finally:
            os.unlink(path)

    def test_powershell_herestring(self):
        found = self.extract("$q = @'\nSELECT Caption FROM Orion.Nodes\n'@\n", ".ps1")
        self.assertEqual(found, ["SELECT Caption FROM Orion.Nodes"])

    def test_docstring_is_not_treated_as_one_query(self):
        # A module docstring that quotes an example must not be swallowed whole; only the
        # quoted query inside it counts. Getting this wrong parsed prose as SQL.
        text = '"""Run it like this:\n\n    query "SELECT Caption FROM Orion.Nodes"\n"""\n'
        found = self.extract(text, ".py")
        self.assertEqual(found, ["SELECT Caption FROM Orion.Nodes"])

    def test_inline_backtick_query_is_extracted(self):
        # A one-liner written inline rather than in a fenced block is just as copyable,
        # and was not being checked at all.
        text = "See `SELECT Caption FROM Orion.Nodes` for the shape.\n"
        self.assertEqual(
            [q for _, q in self.extract_md(text)], ["SELECT Caption FROM Orion.Nodes"])

    def test_inline_query_inside_a_fenced_block_is_not_counted_twice(self):
        text = "```sql\nSELECT Caption FROM Orion.Nodes\n```\n"
        found = self.extract_md(text)
        self.assertEqual(len(found), 1)
        self.assertIn("sql-block", found[0][0])

    def test_a_deliberately_invalid_example_is_skipped(self):
        # Shown to demonstrate the error response, not as a working query.
        text = ("confirm by sending a deliberately invalid query such as "
                "`SELECT Nonsense FROM Orion.Nodes` and printing the body.\n")
        self.assertEqual(self.extract_md(text), [])

    def extract_md(self, text):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            path = fh.name
        try:
            return validate_swql.queries_from_markdown(path)
        finally:
            os.unlink(path)

    def test_templated_query_is_skipped(self):
        # The query the script sends is not the text on the page, so checking it would be
        # checking a string that never runs.
        found = self.extract('q = f"SELECT {col} FROM Orion.Nodes"\n', ".py")
        self.assertEqual(found, [])


class TestNoiseStripping(unittest.TestCase):
    """Comments and string literals have to be recognised in one pass, not two.

    Both cases here came from real dashboard queries and both produced a bogus warning that
    would have been believed, because a warning on a query nobody can run is indistinguishable
    from a real one.
    """

    def test_a_double_dash_inside_a_string_is_not_a_comment(self):
        # A CSS custom property assigned as a colour: the `--` is inside the quotes.
        q = "SELECT CASE WHEN a = 1 THEN 'var(--nui-color-semantic-ok)' END AS C FROM Orion.Nodes"
        clean = validate_swql.strip_noise(q)
        self.assertNotIn("var(", clean)
        self.assertIn("FROM Orion.Nodes", clean)

    def test_a_quote_inside_a_comment_does_not_open_a_string(self):
        q = "SELECT Caption FROM Orion.Nodes -- don't let this swallow the line\nWHERE NodeID = 1"
        clean = validate_swql.strip_noise(q)
        self.assertIn("WHERE NodeID = 1", clean)

    def test_an_escaped_quote_inside_a_string_is_handled(self):
        q = "SELECT Caption FROM Orion.Nodes WHERE Caption = 'it''s here' AND NodeID = 1"
        clean = validate_swql.strip_noise(q)
        self.assertIn("AND NodeID = 1", clean)

    def test_offsets_are_preserved_so_snippets_stay_aligned(self):
        q = "SELECT Caption FROM Orion.Nodes -- trailing comment"
        self.assertEqual(len(validate_swql.strip_noise(q)), len(q))

    def test_a_bracketed_alias_containing_parens_is_not_a_function_call(self):
        # `AS [LastLatency(ms)]` is a real alias in a real dashboard.
        schema = validate_swql.SchemaIndex(VERSION)
        q = "SELECT ROUND(n.ResponseTime, 1) AS [LastLatency(ms)] FROM Orion.Nodes n"
        warned = [f for f in validate_swql.validate(q, schema) if "LastLatency" in str(f)]
        self.assertEqual(warned, [])

    def test_a_genuinely_unknown_function_is_still_warned_about(self):
        # The masking above must not silence the check it runs inside.
        schema = validate_swql.SchemaIndex(VERSION)
        q = "SELECT Nonsensify(n.Caption) AS C FROM Orion.Nodes n"
        warned = [f for f in validate_swql.validate(q, schema) if "Nonsensify" in str(f)]
        self.assertEqual(len(warned), 1, [str(f) for f in warned])


class TestDashboardExtraction(unittest.TestCase):
    """A Modern Dashboard file stores each query twice, and both copies have to be found.

    The duplication is the format's own (docs/webui/modern-dashboards.md). An edit that
    updates one copy and misses the other leaves a stale query the widget can still run, so
    extracting only the first copy would validate the file and miss exactly that.
    """

    ENVELOPE = {
        "version": 1,
        "dashboards": [{"unique_key": "d", "name": "D", "widgets": [{"unique_key": "w"}]}],
        "widgets": [
            {
                "type": "table",
                "unique_key": "w",
                "name": "W",
                "configuration": {
                    "table": {
                        "providers": {
                            "dataSource": {
                                "providerId": "TableSwqlDatasourceService",
                                "properties": {
                                    "swql": "SELECT n.Caption AS [Node] FROM Orion.Nodes n",
                                    "dataFields": [{"id": "Node", "label": "Node", "dataType": "System.String"}],
                                },
                            },
                            "adapter": {
                                "properties": {
                                    "dataSource": {
                                        "properties": {
                                            "swql": "SELECT n.Caption AS [Node] FROM Orion.Nodes n",
                                            "dataFields": [{"id": "Node", "label": "Node", "dataType": "System.String"}],
                                        }
                                    }
                                }
                            },
                        }
                    }
                },
            }
        ],
        "remove": None,
    }

    def write(self, doc):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(doc, fh)
            return fh.name

    def test_both_copies_of_a_query_are_extracted(self):
        path = self.write(self.ENVELOPE)
        try:
            found = validate_swql.queries_from_dashboard(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(found), 2)
        self.assertEqual({q for _, q in found}, {"SELECT n.Caption AS [Node] FROM Orion.Nodes n"})

    def test_labels_name_the_path_to_each_copy(self):
        # A file has dozens of queries and they are frequently identical, so a bare filename
        # would not say which one failed.
        path = self.write(self.ENVELOPE)
        try:
            labels = [label for label, _ in validate_swql.queries_from_dashboard(path)]
        finally:
            os.unlink(path)
        self.assertTrue(any("adapter" in label for label in labels), labels)
        self.assertEqual(len(set(labels)), 2)

    def test_a_json_file_that_is_not_a_dashboard_yields_nothing(self):
        # The validator walks scripts/ by extension, so any other .json must be ignored
        # rather than parsed as a dashboard.
        path = self.write({"swql": "SELECT Caption FROM Orion.Nodes"})
        try:
            self.assertEqual(validate_swql.queries_from_dashboard(path), [])
        finally:
            os.unlink(path)

    def test_divergent_copies_are_reported(self):
        doc = json.loads(json.dumps(self.ENVELOPE))
        providers = doc["widgets"][0]["configuration"]["table"]["providers"]
        providers["adapter"]["properties"]["dataSource"]["properties"]["swql"] = "SELECT 1 AS X FROM Orion.Nodes"
        path = self.write(doc)
        try:
            problems = check_dashboards.check(path)
        finally:
            os.unlink(path)
        self.assertTrue(any("copies of the SWQL differ" in p for p in problems), problems)

    def test_a_datafield_that_is_not_an_alias_is_reported(self):
        # The console renders a blank column rather than raising, which is why this is
        # checked here instead of being noticed on the page.
        doc = json.loads(json.dumps(self.ENVELOPE))
        for props in (
            doc["widgets"][0]["configuration"]["table"]["providers"]["dataSource"]["properties"],
            doc["widgets"][0]["configuration"]["table"]["providers"]["adapter"]["properties"]["dataSource"]["properties"],
        ):
            props["dataFields"][0]["id"] = "Nodee"
        path = self.write(doc)
        try:
            problems = check_dashboards.check(path)
        finally:
            os.unlink(path)
        self.assertTrue(any("not an alias" in p for p in problems), problems)

    def test_a_duplicated_widget_key_is_reported(self):
        # The defect both real authors shipped: copy a widget, keep its key.
        doc = json.loads(json.dumps(self.ENVELOPE))
        doc["widgets"].append(json.loads(json.dumps(doc["widgets"][0])))
        path = self.write(doc)
        try:
            problems = check_dashboards.check(path)
        finally:
            os.unlink(path)
        self.assertTrue(any("defines 2 widgets" in p for p in problems), problems)

    def test_a_clean_file_is_reported_clean(self):
        path = self.write(self.ENVELOPE)
        try:
            self.assertEqual(check_dashboards.check(path), [])
        finally:
            os.unlink(path)

    def test_bracketed_and_bare_aliases_are_both_recognised(self):
        found = check_dashboards.aliases("SELECT a AS [Two Words], b AS One FROM Orion.Nodes")
        self.assertEqual(found, {"Two Words", "One"})

    def test_an_unaliased_column_is_named_by_its_property(self):
        # Whole real files are written this way; reading only `AS` reported 40 false positives.
        found = check_dashboards.aliases(
            "SELECT ONodes.Status, ONodes.DetailsUrl, NNodes.NodeCaption FROM Orion.Nodes AS ONodes")
        self.assertEqual(found, {"Status", "DetailsUrl", "NodeCaption"})

    def test_an_unaliased_expression_is_not_guessed_at(self):
        # The server names it; the text does not say what, so claiming a name would be wrong.
        found = check_dashboards.aliases("SELECT CONCAT(a, b), c AS Named FROM Orion.Nodes")
        self.assertEqual(found, {"Named"})

    def test_a_subquerys_from_does_not_end_the_select_list(self):
        found = check_dashboards.aliases(
            "SELECT COUNT(*) AS [Total] FROM (SELECT x AS Inner1 FROM Orion.Nodes GROUP BY x)")
        self.assertEqual(found, {"Total"})

    def test_a_comma_inside_a_function_call_does_not_split_the_list(self):
        found = check_dashboards.aliases(
            "SELECT CONCAT(a, ', ', b) AS [Joined], c FROM Orion.Nodes")
        self.assertEqual(found, {"Joined", "c"})

    def test_an_absent_component_id_is_not_a_defect(self):
        # Fourteen tiles across two working exports omit it entirely.
        doc = json.loads(json.dumps(self.ENVELOPE))
        doc["widgets"][0] = {
            "type": "kpi", "unique_key": "w", "name": "W",
            "configuration": {
                "tiles": {"properties": {"nodes": ["kpi_1"]}},
                "kpi_1": {
                    "id": "kpi_1",
                    "providers": {
                        "dataSource": {"properties": {
                            "swql": "SELECT COUNT(n.NodeID) AS TheCount FROM Orion.Nodes n",
                            "dataFields": [{"id": "TheCount", "label": "TheCount", "dataType": "System.Int32"}]}},
                        "adapter": {"properties": {"dataSource": {"properties": {
                            "swql": "SELECT COUNT(n.NodeID) AS TheCount FROM Orion.Nodes n",
                            "dataFields": [{"id": "TheCount", "label": "TheCount", "dataType": "System.Int32"}]}}}},
                    },
                    "properties": {"widgetData": {"label": "x", "backgroundColor": "y", "units": ""}},
                },
            },
        }
        path = self.write(doc)
        try:
            self.assertEqual(check_dashboards.check(path), [])
        finally:
            os.unlink(path)

    def test_a_disagreeing_component_id_is_still_a_defect(self):
        doc = json.loads(json.dumps(self.ENVELOPE))
        doc["widgets"][0] = {
            "type": "kpi", "unique_key": "w", "name": "W",
            "configuration": {
                "tiles": {"properties": {"nodes": ["kpi_1"]}},
                "kpi_1": {
                    "id": "kpi_1",
                    "providers": {"adapter": {"properties": {"componentId": "kpi_2"}}},
                    "properties": {},
                },
            },
        }
        path = self.write(doc)
        try:
            problems = check_dashboards.check(path)
        finally:
            os.unlink(path)
        self.assertTrue(any("componentId says kpi_2" in p for p in problems), problems)


@requires_data
class TestRenameDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(DATA, "index.json"), encoding="utf-8") as fh:
            cls.known = {rec["entity"] for rec in json.load(fh)}

    def suggest(self, name):
        return build_reference_data.suggest_rename(name, self.known)

    def test_case_only_rename(self):
        self.assertEqual(self.suggest("Orion.VIM.LUNs"), ["Orion.VIM.Luns"])

    def test_typo_in_source_material(self):
        self.assertEqual(
            self.suggest("Orion.SRM.FIleServerIdentification"),
            ["Orion.SRM.FileServerIdentification"],
        )

    def test_namespace_move_keeping_the_leaf(self):
        self.assertIn("Orion.UCS.Blades", self.suggest("Orion.NPM.UCSBlades"))

    def test_deeper_namespace_wins_over_a_shallow_leaf_match(self):
        self.assertEqual(self.suggest("Orion.F5.Device"), ["Orion.F5.System.Device"])

    def test_generic_leaf_does_not_produce_a_guess(self):
        # "Nodes" matches dozens of entities. A suggestion here would be worse than none,
        # because it looks authoritative.
        self.assertEqual(self.suggest("Orion.F5.Nodes"), [])

    def test_existing_entity_is_not_reported_as_renamed(self):
        self.assertEqual(self.suggest("Orion.Nodes"), ["Orion.Nodes"])


class TestVerbChangeClassification(unittest.TestCase):
    """Invoke sends a positional array, and the classification follows from that."""

    def diff_one_verb(self, old_params, new_params, required=()):
        def entity(params):
            return {
                "Test.Entity": {
                    "entity": "Test.Entity",
                    "properties": [],
                    "sourceRelationships": [],
                    "targetRelationships": [],
                    "inheritance": [],
                    "supportedOperations": ["read"],
                    "verbs": [
                        {
                            "name": "DoThing",
                            "parameters": [
                                {"name": p, "required": p in required} for p in params
                            ],
                        }
                    ],
                }
            }

        result = diff_schema.diff(entity(old_params), entity(new_params))
        return result["verbChanges"][0] if result["verbChanges"] else None

    def test_identical_signature_is_not_reported(self):
        self.assertIsNone(self.diff_one_verb(["a", "b"], ["a", "b"]))

    def test_recasing_is_cosmetic(self):
        # Names never travel on the wire, so a positional caller cannot notice this.
        # Reporting it as breaking buried the one real finding in the 2025.4 comparison.
        change = self.diff_one_verb(["NodeId", "Type"], ["nodeId", "type"])
        self.assertEqual(change["severity"], "cosmetic")

    def test_appending_an_optional_argument_is_additive(self):
        change = self.diff_one_verb(["a", "b"], ["a", "b", "c"])
        self.assertEqual(change["severity"], "additive")

    def test_appending_a_required_argument_is_behavioural(self):
        change = self.diff_one_verb(["a", "b"], ["a", "b", "c"], required=("c",))
        self.assertEqual(change["severity"], "behavioural")

    def test_inserting_an_argument_mid_signature_is_breaking(self):
        # The caller still passes the right number of arguments and they land in the
        # wrong slots, which is the failure mode worth shouting about.
        change = self.diff_one_verb(["a", "b", "c"], ["a", "x", "b", "c"])
        self.assertEqual(change["severity"], "breaking")
        self.assertIn("order changed", change["reason"])

    def test_removing_an_argument_is_breaking(self):
        change = self.diff_one_verb(["a", "b"], ["a"])
        self.assertEqual(change["severity"], "breaking")


@requires_data
class TestDeterminism(unittest.TestCase):
    def test_rename_suggestions_are_stable(self):
        # Ties used to be broken by set iteration order, and Python randomizes string
        # hashing per process, so repeated builds disagreed. Sorting on (length, name)
        # is what makes "regenerate and commit" produce an empty diff.
        with open(os.path.join(DATA, "index.json"), encoding="utf-8") as fh:
            known = {rec["entity"] for rec in json.load(fh)}
        first = build_reference_data.suggest_rename("Orion.F5.Pools", known)
        for _ in range(20):
            self.assertEqual(build_reference_data.suggest_rename("Orion.F5.Pools", set(known)), first)


@requires_data
class TestProseReferences(unittest.TestCase):
    """Entity and member names written in prose are held to the same standard as queries."""

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer

        cls.cer = cer
        cls.entities, _, _ = cer.load_schema(VERSION)
        cls.prefixes = cer.namespace_prefixes(cls.entities)
        index = validate_swql.SchemaIndex(VERSION)

        verbs = {}
        for name, rec in index.entities.items():
            chain = (rec.get("inheritance") or []) + [name]
            verbs[name] = {
                v["name"].lower()
                for anc in chain
                if index.entities.get(anc)
                for v in index.entities[anc].get("verbs") or []
            }

        def members(entity):
            props, navs = index.members(entity)
            return {**props, **{v: "verb" for v in verbs.get(entity, set())}}, navs

        cls.members = staticmethod(members)

    def ok(self, token):
        return self.cer.resolves(token, self.entities, self.prefixes, self.members)[0]

    def test_entity_name(self):
        self.assertTrue(self.ok("Orion.Nodes"))

    def test_namespace_prefix(self):
        # Pages write "entities prefixed Orion.APM." constantly.
        self.assertTrue(self.ok("Orion.APM"))

    def test_property_reference(self):
        self.assertTrue(self.ok("Orion.Nodes.Caption"))

    def test_inherited_property_reference(self):
        self.assertTrue(self.ok("Orion.Nodes.Uri"))

    def test_navigation_chain(self):
        self.assertTrue(self.ok("Orion.Nodes.Interfaces.Name"))

    def test_verb_reference(self):
        # Naming a verb as Entity.Verb is the normal way to write it in prose.
        self.assertTrue(self.ok("Orion.Nodes.Unmanage"))

    def test_property_on_the_wrong_entity_fails(self):
        # Orion.Nodes has IPAddress; Orion.Engines does not, and this is the class of
        # error the prose check exists for.
        self.assertFalse(self.ok("Orion.Nodes.Frobnicate"))

    def test_navigation_that_does_not_exist_fails(self):
        # Documented in docs/swql/joins-and-navigation.md precisely because people assume
        # it works. It is allowlisted in the docs, but resolves() must still reject it.
        self.assertFalse(self.ok("Orion.APM.Component.Node"))

    def test_invented_entity_fails(self):
        self.assertFalse(self.ok("Orion.NodesX"))


class TestNegationDetection(unittest.TestCase):
    """Naming a form that does not exist, in order to warn readers off it, is good writing.

    The checker has to accept those without also accepting an invented name asserted as
    real, which is the whole point of the check.
    """

    def negated(self, text, token):
        import check_entity_references as cer

        start = text.index(token)
        return cer.negated_nearby(text, start, start + len(token))

    def test_negation_before_the_name(self):
        self.assertTrue(self.negated("There is no `Orion.QoE.` namespace.", "Orion.QoE"))

    def test_negation_after_the_name(self):
        self.assertTrue(
            self.negated("`Orion.APM.Component.Node` does not exist; use the application.",
                         "Orion.APM.Component.Node")
        )

    def test_rather_than_counts_as_negation(self):
        self.assertTrue(
            self.negated("Use Orion.APM.Application rather than `Orion.SAM.Application`.",
                         "Orion.SAM.Application")
        )

    def test_plain_assertion_is_not_negated(self):
        # An invented name stated as fact is exactly what must still be reported.
        self.assertFalse(
            self.negated("Query `Orion.Bogus.Thing` to list the widgets.", "Orion.Bogus.Thing")
        )

    def test_negation_in_a_previous_paragraph_does_not_carry_over(self):
        text = "There is no such thing.\n\nQuery `Orion.Bogus.Thing` for the widgets."
        self.assertFalse(self.negated(text, "Orion.Bogus.Thing"))

    def test_unrelated_not_after_the_name_is_not_enough(self):
        # "not" appears, but it does not negate the name, so the forward pattern is
        # deliberately anchored and should not fire.
        self.assertFalse(
            self.negated("`Orion.Bogus.Thing` returns rows that have not been polled.",
                         "Orion.Bogus.Thing")
        )


@requires_data
class TestPathFinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = Schema(VERSION)

    def adjacency(self, entity):
        rec = self.schema.get(entity)
        return {r["name"]: r["type"] for r in rec["sourceRelationships"] + rec["targetRelationships"]}

    def test_interfaces_reach_nodes_in_one_hop(self):
        self.assertEqual(self.adjacency("Orion.NPM.Interfaces").get("Node"), "Orion.Nodes")

    def test_components_reach_applications_in_one_hop(self):
        self.assertEqual(
            self.adjacency("Orion.APM.Component").get("Application"), "Orion.APM.Application"
        )

    def test_components_do_not_reach_nodes_directly(self):
        # The route is Component.Application.Node. Documenting a direct Component.Node
        # would be wrong, and this is the assertion that keeps that honest.
        self.assertNotIn("Node", self.adjacency("Orion.APM.Component"))


class TestCountClaims(unittest.TestCase):
    """Numeric claims about the schema are checked against the schema.

    The design constraint is precision rather than recall. Prose counts subsets far more
    often than totals, so the tests that matter most here are the ones asserting that a
    true sentence about a subset is left alone.
    """

    @classmethod
    def setUpClass(cls):
        import check_counts

        cls.mod = check_counts
        cls.schema = check_counts.Schema(VERSION)

    def claims(self, sentence):
        return list(self.mod.claims_in(sentence, self.schema))

    def verdicts(self, sentence):
        return [(claimed == actual) for _, claimed, actual, _, _ in self.claims(sentence)]

    def test_number_word_parsing(self):
        self.assertEqual(self.mod.to_int("seven"), 7)
        self.assertEqual(self.mod.to_int("twenty-five"), 25)
        self.assertEqual(self.mod.to_int("2,067"), 2067)

    def test_number_word_is_not_matched_inside_a_compound(self):
        # "Twenty-five entities inherit from X" must read as 25, not as a stray "five".
        # Getting this wrong turns a correct page into a reported error.
        sentence = "Twenty-five entities inherit from `System.CustomPropertiesEntity` in 2026.2."
        self.assertEqual(self.verdicts(sentence), [True])

    def test_declared_property_count(self):
        self.assertEqual(self.verdicts("`Orion.Nodes` declares 102 properties."), [True])

    def test_inherited_property_count_also_accepted(self):
        # Both readings are legitimate and the prose does not always say which it means.
        self.assertEqual(self.verdicts("`Orion.Nodes` declares 113 properties."), [True])

    def test_wrong_property_count_is_caught(self):
        self.assertEqual(self.verdicts("`Orion.Nodes` declares 99 properties."), [False])

    def test_parenthesised_count(self):
        self.assertEqual(self.verdicts("`Orion.VIM.Luns` (7 properties) is the block device."), [True])

    def test_inheritance_count(self):
        sentence = "174 entities inherit from `System.ManagedEntity`."
        self.assertEqual(self.verdicts(sentence), [True])

    def test_wrong_inheritance_count_is_caught(self):
        self.assertEqual(self.verdicts("9 entities inherit from `System.ManagedEntity`."), [False])

    def test_verb_arity(self):
        self.assertEqual(self.verdicts("`Orion.Nodes.Unmanage` takes five arguments."), [True])

    def test_wrong_verb_arity_is_caught(self):
        self.assertEqual(self.verdicts("`Orion.Nodes.Unmanage` takes two arguments."), [False])

    def test_subset_phrasing_is_not_treated_as_a_total(self):
        # True sentences about entities with many more verbs than the number given. Each
        # one of these was a false positive before the subset guard existed.
        for sentence in (
            "There are two verbs on `Cirrus.ConfigArchive`: `Diff` and `CompareConfigs`.",
            "Both inherit from `System.CustomPropertiesEntity` and carry the standard "
            "four verbs, `CreateCustomProperty` and the rest.",
            "`Orion.AlertConfigurations` carries three verbs whose names say what that is.",
        ):
            self.assertEqual(self.claims(sentence), [], f"should be skipped: {sentence}")

    def test_unknown_entity_is_ignored(self):
        # Inventing a name is check_entity_references.py's job, not this one's.
        self.assertEqual(self.claims("`Orion.Nope` declares 5 properties."), [])

    def test_navigation_count_spans_both_relationship_lists(self):
        # The schema splits relationships into source and target, and both are navigable
        # from the declaring entity, so a navigation count is the two together.
        declared, resolved = self.schema.member_counts("Orion.Nodes", "navigation properties")
        record = self.schema.entities["Orion.Nodes"]
        self.assertEqual(
            declared,
            len(record["sourceRelationships"]) + len(record["targetRelationships"]))
        self.assertGreaterEqual(resolved, declared)

    def test_wrong_navigation_count_is_caught(self):
        self.assertEqual(
            self.verdicts("`Orion.Nodes` declares 5 navigation properties."), [False])

    def test_a_count_scoped_to_a_destination_is_skipped(self):
        # "two navigation properties into NCM" is a true sentence about an entity with 161
        # of them. The qualifier sits after the phrase the pattern matches, so the subset
        # guard has to look past the match rather than only inside it.
        sentence = "`Orion.Nodes` declares exactly two navigation properties into NCM:"
        self.assertEqual(self.claims(sentence), [])

    def test_an_ordinary_continuation_is_not_read_as_scoping(self):
        # The scoping guard must not swallow a real total that simply continues.
        self.assertEqual(
            self.verdicts("`Orion.Nodes` declares 102 properties in the 2026.2 schema."),
            [True])


@requires_data
class TestReturnTypes(unittest.TestCase):
    """The shape of what a verb returns, extracted from the Swagger contract.

    The entity pages give only a type name, so before this existed "what do I get back"
    had no answer short of reading SolarWinds' Swagger by hand, and a page could assert a
    return shape that nothing checked.
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(DATA, "types.json"), encoding="utf-8") as fh:
            cls.types = json.load(fh)
        with open(os.path.join(DATA, "verbs.json"), encoding="utf-8") as fh:
            cls.verbs = json.load(fh)

    def test_a_useful_number_of_returns_resolve(self):
        known = [v for v in self.verbs if v.get("returns") in self.types]
        self.assertGreater(len(known), 400)

    def test_the_alert_import_result_has_five_members(self):
        # SolarWinds' own page describes three. The two extra booleans are what turn a
        # silent partial import into a diagnosable one.
        record = self.types["SolarWinds.Orion.Core.Common.Alerting.AlertImportResult"]
        names = [m["name"] for m in record["members"]]
        self.assertEqual(names, ["AlertId", "Name", "MigrationMessage",
                                 "IncorrectPasswordForDecryptSensitiveData",
                                 "AlertDefinitionIsNotSupported"])

    def test_an_array_return_keeps_its_element_type(self):
        # 65 verbs return a bare "array". Recording only that loses the whole answer.
        verb = next(v for v in self.verbs
                    if v["entity"] == "Orion.AlertSuppression"
                    and v["name"] == "GetAlertSuppressionState")
        self.assertEqual(verb["returns"], "array")
        self.assertIn(verb["returnsItems"], self.types)
        members = self.types[verb["returnsItems"]]["members"]
        self.assertIn("SuppressionMode", [m["name"] for m in members])

    def test_member_types_are_collected_transitively(self):
        # A return shape whose member is an enum is only half an answer without the enum.
        mode = self.types["SolarWinds.Orion.Core.Common.Models.Alerts.EntityAlertSuppressionMode"]
        self.assertEqual(mode["kind"], "string")
        self.assertIn("SuppressedByParent", mode["enum"])

    def test_the_suppression_enum_is_strings_not_integers(self):
        # Worth pinning: a page once tabulated these as 0 to 4, which the contract does
        # not say. The values on the wire are the names.
        mode = self.types["SolarWinds.Orion.Core.Common.Models.Alerts.EntityAlertSuppressionMode"]
        self.assertTrue(all(isinstance(v, str) for v in mode["enum"]))

    def test_every_recorded_return_type_is_actually_referenced(self):
        referenced = set()
        for v in self.verbs:
            referenced.add(v.get("returns"))
            referenced.add(v.get("returnsItems"))
            for p in v.get("parameters") or []:
                referenced.add(p.get("type"))
                if isinstance(p.get("items"), dict):
                    referenced.add(p["items"].get("type"))
        # Everything else got in by being a member type of something referenced.
        member_types = {m.get("type") for r in self.types.values() for m in r.get("members", [])}
        member_types |= {m.get("items") for r in self.types.values() for m in r.get("members", [])}
        for name in self.types:
            self.assertTrue(name in referenced or name in member_types, name)


@requires_data
class TestNetObjectIdContract(unittest.TestCase):
    """The argument name `netObjectId` is not the argument's contract.

    Twelve verbs declare it `string` and want `N:42`; nine declare it `number` and want the
    bare key. The guides used to say the string form was universal, which is the kind of
    plausible blanket rule that produces a call SWIS accepts and answers wrongly.
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(DATA, "verbs.json"), encoding="utf-8") as fh:
            verbs = json.load(fh)
        cls.taking = [
            (v["entity"], v["name"], p.get("type"))
            for v in verbs
            for p in (v.get("parameters") or [])
            if p.get("name", "").lower() == "netobjectid"
        ]

    def test_both_declared_types_are_present(self):
        kinds = {t for _, _, t in self.taking}
        self.assertEqual(kinds, {"string", "number"})

    def test_the_number_typed_verbs_are_the_real_time_polling_family(self):
        # These are the ones a blanket "always send N:42" rule gets wrong. Nine are the
        # real-time polling family; the tenth arrived with the contract-only verbs, on an
        # entity that has no rendered schema page.
        numbers = {f"{e}.{v}" for e, v, t in self.taking if t == "number"}
        polling = {
            f"{entity}.{verb}"
            for entity in ("Orion.Nodes", "Orion.NPM.Interfaces", "Orion.Volumes")
            for verb in ("GetSupportedMetrics", "StartRealTimePolling", "StopRealTimePolling")
        }
        self.assertEqual(numbers, polling | {"Orion.SRM.BusinessLayer.AddManualE2EMapping"})

    def test_unmanage_still_wants_the_string_form(self):
        by_key = {f"{e}.{v}": t for e, v, t in self.taking}
        self.assertEqual(by_key.get("Orion.Nodes.Unmanage"), "string")

    def test_the_same_entity_can_take_both_forms(self):
        on_nodes = {t for e, _, t in self.taking if e == "Orion.Nodes"}
        self.assertEqual(on_nodes, {"string", "number"})


class TestSummaryTables(unittest.TestCase):
    """A table whose columns are member counts is checked row by row.

    The header names what each column counts, so the numbers are unambiguous without the
    prose repeating the entity. Eight pages use this shape for 77 figures, none of which
    any other check could see.
    """

    @classmethod
    def setUpClass(cls):
        import check_counts

        cls.mod = check_counts
        cls.schema = check_counts.Schema(VERSION)

    def claims(self, text):
        return list(self.mod.table_claims(text, self.schema))

    TABLE = ("| Entity | Properties | Verbs | What it is |\n"
             "|---|---:|---:|---|\n"
             "| `Orion.AgentManagement.Agent` | 37 | 20 | One row per agent. |\n"
             "| `Orion.AgentManagement.AgentPlugin` | 6 | 0 | One row per plugin. |\n")

    def test_every_count_column_is_read(self):
        found = self.claims(self.TABLE)
        self.assertEqual(len(found), 4)
        for _, claimed, actual, _, _ in found:
            self.assertEqual(claimed, actual)

    def test_a_wrong_figure_is_caught(self):
        wrong = self.TABLE.replace("| 37 |", "| 39 |")
        bad = [c for c in self.claims(wrong) if c[1] != c[2]]
        self.assertEqual(len(bad), 1)
        self.assertIn("properties", bad[0][0])

    def test_a_zero_count_is_still_checked(self):
        # AgentPlugin really does declare no verbs, and 0 must not be read as "no claim".
        found = [c for c in self.claims(self.TABLE) if c[0].endswith("verbs") and c[1] == 0]
        self.assertTrue(found)

    def test_a_table_without_count_columns_is_ignored(self):
        table = ("| Entity | What it is |\n|---|---|\n"
                 "| `Orion.Nodes` | The device record |\n")
        self.assertEqual(self.claims(table), [])

    def test_rows_naming_something_that_is_not_an_entity_are_skipped(self):
        table = ("| Entity | Properties |\n|---|---:|\n"
                 "| `Not.An.Entity` | 12 |\n| some prose | 4 |\n")
        self.assertEqual(self.claims(table), [])

    def test_the_real_pages_are_consistent(self):
        import glob as _glob

        total = 0
        for path in _glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True):
            if self.mod.is_generated(path):
                continue
            with open(path, encoding="utf-8") as fh:
                found = self.claims(fh.read())
            total += len(found)
            self.assertEqual([c for c in found if c[1] != c[2]], [], path)
        self.assertGreater(total, 50)


class TestSizeParagraphs(unittest.TestCase):
    """The `**Size.**` convention gives an entity's shape in one line, and the entity is
    its section heading rather than a name in the sentence."""

    @classmethod
    def setUpClass(cls):
        import check_counts

        cls.mod = check_counts
        cls.schema = check_counts.Schema(VERSION)

    def claims(self, text):
        return list(self.mod.size_claims(text, self.schema))

    def test_entity_comes_from_the_heading(self):
        text = ("## `Orion.Volumes`\n\n**Size.** 53 declared properties, 19 source "
                "relationships, 3 target relationships, 5 verbs.\n")
        found = self.claims(text)
        self.assertEqual(len(found), 4)
        for label, claimed, actual, _, _ in found:
            self.assertTrue(label.startswith("Orion.Volumes"), label)
            self.assertEqual(claimed, actual, label)

    def test_a_wrong_figure_is_caught(self):
        text = ("## `Orion.Volumes`\n\n**Size.** 53 declared properties, 19 source "
                "relationships, 7 target relationships, 5 verbs.\n")
        wrong = [c for c in self.claims(text) if c[1] != c[2]]
        self.assertEqual(len(wrong), 1)
        self.assertIn("target relationships", wrong[0][0])

    def test_no_verbs_at_all_is_checked_as_zero(self):
        text = ("## `Orion.Engines`\n\n**Size.** 51 declared properties, 9 source "
                "relationships, 3 target relationships, and **no verbs at all**.\n")
        found = self.claims(text)
        verbs = [c for c in found if c[0].endswith("verbs")]
        self.assertTrue(verbs)
        for _, claimed, actual, _, _ in verbs:
            self.assertEqual(claimed, actual)

    def test_a_size_paragraph_under_a_non_entity_heading_is_skipped(self):
        text = "## Sizing\n\n**Size.** 53 declared properties, 5 verbs.\n"
        self.assertEqual(self.claims(text), [])

    def test_the_real_page_is_fully_consistent(self):
        with open(os.path.join(ROOT, "docs", "schema", "key-entities.md"), encoding="utf-8") as fh:
            text = fh.read()
        found = self.claims(text)
        self.assertGreater(len(found), 25)
        self.assertEqual([c for c in found if c[1] != c[2]], [])


class TestPropertyTypeClaims(unittest.TestCase):
    """Property types stated in prose are checked against the schema.

    The two NodeID columns are the case that matters: `Cirrus.Nodes.NodeID` is a GUID and
    `Orion.Nodes.NodeID` an integer, and the guides explain a whole class of silent
    join failure with those two facts. Swapping them would make the explanation wrong in a
    way no query validator would notice.
    """

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer

        cls.cer = cer
        index = validate_swql.SchemaIndex(VERSION)
        cls.members = staticmethod(index.members)

    def problems(self, text):
        return self.cer.type_claims(text, self.members)

    def test_correct_type_passes(self):
        self.assertEqual(self.problems("`Orion.Nodes.NodeID` is a `System.Int32`."), [])

    def test_swapped_id_types_are_caught(self):
        found = self.problems(
            "`Cirrus.Nodes.NodeID` is a `System.Int32` and `Orion.Nodes.NodeID` is a `System.Guid`."
        )
        self.assertEqual(len(found), 2)
        self.assertEqual({token for token, _, _ in found},
                         {"Cirrus.Nodes.NodeID", "Orion.Nodes.NodeID"})

    def test_inherited_property_type_resolves(self):
        # Uri is declared on System.Entity, not on Orion.Nodes.
        self.assertEqual(self.problems("`Orion.Nodes.Uri` is a `System.String`."), [])

    def test_navigation_property_is_left_alone(self):
        # A navigation property is described by its relationship kind, which is a
        # different sort of statement than a member type.
        self.assertEqual(self.problems("`Orion.Nodes.Interfaces` is a `System.Hosting`."), [])

    def test_unknown_entity_is_left_to_the_name_check(self):
        self.assertEqual(self.problems("`Orion.Nope.Thing` is a `System.Int32`."), [])


class TestNetObjectPrefixes(unittest.TestCase):
    """NetObject prefixes written in prose have to be real ones.

    A verb taking a netObjectId wants `N:42` rather than `42`, and an invented prefix is
    the same plausible-but-wrong failure as an invented entity name: the call is accepted
    and acts on nothing, or on the wrong kind of object.
    """

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer

        cls.cer = cer
        cls.prefixes = cer.load_netobject_prefixes()

    def test_reference_data_loaded(self):
        self.assertGreater(len(self.prefixes), 50)

    def test_known_prefixes_map_to_the_right_entities(self):
        self.assertIn("Orion.Nodes", self.prefixes["N"])
        self.assertIn("Orion.NPM.Interfaces", self.prefixes["I"])
        self.assertIn("Orion.Volumes", self.prefixes["V"])

    def test_real_prefixes_pass(self):
        text = "A node is `N:42`, an interface `I:7`, an application `AA:<ApplicationID>`."
        self.assertEqual(self.cer.netobject_claims(text, self.prefixes), [])

    def test_invented_prefix_is_caught(self):
        found = self.cer.netobject_claims("A node is `ZZ:42`.", self.prefixes)
        self.assertEqual(found, ["`ZZ:42`"])

    def test_bare_prefix_form_is_recognised(self):
        self.assertEqual(self.cer.netobject_claims("The prefix is `TSR:`.", self.prefixes), [])


class TestGeneratedFileDetection(unittest.TestCase):
    """Generated pages are skipped by their banner, not by their directory.

    docs/reference/ is mostly generated, and checking an enumeration of the same data it
    was generated from proves nothing. Skipping the whole directory would also skip a
    hand-written page that lives there, such as a glossary, which is exactly the kind of
    page that needs checking.
    """

    @classmethod
    def setUpClass(cls):
        import check_counts
        import check_signatures

        cls.mods = (check_counts, check_signatures)

    def test_every_generated_reference_page_is_detected(self):
        pages = glob.glob(os.path.join(ROOT, "docs", "reference", "*.md"))
        self.assertGreater(len(pages), 4)
        for page in pages:
            with open(page, encoding="utf-8") as fh:
                banner = "GENERATED FILE" in fh.read(400)
            for mod in self.mods:
                self.assertEqual(mod.is_generated(page), banner, page)

    def test_a_hand_written_page_is_not_skipped(self):
        for mod in self.mods:
            self.assertFalse(mod.is_generated(os.path.join(ROOT, "docs", "README.md")))
            self.assertFalse(mod.is_generated(os.path.join(ROOT, "CONTRIBUTING.md")))


class TestUnverifiedIndex(unittest.TestCase):
    """The index of what this repository declines to assert is generated from the prose.

    AGENTS.md and llms.txt both send a reader here before answering anything load-bearing,
    so a statement the extractor drops or mangles is a statement that silently stops being
    surfaced as uncertain.
    """

    @classmethod
    def setUpClass(cls):
        import build_unverified_index

        cls.mod = build_unverified_index

    def test_bold_label_form_is_recognised(self):
        # "**Unverified.** The standard SQL spelling..." marks a whole claim rather than
        # qualifying one inside a sentence, and only the sentence forms were read before.
        self.assertTrue(self.mod.MARKER_RE.search("**Unverified.** The standard SQL spelling"))

    def test_sentence_forms_still_recognised(self):
        for text in (
            "Whether the simple form is accepted **is unverified here**.",
            "This repository cannot verify them.",
            "The accepted values are not recorded in the published schema.",
        ):
            self.assertTrue(self.mod.MARKER_RE.search(text), text)

    def test_ordinary_prose_is_not_marked(self):
        self.assertFalse(self.mod.MARKER_RE.search("Verify this on your own server first."))

    def test_a_marker_split_across_a_line_break_is_found(self):
        # The prose is hard-wrapped, so a multi-word marker routinely straddles a newline.
        # Testing the raw paragraph means a literal space in the pattern never matches and
        # the statement is silently dropped from the index.
        para = "which licence is a licensing question rather than a schema one, and is not\nrecorded in the published schema."
        self.assertFalse(self.mod.MARKER_RE.search(para))
        self.assertTrue(self.mod.MARKER_RE.search(" ".join(para.split())))

    def test_the_glossary_is_collected(self):
        # A hand-written page under docs/reference/. Skipping that directory wholesale,
        # rather than skipping on the generated banner, used to exclude it.
        found = self.mod.collect(os.path.join(ROOT, "docs"))
        self.assertIn(os.path.join("docs", "reference", "glossary.md"), found)

    def test_generated_pages_are_not_collected(self):
        found = self.mod.collect(os.path.join(ROOT, "docs"))
        for page in ("unverified.md", "entity-index.md", "verb-index.md"):
            self.assertNotIn(os.path.join("docs", "reference", page), found)

    def test_numbered_list_item_starts_a_new_sentence(self):
        # Without the digit in the lookahead the "3." opening the next item was read as
        # part of the previous sentence and trailed into the index.
        para = "timings reported by `WITH QUERYSTATS`.\n3. **An injection class disappears.**"
        first = self.mod.statements(para)[0]
        self.assertTrue(first.endswith("`WITH QUERYSTATS`."), first)

    def test_bold_markers_stay_balanced(self):
        para = "**`UNION ALL` is unverified.** The official reference documents only `UNION`."
        for s in self.mod.statements(para):
            self.assertEqual(s.count("**") % 2, 0, s)

    def test_a_table_yields_rows_not_one_blob(self):
        # A table has no blank line between rows, so the whole thing is one paragraph.
        para = (
            "| Operator | Meaning | Evidence |\n"
            "|:---|:---|:---|\n"
            "| `=` | Equal | Used throughout |\n"
            "| `<>` | Not equal | **Unverified.** Appears in no sample |\n"
        )
        rows = self.mod.statements(para)
        self.assertEqual(len(rows), 3)  # header plus two data rows, no separator rule
        marked = [r for r in rows if self.mod.MARKER_RE.search(r)]
        self.assertEqual(len(marked), 1)
        self.assertIn("`<>`", marked[0])
        self.assertNotIn("Equal | Used throughout", marked[0])

    def test_prose_paragraph_is_not_treated_as_a_table(self):
        para = "One sentence here. A second one follows it."
        self.assertEqual(len(self.mod.statements(para)), 2)

    def test_same_page_anchor_is_requalified_to_its_source(self):
        # A lifted sentence lands in docs/reference/, so a bare "#anchor" would point at a
        # heading of the index rather than of the page the sentence came from.
        out = self.mod.requalify_links(
            "listed in [what is not verified here](#what-is-not-verified-here).",
            "docs/modules/vnqm.md",
        )
        self.assertIn("(../modules/vnqm.md#what-is-not-verified-here)", out)

    def test_relative_path_is_rebased(self):
        # Written relative to docs/swql/, it has to resolve from docs/reference/.
        out = self.mod.requalify_links(
            "see [joins](joins-and-navigation.md#querying-a-base-entity).",
            "docs/swql/gotchas.md",
        )
        self.assertIn("(../swql/joins-and-navigation.md#querying-a-base-entity)", out)

    def test_external_links_are_left_alone(self):
        text = "see [the reference](https://solarwinds.github.io/OrionSDK/docs/)."
        self.assertEqual(self.mod.requalify_links(text, "docs/swql/functions.md"), text)

    def test_a_heading_after_an_entry_is_separated_by_a_blank_line(self):
        # A bold line straight after a "- " bullet is a lazy continuation of that list
        # item, so every section heading rendered inside the entry above it instead of
        # over the ones below. It read as a wall of bullets on the rendered page.
        page = open(os.path.join(ROOT, "docs", "reference", "unverified.md")).read()
        lines = page.split("\n")
        glued = [
            i + 1
            for i in range(len(lines) - 1)
            if lines[i].startswith("- ") and lines[i + 1].startswith("**[")
        ]
        self.assertEqual(glued, [], f"headings absorbed into the entry above: {glued}")


class TestRightsClaims(unittest.TestCase):
    """A right named in prose has to be one the schema declares.

    An invented right sends a reader to look for a permission that does not exist, which
    is a worse outcome than no guidance at all.
    """

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer

        cls.cer = cer
        cls.rights = cer.load_rights(VERSION)

    def test_the_rights_the_guides_lean_on_are_real(self):
        for right in ("manageNodes", "allowUnmanage", "allowRealTimePolling", "admin"):
            self.assertIn(right, self.rights)

    def test_real_right_passes(self):
        self.assertEqual(
            self.cer.right_claims("It requires the `manageNodes` right.", self.rights), [])

    def test_invented_right_is_caught(self):
        self.assertEqual(
            self.cer.right_claims("It requires the `manageEverything` right.", self.rights),
            ["manageEverything"])

    def test_an_operation_named_as_a_right_is_not_reported(self):
        # The guides write "an entity-level `invoke` right", meaning the right governing
        # the invoke operation rather than a right called invoke. Reporting those would be
        # noise, so the pattern only reads the "requires ..." form.
        text = "363 belong to an entity that declares an `invoke` right of its own."
        self.assertEqual(self.cer.right_claims(text, self.rights), [])


@requires_data
class TestMemberTables(unittest.TestCase):
    """A table documenting a type's members is checked against the extracted contract.

    The type is named in the sentence introducing the table, by its short name. These
    document the shape of what a verb returns or takes, which nothing else could check
    until the type definitions were extracted.
    """

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer

        cls.cer = cer
        cls.types = cer.load_types(VERSION)

    TABLE = ("`Orion.NPM.Interfaces.CreateInterfacesPluginConfiguration` takes an\n"
             "`InterfacesDiscoveryPluginContext`:\n"
             "\n"
             "| Member | Type | Notes |\n"
             "|:---|:---|:---|\n"
             "| `UseDefaults` | boolean | ok |\n"
             "| `AutoImportStatus` | array | ok |\n")

    def test_types_load_with_unique_short_names(self):
        self.assertGreater(len(self.types), 100)
        self.assertIn("InterfacesDiscoveryPluginContext", self.types)

    def test_a_correct_table_reports_nothing(self):
        resolved, problems = self.cer.member_table_claims(self.TABLE, self.types)
        self.assertEqual(resolved, 1)
        self.assertEqual(problems, [])

    def test_an_invented_member_is_caught(self):
        bad = self.TABLE.replace("`AutoImportStatus`", "`AutoImportStatuses`")
        _, problems = self.cer.member_table_claims(bad, self.types)
        self.assertEqual(problems,
                         [("InterfacesDiscoveryPluginContext", "AutoImportStatuses")])

    def test_the_lead_paragraph_is_found_across_the_blank_line(self):
        # A markdown table is always preceded by a blank line. Stopping the backward scan
        # at the first blank line leaves the lead empty and makes the whole check inert,
        # which is how it was first written.
        resolved, _ = self.cer.member_table_claims(self.TABLE, self.types)
        self.assertEqual(resolved, 1)

    def test_a_table_with_no_type_named_above_it_is_skipped(self):
        text = self.TABLE.replace("`InterfacesDiscoveryPluginContext`", "some context")
        resolved, problems = self.cer.member_table_claims(text, self.types)
        self.assertEqual((resolved, problems), (0, []))

    def test_the_real_pages_are_consistent(self):
        import glob as _glob

        total = 0
        for path in _glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "GENERATED FILE" in text[:400]:
                continue
            resolved, problems = self.cer.member_table_claims(text, self.types)
            total += resolved
            self.assertEqual(problems, [], path)
        self.assertGreaterEqual(total, 4)


class TestAtomicWrites(unittest.TestCase):
    """The data writers rename into place rather than truncating the target.

    These files are large. Anything reading one while a rebuild runs gets a
    JSONDecodeError partway through, which surfaced three times as a spurious CI failure
    before the writers were changed.
    """

    def test_both_data_writers_are_atomic(self):
        import inspect

        import build_reference_data
        import build_schema_data

        for module in (build_schema_data, build_reference_data):
            source = inspect.getsource(module.write_json)
            self.assertIn("os.replace", source, module.__name__)
            self.assertIn(".tmp", source, module.__name__)

    def test_a_write_leaves_no_temporary_behind(self):
        import json as _json
        import tempfile

        import build_schema_data

        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "out.json")
            build_schema_data.write_json(target, {"a": 1})
            self.assertEqual(_json.load(open(target, encoding="utf-8")), {"a": 1})
            self.assertEqual(sorted(os.listdir(d)), ["out.json"])


class TestDotNetTypeNames(unittest.TestCase):
    """Verb signatures quoted in the documentation carry escaped .NET generics."""

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer

        cls.cer = cer

    def test_nested_element_types_are_collected(self):
        # docfx puts an array's element type one level down. Reading only the top level
        # means a page cannot paste a real verb signature without being reported.
        param = {
            "name": "configuration",
            "type": "array",
            "items": {"type": "System.Collections.Generic.KeyValuePair~System.String_System.String~"},
        }
        found = self.cer.type_names(param)
        self.assertIn("array", found)
        self.assertIn(
            "System.Collections.Generic.KeyValuePair~System.String_System.String~", found
        )

    def test_plain_parameter_still_yields_its_type(self):
        self.assertEqual(self.cer.type_names({"name": "nodeId", "type": "number"}), {"number"})

    def test_dotnet_namespaces_do_not_collide_with_swis_entities(self):
        # PowerShell samples name .NET types directly. Exempting those namespaces is only
        # safe while no real entity lives under one, so assert that rather than assume it.
        entities, _, _ = self.cer.load_schema(VERSION)
        clashing = [e for e in entities if e.startswith(self.cer.DOTNET_NAMESPACES)]
        self.assertEqual(clashing, [])
        # The SWIS System.* entities this must not start ignoring.
        self.assertIn("System.ManagedEntity", entities)
        self.assertFalse("System.ManagedEntity".startswith(self.cer.DOTNET_NAMESPACES))


class TestSignatureClaims(unittest.TestCase):
    """Verb signatures written in prose are checked against the positional contract.

    This is the highest-stakes claim in the repository: arguments never travel by name, so
    a reordered signature produces a call that fails silently rather than one that errors.
    """

    @classmethod
    def setUpClass(cls):
        import check_signatures

        cls.mod = check_signatures
        cls.contract = check_signatures.Contract(VERSION)

    def compare(self, shown, actual, elided=False):
        return self.mod.compare(shown, actual, elided)

    def test_notation_is_stripped_from_argument_names(self):
        # Prose writes nodeId[], Reboot? and componentId: number for real argument names.
        for written, plain in (
            ("nodeId[]", "nodeid"), ("Reboot?", "reboot"),
            ("componentId: number", "componentid"), ("configId1", "configid1"),
        ):
            self.assertEqual(self.mod.normalise(written), plain)

    def test_matching_signature_passes(self):
        self.assertIsNone(self.compare(["configId1", "configId2"], ["configId1", "configId2"]))

    def test_prefix_is_accepted(self):
        # A paragraph about which id space a verb takes writes only the first argument,
        # and a paragraph about a version change writes the older shorter form. Both are
        # correct prose, and treating them as errors would be noise.
        self.assertIsNone(self.compare(["nodeId"], ["nodeId", "configType"]))

    def test_reordered_arguments_are_caught(self):
        problem = self.compare(["configId2", "configId1"], ["configId1", "configId2"])
        self.assertIsNotNone(problem)
        self.assertIn("position 2", problem)

    def test_wrong_argument_name_is_caught(self):
        problem = self.compare(["configId1", "flavour"], ["configId1", "settings"])
        self.assertIsNotNone(problem)
        self.assertIn("settings", problem)

    def test_too_many_arguments_are_caught(self):
        problem = self.compare(["a", "b", "c"], ["a", "b"])
        self.assertIsNotNone(problem)
        self.assertIn("the contract has 2", problem)

    def test_elision_allows_a_gap_but_not_a_wrong_name(self):
        self.assertIsNone(self.compare(["subnetGroupId", "cidr"],
                                       ["subnetGroupId", "name", "cidr"], elided=True))
        self.assertIsNotNone(self.compare(["subnetGroupId", "nope"],
                                          ["subnetGroupId", "name", "cidr"], elided=True))

    def test_elision_still_requires_the_real_order(self):
        problem = self.compare(["cidr", "subnetGroupId"],
                               ["subnetGroupId", "name", "cidr"], elided=True)
        self.assertIsNotNone(problem)

    def test_resolution_prefers_an_entity_named_nearby(self):
        verb = self.contract.resolve("Unmanage", ["Orion.Nodes"])
        self.assertIsNotNone(verb)
        self.assertEqual(verb["entity"], "Orion.Nodes")

    def test_unknown_verb_name_resolves_to_nothing(self):
        self.assertIsNone(self.contract.resolve("Frobnicate", []))

    def test_balanced_scan_reads_a_nested_call(self):
        # A regex stopping at the first ')' truncates ToLocal(GetUtcDate()) and then
        # reports the mangled remainder.
        text = "`ToLocal(GetUtcDate())` converts."
        body = self.mod.balanced_arguments(text, text.index("("))
        self.assertEqual(body, "GetUtcDate()")
        self.assertEqual(self.mod.split_arguments(body), ["GetUtcDate()"])

    def test_unterminated_call_is_not_read(self):
        self.assertIsNone(self.mod.balanced_arguments("`Sum(a` and more", 4))

    def test_arguments_split_at_the_top_level_only(self):
        self.assertEqual(
            self.mod.split_arguments("a, Concat(b, c), d"), ["a", "Concat(b, c)", "d"])


class TestFunctionArity(unittest.TestCase):
    """SWQL functions are checked by argument count, since the reference names are
    placeholders that real prose has no reason to repeat."""

    @classmethod
    def setUpClass(cls):
        import check_signatures

        cls.functions = check_signatures.Functions()

    def test_fixed_arity(self):
        self.assertEqual(self.functions.arity("Round")[:2], (2, 2))
        self.assertEqual(self.functions.arity("Year")[:2], (1, 1))

    def test_variadic_is_unbounded(self):
        # Concat is written Concat(a, b, c, ...) and takes any number beyond that.
        low, high, _ = self.functions.arity("Concat")
        self.assertEqual(high, float("inf"))
        self.assertGreaterEqual(low, 1)

    def test_optional_arguments_widen_the_range(self):
        low, high, _ = self.functions.arity("String_Agg")
        self.assertEqual(low, 2)
        self.assertGreater(high, low)

    def test_unknown_name_has_no_arity(self):
        self.assertIsNone(self.functions.arity("Frobnicate"))


class TestSignatureNegation(unittest.TestCase):
    """A form named in order to warn readers off it must not be reported."""

    @classmethod
    def setUpClass(cls):
        import check_entity_references as cer
        import check_signatures

        cls.negated = staticmethod(cer.negated_nearby)
        cls.mod = check_signatures

    def span(self, text, name):
        start = text.index(f"`{name}(")
        body = self.mod.balanced_arguments(text, text.index("(", start))
        # The span must cover the closing backtick, or a negation that follows the call
        # is searched for in the middle of the arguments.
        return start, start + 1 + len(name) + 1 + len(body) + 2

    def test_negation_after_the_call_is_detected(self):
        text = "A standalone negation: `IsNull(x)` is not a thing."
        start, end = self.span(text, "IsNull")
        self.assertTrue(self.negated(text, start, end))

    def test_a_denial_after_an_intervening_clause_is_detected(self):
        # "a `DPA.AlarmLevel` entity that the 2026.2 schema does not publish" is a denial,
        # but the negation does not start immediately after the name, so the anchored
        # pattern alone misses it.
        import check_entity_references as cer

        text = ("Each description points at a `DPA.AlarmLevel` entity that the 2026.2 "
                "schema does not publish.")
        start = text.index("DPA.AlarmLevel")
        self.assertTrue(cer.negated_nearby(text, start, start + len("DPA.AlarmLevel")))

    def test_an_unrelated_later_negation_does_not_launder_a_name(self):
        import check_entity_references as cer

        text = ("Use `Orion.Invented` for this. Some other thing does not matter here at "
                "all, and neither does the rest of this sentence.")
        start = text.index("Orion.Invented")
        self.assertFalse(cer.negated_nearby(text, start, start + len("Orion.Invented")))

    def test_an_ordinary_call_is_not_read_as_negated(self):
        text = "Use `Round(v.Percent, 1)` to round the value."
        start, end = self.span(text, "Round")
        self.assertFalse(self.negated(text, start, end))


class TestContractSignatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import check_signatures

        cls.contract = check_signatures.Contract(VERSION)

    def test_real_signature_from_the_contract(self):
        verb = self.contract.resolve("SuppressAlerts", ["Orion.AlertSuppression"])
        names = [p["name"] for p in verb["parameters"]]
        self.assertEqual(names[:3], ["entityUris", "suppressFrom", "suppressUntil"])
        # The alerting guide states that only the first is required. Hold that claim here
        # too, since it is what makes the shorter published form safe to keep using.
        self.assertTrue(verb["parameters"][0]["required"])
        self.assertFalse(any(p["required"] for p in verb["parameters"][1:]))


class TestTableClaims(unittest.TestCase):
    """Facts stated in a table cell are held to the same standard as facts in a sentence.

    331 property/type rows and 25 fenced signatures were written across the guides and
    none of them were read by any checker: the prose forms were covered and the denser,
    more quotable table and block forms were not. A reader has no way to tell which half
    of a page was verified.
    """

    @classmethod
    def setUpClass(cls):
        import check_counts
        import check_entity_references

        cls.counts = check_counts
        cls.refs = check_entity_references

    def test_a_size_cell_is_read_as_a_count(self):
        cell = "16 properties, 1 verb"
        found = [
            (m.group("n"), m.group("kind"), bool(m.group("nav")))
            for m in self.counts.CELL_COUNT_RE.finditer(cell)
        ]
        self.assertEqual(found, [("16", "properties", False), ("1", "verb", False)])

    def test_navigation_properties_are_not_read_as_plain_properties(self):
        m = self.counts.CELL_COUNT_RE.search("11 navigation properties")
        self.assertTrue(m.group("nav"))

    def test_a_bare_year_in_a_cell_is_not_a_count(self):
        self.assertIsNone(self.counts.CELL_COUNT_RE.search("Added in 2023.4"))

    def test_the_subject_comes_from_the_whole_section_not_just_the_lead(self):
        # A section names its entity once and then hangs several tables off it. Reading
        # only the paragraph above the table left those unresolved and unchecked.
        lines = [
            "## The pool",
            "",
            "`Orion.HA.Pools` is the pool record.",
            "",
            "**The timers:**",
            "",
            "| Property | Type |",
        ]
        token_re = self.refs.entity_token_re({"Orion"})
        subject = self.refs.table_subject(lines, 6, {"Orion.HA.Pools"}, {}, token_re)
        self.assertEqual(subject, "Orion.HA.Pools")

    def test_an_ancestor_named_beside_its_descendant_is_not_the_subject(self):
        lines = [
            "### `Orion.Events`",
            "",
            "Eight declared, plus three inherited from `Orion.MixedObjectType`.",
            "",
            "| Property | Type |",
        ]
        token_re = self.refs.entity_token_re({"Orion"})
        subject = self.refs.table_subject(
            lines, 4,
            {"Orion.Events", "Orion.MixedObjectType"},
            {"Orion.Events": ["System.Entity", "Orion.MixedObjectType"]},
            token_re,
        )
        self.assertEqual(subject, "Orion.Events")

    def test_a_parent_heading_outranks_prose_that_quotes_another_entity(self):
        # "## Cirrus.Nodes" then "### Properties worth knowing", whose only prose mention
        # is Orion.Nodes inside a quoted schema description. Reading the nearest section's
        # body picked the quoted name and reported every row of a correct table.
        lines = [
            "## Cirrus.Nodes",
            "",
            "### Properties worth knowing",
            "",
            "Many are mirrors: `ReverseDNS` is \"The Orion.Nodes DNS value\".",
            "",
            "| Property | Type |",
        ]
        token_re = self.refs.entity_token_re({"Orion", "Cirrus"})
        subject = self.refs.table_subject(
            lines, 6, {"Cirrus.Nodes", "Orion.Nodes"}, {}, token_re
        )
        self.assertEqual(subject, "Cirrus.Nodes")

    def test_body_text_still_resolves_when_no_heading_names_an_entity(self):
        lines = [
            "## The recurrence",
            "",
            "### A cron expression without its timezone is ambiguous",
            "",
            "Six of the fourteen `Orion.Frequencies` columns are about time zones.",
            "",
            "| Property | Type |",
        ]
        token_re = self.refs.entity_token_re({"Orion"})
        subject = self.refs.table_subject(lines, 6, {"Orion.Frequencies"}, {}, token_re)
        self.assertEqual(subject, "Orion.Frequencies")

    def test_two_unrelated_entities_leave_the_table_unresolved(self):
        # Guessing would be worse than skipping: a wrong subject reports every row.
        lines = ["## Both", "", "`Orion.Nodes` and `Orion.Volumes` differ.", "", "| Property | Type |"]
        token_re = self.refs.entity_token_re({"Orion"})
        self.assertIsNone(
            self.refs.table_subject(lines, 4, {"Orion.Nodes", "Orion.Volumes"}, {}, token_re)
        )

    def test_a_fenced_signature_is_found_and_qualified(self):
        import check_signatures

        block = "Orion.Dependencies.RemoveDependencies(ids) -> number\n  Ignore dependencies.\n"
        m = check_signatures.FENCED_SIGNATURE_RE.search(block)
        self.assertEqual(m.group("entity"), "Orion.Dependencies")
        self.assertEqual(m.group("verb"), "RemoveDependencies")
        self.assertEqual(
            check_signatures.balanced_arguments(block, m.end("open") - 1), "ids"
        )


class TestGateSelfTest(unittest.TestCase):
    """The seeded errors must still be seedable, and must not be left in the tree.

    check_gate.py runs the checkers, so it is the slow part of the gate. These are the
    cheap halves of it: a seed anchored on text a page no longer contains tests nothing
    and would pass, and a mutation left behind would be a defect committed by the tool
    meant to prevent them.
    """

    @classmethod
    def setUpClass(cls):
        import check_gate

        cls.mod = check_gate

    def test_every_seed_still_matches_its_page(self):
        for label, rel, old, _new, _cmd in self.mod.CASES:
            with self.subTest(label):
                text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
                self.assertIn(old, text, f"{label}: seed no longer in {rel}")

    def test_no_mutation_is_left_in_the_tree(self):
        for label, rel, _old, new, _cmd in self.mod.CASES:
            with self.subTest(label):
                text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
                self.assertNotIn(new, text, f"{label}: mutation left in {rel}")

    def test_each_seed_actually_changes_the_page(self):
        for label, _rel, old, new, _cmd in self.mod.CASES:
            with self.subTest(label):
                self.assertNotEqual(old, new)


class TestOutputPairing(unittest.TestCase):
    """A command block pairs with the output block directly under it, and no further.

    Most documented commands are shown without their output. With a non-greedy ".*?" the
    command group ran forward from one of those until it found some later pair, swallowing
    every real command/output pair in between; the match then had a hundred-line
    "command", runnable() rejected it, and the whole span went unchecked in silence. That
    is the failure mode a checker must not have, because it reports success.
    """

    @classmethod
    def setUpClass(cls):
        import check_examples

        cls.mod = check_examples

    def test_a_command_without_output_does_not_swallow_the_next_pair(self):
        page = (
            "```bash\nfirst --no-output-shown\n```\n\n"
            "Prose between them.\n\n"
            "```bash\nsecond --has-output\n```\n\n"
            "```text\nthe real output\n```\n"
        )
        pairs = [
            (m.group("cmd").strip(), m.group("out").strip())
            for m in self.mod.PAIR_RE.finditer(page)
        ]
        self.assertEqual(pairs, [("second --has-output", "the real output")])

    def test_neither_group_spans_a_fence(self):
        page = (
            "```bash\ncmd --one\n```\n\n```text\nout one\n```\n\n"
            "```bash\ncmd --two\n```\n\n```text\nout two\n```\n"
        )
        pairs = [
            (m.group("cmd").strip(), m.group("out").strip())
            for m in self.mod.PAIR_RE.finditer(page)
        ]
        self.assertEqual(pairs, [("cmd --one", "out one"), ("cmd --two", "out two")])
        for cmd, out in pairs:
            self.assertNotIn("```", cmd)
            self.assertNotIn("```", out)

    def test_a_command_reading_stdin_gets_eof_rather_than_blocking(self):
        # validate_swql.py takes "-" for a query on standard input, and the guides document
        # it. Inheriting this process's stdin left the runner blocking on a terminal that
        # would never send anything, and the whole check died on the 180-second timeout.
        import subprocess
        import sys

        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "validate_swql.py"), "-"],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_an_elision_marker_allows_a_gap_but_a_missing_line_still_fails(self):
        actual = ["Verb.Name", "  returns: number", "  requires: admin"]
        ok, _ = self.mod.matches(["Verb.Name", "...", "  requires: admin"], actual)
        self.assertTrue(ok)
        # Without the marker the lines have to follow closely, which is what catches an
        # output block that quietly went stale.
        ok, _ = self.mod.matches(["Verb.Name", "  requires: nonesuch"], actual)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
