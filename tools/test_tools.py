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

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_reference_data
import diff_schema
import validate_swql
from schema_query import Schema

VERSION = "2026.2"
DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "schema", VERSION
)
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

    def test_templated_query_is_skipped(self):
        # The query the script sends is not the text on the page, so checking it would be
        # checking a string that never runs.
        found = self.extract('q = f"SELECT {col} FROM Orion.Nodes"\n', ".py")
        self.assertEqual(found, [])


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

    def test_real_signature_from_the_contract(self):
        verb = self.contract.resolve("SuppressAlerts", ["Orion.AlertSuppression"])
        names = [p["name"] for p in verb["parameters"]]
        self.assertEqual(names[:3], ["entityUris", "suppressFrom", "suppressUntil"])
        # The alerting guide states that only the first is required. Hold that claim here
        # too, since it is what makes the shorter published form safe to keep using.
        self.assertTrue(verb["parameters"][0]["required"])
        self.assertFalse(any(p["required"] for p in verb["parameters"][1:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
