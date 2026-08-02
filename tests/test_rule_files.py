"""Validation suite for Hujja rule files and the rule-file contract.

Runs on the standard library plus PyYAML and jsonschema:

    python -B -m unittest discover -s tests -p "test_*.py" -v

Two layers are checked. JSON Schema Draft 2020-12 covers local field shapes
and combinations. Everything JSON Schema cannot express -- referential
integrity, cross-object invariants, and the separations the contract exists to
protect -- is checked here in Python.

REQUIREMENT_MAP at the bottom of this module binds every required check
identifier to the test that implements it, and a meta-test fails the suite if
that binding is incomplete.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "hujja" / "schemas" / "rule-file.schema.json"
RULES_DIR = REPO_ROOT / "src" / "hujja" / "rules"
README_PATH = REPO_ROOT / "README.md"
TEST_PATH = Path(__file__).resolve()

PUBLIC_FILES = (
    SCHEMA_PATH,
    RULES_DIR / "djim_spdji.yaml",
    REPO_ROOT / "docs" / "rule-file-format.md",
    REPO_ROOT / "docs" / "fact-model.md",
    README_PATH,
    TEST_PATH,
)

VERIFICATION_LOG_REF = "README.md#source-verification-log"
README_ANCHOR = '<a id="source-verification-log"></a>'

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

# Formats are annotations by default, so a bare validator would accept an
# impossible calendar date such as 2026-02-31. The whole suite therefore shares
# one format-aware validator; no test may construct a bare one that bypasses it.
FORMAT_CHECKER = FormatChecker()
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FORMAT_CHECKER)

RULE_PATHS = sorted(RULES_DIR.glob("*.yaml"))
RULE_DOCS = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in RULE_PATHS}
DJIM = RULE_DOCS["djim_spdji"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def walk(node, path=()):
    """Yield (path, node) for every node in a loaded document."""
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, path + (index,))


def registry_ids(doc, key, subkey=None):
    entries = doc.get(key)
    if subkey is not None:
        entries = (entries or {}).get(subkey)
    if isinstance(entries, dict):
        return {entries["id"]} if "id" in entries else set()
    return {entry["id"] for entry in (entries or []) if isinstance(entry, dict) and "id" in entry}


def activity_ids(doc):
    screen = doc.get("business_activity_screen") or {}
    ids = set()
    for group in ("excluded_activities", "historical_activities"):
        ids |= {a["id"] for a in screen.get(group, [])}
    return ids


def all_declared_ids(doc):
    """Every declared object id, grouped by registry name."""
    screen = doc.get("business_activity_screen") or {}
    groups = {
        "editions": [e["id"] for e in doc["methodology"]["editions"]],
        "source_evidence": [e["id"] for e in doc["source_evidence"]],
        "provenance": [e["id"] for e in doc["provenance"]],
        "open_decisions": [e["id"] for e in doc["open_decisions"]],
        "required_inputs": [e["id"] for e in doc["required_inputs"]],
        "operands": [e["id"] for e in doc["operands"]],
        "cadences": [doc["cadences"]["index_review"]["id"], doc["cadences"]["evaluation_period"]["id"]],
        "ratio_screens": [s["id"] for s in doc["ratio_screens"]],
        "tolerance_tests": [s["id"] for s in screen.get("tolerance_tests", [])],
        "excluded_activities": [a["id"] for a in screen.get("excluded_activities", [])],
        "historical_activities": [a["id"] for a in screen.get("historical_activities", [])],
        "category_mappings": [m["id"] for m in screen.get("category_mappings", [])],
        "conditional_eligibility": [c["id"] for c in screen.get("conditional_eligibility", [])],
        "subcategories": [
            s["id"] for a in screen.get("excluded_activities", []) for s in a.get("subcategories", [])
        ],
        "methodology_change_record": [c["id"] for c in doc.get("methodology_change_record", [])],
        "purification_methods": [m["id"] for m in doc.get("purification_methods", [])],
        "contextual_claims": [
            claim["id"]
            for s in (list(doc["ratio_screens"]) + list(screen.get("tolerance_tests", [])))
            for claim in s.get("contextual_claims", [])
        ],
    }
    return groups


def typed_reference_targets(doc):
    """Map each reference field name to the set of ids it may legally resolve to."""
    provenance = registry_ids(doc, "provenance")
    editions = {e["id"] for e in doc["methodology"]["editions"]}
    inputs = registry_ids(doc, "required_inputs")
    changes = {c["id"] for c in doc.get("methodology_change_record", [])}
    return {
        "provenance_ref": provenance,
        "source_evidence_refs": registry_ids(doc, "source_evidence"),
        "open_decision_ref": registry_ids(doc, "open_decisions"),
        "edition_ref": editions,
        "edition_a": editions,
        "edition_b": editions,
        "source_editions": editions,
        "rule_basis_edition": editions,
        "numerator_ref": registry_ids(doc, "operands"),
        "denominator_ref": registry_ids(doc, "operands"),
        "operand_refs": registry_ids(doc, "operands"),
        "input_refs": inputs,
        "input_ref": inputs,
        "counter_input_ref": inputs,
        "state_input_ref": inputs,
        "depends_on_inputs": inputs,
        "period_ref": {doc["cadences"]["evaluation_period"]["id"]},
        "superseded_by_change_ref": changes,
        "activity_ref": activity_ids(doc),
        "applies_to_activity_ref": activity_ids(doc),
    }


def iter_references_in(subtree, targets):
    """Yield (path, field_name, referenced_id) for every reference inside a subtree."""
    for path, node in walk(subtree):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            field = "provenance_ref" if key.endswith("_provenance_ref") else key
            if field not in targets:
                continue
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                if isinstance(item, str):
                    yield path + (key,), field, item


def iter_references(doc):
    """Yield (path, field_name, referenced_id) for every reference in the document."""
    yield from iter_references_in(doc, typed_reference_targets(doc))


def prohibited_tokens():
    """Build prohibited search tokens at runtime from harmless fragments.

    No prohibited token is stored in this file as one contiguous literal.
    """
    marker = "A" + "2"
    return {
        "finding_id_prefix_a": marker + "A" + "-",
        "finding_id_prefix_b": marker + "B" + "-",
        "addendum_name": "adden" + "dum" + "-" + "a2",
        "hidden_review_dir": "." + "local",
        "source_backup_root": "hujja" + "-source" + "-backups",
        "brief_backup_root": "hujja" + "-brief" + "-backups",
        "private_review_path": "reviews" + "/" + "spdji",
        "consolidated_review_hash": (
            "bf8983e6e82e5f9e" + "ece419cf545f1d24" + "2d1c25c086add229" + "9c54de8c860ff7a6"
        ),
    }


def repository_cache_artifacts():
    """Bytecode caches inside the repository, ignoring the virtual environment.

    Scoped to what a test run can create. Distribution output under dist/ or
    build/ is deliberately out of scope: those directories are gitignored and
    may hold artifacts predating this suite, which no test may delete.
    """
    found = []
    for path in REPO_ROOT.rglob("*"):
        parts = path.parts
        if ".venv" in parts or ".git" in parts:
            continue
        if path.is_dir() and path.name == "__pycache__":
            found.append(str(path))
        elif path.is_file() and path.suffix == ".pyc":
            found.append(str(path))
    return sorted(found)


def immediate_transitions(doc):
    """Yield (path, immediate_transition object) for every screen in the document."""
    for path, node in walk(doc):
        if isinstance(node, dict) and "immediate_transition" in node:
            yield path + ("immediate_transition",), node["immediate_transition"]


def all_screens(doc):
    screen = doc.get("business_activity_screen") or {}
    return list(doc["ratio_screens"]) + list(screen.get("tolerance_tests", []))


# --------------------------------------------------------------------------
# Schema validation, identity and versions
# --------------------------------------------------------------------------

class TestSchemaAndIdentity(unittest.TestCase):

    def test_schema_document_is_valid(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_every_rule_file_validates(self):
        self.assertTrue(RULE_PATHS, "no rule files found")
        for name, doc in RULE_DOCS.items():
            with self.subTest(rule_file=name):
                errors = sorted(VALIDATOR.iter_errors(doc), key=lambda e: list(e.absolute_path))
                detail = "; ".join(
                    "/".join(str(p) for p in e.absolute_path) + " :: " + e.message for e in errors
                )
                self.assertEqual([], errors, detail)

    def test_schema_version_is_two_zero_zero(self):
        """P01"""
        self.assertEqual("2.0.0", SCHEMA["properties"]["schema_version"]["const"])
        for name, doc in RULE_DOCS.items():
            with self.subTest(rule_file=name):
                self.assertEqual("2.0.0", doc["schema_version"])

    def test_djim_rule_file_version(self):
        """P02"""
        self.assertEqual("1.1.0", DJIM["rule_file"]["version"])
        self.assertEqual("djim_spdji", DJIM["rule_file"]["id"])

    def test_review_status_remains_unreviewed(self):
        """P25"""
        for name, doc in RULE_DOCS.items():
            with self.subTest(rule_file=name):
                self.assertEqual("unreviewed", doc["review"]["status"])
                for field in ("reviewer", "scope", "date"):
                    self.assertIsNone(doc["review"][field])


# --------------------------------------------------------------------------
# Referential integrity
# --------------------------------------------------------------------------

class TestReferentialIntegrity(unittest.TestCase):

    def test_ids_are_unique(self):
        """P03"""
        for name, doc in RULE_DOCS.items():
            groups = all_declared_ids(doc)
            seen = {}
            for group, ids in groups.items():
                with self.subTest(rule_file=name, registry=group):
                    self.assertEqual(len(ids), len(set(ids)), f"duplicate id inside {group}")
                for identifier in ids:
                    with self.subTest(rule_file=name, identifier=identifier):
                        self.assertNotIn(
                            identifier, seen,
                            f"id {identifier!r} declared in both {seen.get(identifier)} and {group}",
                        )
                        seen[identifier] = group

    def test_every_reference_resolves_to_correct_type(self):
        """P04"""
        for name, doc in RULE_DOCS.items():
            targets = typed_reference_targets(doc)
            for path, field, value in iter_references(doc):
                with self.subTest(rule_file=name, path="/".join(str(p) for p in path), ref=value):
                    self.assertIn(
                        value, targets[field],
                        f"{field} {value!r} does not resolve to an object of the expected type",
                    )

    def _refs_of(self, doc, field_names):
        return [(path, field, value) for path, field, value in iter_references(doc) if field in field_names]

    def test_edition_references_resolve(self):
        """P05"""
        editions = {e["id"] for e in DJIM["methodology"]["editions"]}
        refs = self._refs_of(DJIM, {"edition_ref", "edition_a", "edition_b", "source_editions"})
        self.assertTrue(refs)
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, editions)

    def test_source_evidence_references_resolve(self):
        """P06"""
        declared = registry_ids(DJIM, "source_evidence")
        refs = self._refs_of(DJIM, {"source_evidence_refs"})
        self.assertTrue(refs)
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, declared)

    def test_provenance_references_resolve(self):
        """P07"""
        declared = registry_ids(DJIM, "provenance")
        refs = self._refs_of(DJIM, {"provenance_ref"})
        self.assertTrue(refs)
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, declared)

    def test_open_decision_references_resolve(self):
        """P08"""
        declared = registry_ids(DJIM, "open_decisions")
        refs = self._refs_of(DJIM, {"open_decision_ref"})
        self.assertTrue(refs)
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, declared)

    def test_operand_references_resolve(self):
        """P09"""
        declared = registry_ids(DJIM, "operands")
        refs = self._refs_of(DJIM, {"numerator_ref", "denominator_ref", "operand_refs"})
        self.assertTrue(refs)
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, declared)

    def test_input_references_resolve(self):
        """P10"""
        declared = registry_ids(DJIM, "required_inputs")
        refs = self._refs_of(
            DJIM, {"input_refs", "input_ref", "counter_input_ref", "state_input_ref", "depends_on_inputs"}
        )
        self.assertTrue(refs)
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, declared)

    def test_period_references_target_evaluation_period_only(self):
        """P11"""
        evaluation_id = DJIM["cadences"]["evaluation_period"]["id"]
        index_review_id = DJIM["cadences"]["index_review"]["id"]
        refs = self._refs_of(DJIM, {"period_ref"})
        self.assertTrue(refs, "no period references found")
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertEqual(evaluation_id, value)
                self.assertNotEqual(index_review_id, value)

    def test_change_references_target_non_operative_records(self):
        """P12"""
        records = {c["id"]: c for c in DJIM.get("methodology_change_record", [])}
        refs = self._refs_of(DJIM, {"superseded_by_change_ref"})
        self.assertTrue(refs, "no change references found")
        for path, _field, value in refs:
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIn(value, records)
                self.assertEqual("not_operative", records[value]["normative_use"])


# --------------------------------------------------------------------------
# The three documentary dimensions
# --------------------------------------------------------------------------

class TestDocumentaryModel(unittest.TestCase):

    def test_explicit_requires_public_source_evidence(self):
        """P13"""
        evidence = {e["id"]: e for e in DJIM["source_evidence"]}
        for entry in DJIM["provenance"]:
            if entry["documentary_resolution"] not in {"explicit", "partially_supported"}:
                continue
            with self.subTest(provenance=entry["id"]):
                refs = entry.get("source_evidence_refs") or []
                self.assertTrue(refs, "resolution asserts source support but names no evidence")
                for ref in refs:
                    self.assertIn(ref, evidence)
                    self.assertEqual(VERIFICATION_LOG_REF, evidence[ref]["verification_log_ref"])
                    self.assertTrue(evidence[ref]["locator"].strip())

    def test_consistency_is_not_inferred_from_resolution(self):
        """P14"""
        by_resolution = {}
        for entry in DJIM["provenance"]:
            by_resolution.setdefault(entry["documentary_resolution"], set()).add(
                entry["source_consistency"]["state"]
            )
        self.assertIn("explicit", by_resolution)
        for resolution, states in by_resolution.items():
            with self.subTest(resolution=resolution):
                self.assertNotIn(
                    "consistent", states,
                    "no consistency assessment is supported by the declared reviewed evidence set",
                )
        self.assertEqual(
            {"not_assessed", "inconsistent"}, by_resolution["explicit"],
            "explicit resolution must not imply a single consistency state",
        )

    def test_consistency_defaults_to_not_assessed(self):
        """P15"""
        assessed = [
            e["id"] for e in DJIM["provenance"] if e["source_consistency"]["state"] != "not_assessed"
        ]
        self.assertEqual(["pv_change_record_immediate_reentry"], assessed)
        for entry in DJIM["provenance"]:
            if entry["id"] in assessed:
                continue
            with self.subTest(provenance=entry["id"]):
                self.assertEqual("not_assessed", entry["source_consistency"]["state"])
                self.assertIsNone(entry["source_consistency"]["scope"])

    def test_scoped_inconsistency_is_bound_to_the_change_record(self):
        """P16"""
        entry = next(e for e in DJIM["provenance"] if e["id"] == "pv_change_record_immediate_reentry")
        self.assertEqual("explicit", entry["documentary_resolution"])
        self.assertEqual("inconsistent", entry["source_consistency"]["state"])
        scope = entry["source_consistency"]["scope"]
        self.assertIsInstance(scope, str)
        self.assertIn("entry", scope.lower())
        self.assertIn("does not extend to the complete", scope.lower())
        referenced_by = [
            c["id"] for c in DJIM["methodology_change_record"] if c["provenance_ref"] == entry["id"]
        ]
        self.assertEqual(["chg_immediate_reentry_replaced"], referenced_by)
        for record in DJIM["methodology_change_record"]:
            self.assertEqual("not_operative", record["normative_use"])

    def test_inherited_content_is_preserved_and_unresolved(self):
        """P45"""
        inherited = [e for e in DJIM["provenance"] if e.get("inherited_from_tracked_rule_file")]
        self.assertTrue(inherited, "no inherited-content provenance declared")
        for entry in inherited:
            with self.subTest(provenance=entry["id"]):
                self.assertEqual("unresolved", entry["documentary_resolution"])
                self.assertNotIn("source_evidence_refs", entry)
                self.assertIn("tracked rule-file content", entry["scope_limit"])
        inherited_ids = {e["id"] for e in inherited}
        # The inherited values themselves are still present and computable.
        operands = {o["id"]: o for o in DJIM["operands"]}
        self.assertIn(
            operands["op_interest_bearing_debt"]["documentary_basis_provenance_ref"], inherited_ids
        )
        self.assertEqual(
            ["in_total_interest_bearing_debt"],
            operands["op_interest_bearing_debt"]["computation"]["input_refs"],
        )
        activities = {a["id"] for a in DJIM["business_activity_screen"]["excluded_activities"]}
        for expected in (
            "act_alcohol",
            "act_tobacco_ecigarettes",
            "act_recreational_cannabis",
            "act_conventional_financial_services",
        ):
            self.assertIn(expected, activities)

    def test_no_verdict_policy_key_or_value(self):
        """P39"""
        prohibited_keys = {
            "on_missing",
            "if_absent",
            "fallback",
            "default_status",
            "default_verdict",
            "missing_input_behaviour",
            "review_required",
        }
        prohibited_values = ("DOUBTFUL", "NON_COMPLIANT", "COMPLIANT")
        for name, doc in RULE_DOCS.items():
            for path, node in walk(doc):
                if isinstance(node, dict):
                    for key in node:
                        with self.subTest(rule_file=name, key=key):
                            self.assertNotIn(key, prohibited_keys)
                if isinstance(node, str):
                    for token in prohibited_values:
                        with self.subTest(rule_file=name, token=token):
                            self.assertNotIn(token, node)


# --------------------------------------------------------------------------
# Data origin
# --------------------------------------------------------------------------

class TestDataOrigin(unittest.TestCase):

    def test_data_origin_only_on_runtime_inputs(self):
        """P17"""
        for name, doc in RULE_DOCS.items():
            occurrences = [
                path for path, node in walk(doc)
                if isinstance(node, dict) and "data_origin" in node
            ]
            self.assertTrue(occurrences)
            for path in occurrences:
                with self.subTest(rule_file=name, path="/".join(str(p) for p in path)):
                    self.assertEqual("required_inputs", path[0])
                    self.assertEqual(2, len(path), "data_origin must sit directly on an input entry")

    def test_semantic_source_and_channel_are_separate(self):
        """P18"""
        pairs = set()
        for entry in DJIM["required_inputs"]:
            origin = entry["data_origin"]
            with self.subTest(input=entry["id"]):
                self.assertIn("semantic_source", origin)
                self.assertIn("supplied_via", origin)
                self.assertNotEqual(origin["semantic_source"], origin["supplied_via"])
                if origin["supplied_via"] == "unresolved":
                    self.assertIn("open_decision_ref", origin)
            pairs.add((origin["semantic_source"], origin["supplied_via"]))
        sources = {s for s, _ in pairs}
        channels = {c for _, c in pairs}
        self.assertGreater(len(sources), 1)
        self.assertGreater(len(channels), 1)
        self.assertNotIn(
            "methodology_defined", sources,
            "methodology constants are justified by provenance, not delivered as runtime data",
        )

    def test_supplied_via_basis_is_absent(self):
        """P19"""
        needle = "supplied_via_basis"
        self.assertNotIn(needle, SCHEMA_PATH.read_text(encoding="utf-8"))
        for name, doc in RULE_DOCS.items():
            for path, node in walk(doc):
                if isinstance(node, dict):
                    with self.subTest(rule_file=name, path="/".join(str(p) for p in path)):
                        self.assertNotIn(needle, node)

    def test_execution_readiness_is_absent(self):
        """P20"""
        needle = "execution_readiness"
        for target in (SCHEMA_PATH, RULES_DIR / "djim_spdji.yaml"):
            with self.subTest(file=target.name):
                self.assertNotIn(needle, target.read_text(encoding="utf-8"))
        for name, doc in RULE_DOCS.items():
            for path, node in walk(doc):
                if isinstance(node, dict):
                    with self.subTest(rule_file=name, path="/".join(str(p) for p in path)):
                        self.assertNotIn(needle, node)


# --------------------------------------------------------------------------
# Editions, URL neutralization, README boundary
# --------------------------------------------------------------------------

class TestEditionsAndEvidenceBoundary(unittest.TestCase):

    def test_rule_basis_edition_resolves(self):
        """P22"""
        for name, doc in RULE_DOCS.items():
            with self.subTest(rule_file=name):
                editions = {e["id"]: e for e in doc["methodology"]["editions"]}
                basis = doc["methodology"]["rule_basis_edition"]
                self.assertIn(basis, editions)
                self.assertEqual("rule_basis", editions[basis]["role"])
                roles = [e["role"] for e in editions.values()]
                self.assertEqual(1, roles.count("rule_basis"))

    def test_no_active_edition_field(self):
        """P23"""
        needle = "active_edition"
        self.assertNotIn(needle, SCHEMA_PATH.read_text(encoding="utf-8"))
        for name, doc in RULE_DOCS.items():
            for path, node in walk(doc):
                if isinstance(node, dict):
                    with self.subTest(rule_file=name, path="/".join(str(p) for p in path)):
                        self.assertNotIn(needle, node)

    def test_inherited_url_is_not_an_edition_identifier(self):
        """P24"""
        provenance = {e["id"]: e for e in DJIM["provenance"]}
        seen = 0
        for edition in DJIM["methodology"]["editions"]:
            url = edition["official_url"]
            if url is None:
                continue
            seen += 1
            with self.subTest(edition=edition["id"]):
                self.assertEqual("inherited_from_tracked_rule_file", url["origin"])
                self.assertEqual("unresolved", url["edition_specificity"])
                self.assertEqual("unverified", url["verification_status"])
                self.assertIn(url["provenance_ref"], provenance)
                self.assertEqual(
                    "unresolved", provenance[url["provenance_ref"]]["documentary_resolution"]
                )
                self.assertNotEqual(url["value"], edition["id"])
                self.assertNotEqual(url["value"], edition["label"])
        self.assertEqual(1, seen, "expected exactly one inherited URL")
        # No source-evidence locator may be a URL standing in for an edition.
        for entry in DJIM["source_evidence"]:
            with self.subTest(source_evidence=entry["id"]):
                self.assertNotIn("http", entry["locator"].lower())

    def test_readme_anchor_exists(self):
        """P47"""
        readme = README_PATH.read_text(encoding="utf-8")
        self.assertIn(README_ANCHOR, readme)
        self.assertLess(
            readme.index(README_ANCHOR), readme.index("| Source | Version encoded |"),
            "the anchor must sit immediately before the public log table",
        )

    def test_source_evidence_uses_the_stable_boundary(self):
        """P48"""
        for name, doc in RULE_DOCS.items():
            self.assertTrue(doc["source_evidence"])
            for entry in doc["source_evidence"]:
                with self.subTest(rule_file=name, source_evidence=entry["id"]):
                    self.assertEqual(VERIFICATION_LOG_REF, entry["verification_log_ref"])


# --------------------------------------------------------------------------
# Cadence separation
# --------------------------------------------------------------------------

class TestCadenceSeparation(unittest.TestCase):

    def test_review_and_evaluation_period_are_separate_objects(self):
        """P26"""
        cadences = DJIM["cadences"]
        review = cadences["index_review"]
        period = cadences["evaluation_period"]
        self.assertNotEqual(review["id"], period["id"])
        self.assertEqual("index_composition", review["applies_to"])
        self.assertEqual(set(), set(review) & {"duration", "schedule", "mapping_to_index_review"})
        self.assertEqual(set(), set(period) & {"frequency", "months", "applies_to"})
        self.assertEqual("quarterly", review["frequency"])
        self.assertEqual([3, 6, 9, 12], review["months"])

    def test_no_cadence_token_under_evaluation_period(self):
        """P27"""
        tokens = {"quarterly", "monthly", "annual", "semi_annual", "weekly", "daily"}
        period = DJIM["cadences"]["evaluation_period"]
        for field in ("duration", "schedule"):
            with self.subTest(field=field):
                self.assertIsNone(period[field])
                for _path, node in walk(period[field]):
                    self.assertNotIsInstance(node, str)
        for _path, node in walk(period):
            if isinstance(node, str):
                with self.subTest(value=node):
                    self.assertNotIn(node.lower(), tokens)

    def test_evaluation_to_review_mapping_not_established(self):
        """P28"""
        mapping = DJIM["cadences"]["evaluation_period"]["mapping_to_index_review"]
        self.assertEqual("not_established", mapping["status"])
        provenance = {e["id"]: e for e in DJIM["provenance"]}
        self.assertEqual("unresolved", provenance[mapping["provenance_ref"]]["documentary_resolution"])
        self.assertIn("open_decision_ref", mapping)


# --------------------------------------------------------------------------
# Operands
# --------------------------------------------------------------------------

class TestOperands(unittest.TestCase):

    def test_sampling_interval_remains_unresolved(self):
        """P29"""
        provenance = {e["id"]: e for e in DJIM["provenance"]}
        windows = [
            node["computation"]["averaging_window"]
            for node in DJIM["operands"]
            if "averaging_window" in node["computation"]
        ]
        self.assertEqual(1, len(windows))
        window = windows[0]
        self.assertEqual(24, window["length"])
        self.assertEqual("months", window["unit"])
        self.assertEqual("trailing_average", window["method"])
        self.assertEqual("explicit", provenance[window["provenance_ref"]]["documentary_resolution"])
        sampling = window["sampling"]
        self.assertIsNone(sampling["interval"])
        self.assertEqual("unresolved", provenance[sampling["provenance_ref"]]["documentary_resolution"])
        self.assertIn("open_decision_ref", sampling)
        self.assertNotEqual(window["provenance_ref"], sampling["provenance_ref"])

    def test_labels_from_different_editions_are_not_aliased(self):
        """P30"""
        for operand in DJIM["operands"]:
            labels = operand["documentary_labels"] or []
            editions = {label["edition_ref"] for label in labels}
            equivalences = operand["equivalence_across_editions"] or []
            established = {
                frozenset({eq["edition_a"], eq["edition_b"]})
                for eq in equivalences
                if eq["status"] == "established"
            }
            with self.subTest(operand=operand["id"]):
                if len(editions) > 1:
                    for pair in ((a, b) for a in editions for b in editions if a < b):
                        self.assertIn(
                            frozenset(pair), established,
                            "labels from two editions require an established equivalence record",
                        )
                for eq in equivalences:
                    if eq["status"] == "not_established":
                        self.assertNotEqual(eq["edition_a_label"], eq["edition_b_label"])


# --------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------

class TestTransitions(unittest.TestCase):

    def setUp(self):
        self.screen = next(s for s in DJIM["ratio_screens"] if s["id"] == "scr_djim_leverage")
        self.transitions = self.screen["status_transitions"]
        self.provenance = {e["id"]: e for e in DJIM["provenance"]}
        self.records = {c["id"]: c for c in DJIM.get("methodology_change_record", [])}

    def test_directions_are_independently_represented(self):
        """P31"""
        forward = self.transitions["from_compliant_to_non_compliant"]
        reverse = self.transitions["from_non_compliant_to_compliant"]
        self.assertNotEqual(set(forward), set(reverse))
        self.assertIn("tolerance_band", forward)
        self.assertNotIn("tolerance_band", reverse)
        self.assertEqual(0.02, forward["tolerance_band"]["width"])
        self.assertEqual("same_as_threshold", forward["tolerance_band"]["unit"])
        self.assertTrue(forward["within_band"]["status_retained"])
        self.assertEqual(3, forward["within_band"]["trigger"]["required_consecutive_periods"])
        self.assertEqual(3, reverse["requires"]["required_consecutive_periods"])
        self.assertEqual("ordinary_threshold", reverse["requires"]["test"])
        self.assertNotEqual(
            forward["within_band"]["trigger"]["counter_input_ref"],
            reverse["requires"]["counter_input_ref"],
        )
        self.assertEqual("present", forward["beyond_band"]["immediate_transition"]["availability"])
        self.assertEqual("absent", reverse["immediate_transition"]["availability"])

    def test_availability_vocabulary_is_operational_only(self):
        """P32"""
        allowed = {"present", "absent", "not_established"}
        documentary = {"explicit", "partially_supported", "unresolved", "not_found_after_targeted_review"}
        found = 0
        for path, transition in immediate_transitions(DJIM):
            found += 1
            with self.subTest(path="/".join(str(p) for p in path)):
                self.assertIsInstance(transition, dict)
                self.assertIn(transition["availability"], allowed)
                self.assertNotIn(transition["availability"], documentary)
        self.assertEqual(2, found)
        self.assertEqual(
            allowed,
            set(SCHEMA["$defs"]["immediateTransition"]["properties"]["availability"]["enum"]),
        )

    def test_transition_invariants(self):
        """P33"""
        for path, transition in immediate_transitions(DJIM):
            label = "/".join(str(p) for p in path)
            availability = transition["availability"]
            provenance = self.provenance[transition["provenance_ref"]]

            with self.subTest(invariant="1-present-carries-no-supersession", path=label):
                if availability == "present":
                    self.assertNotIn("superseded_by_change_ref", transition)

            with self.subTest(invariant="2-present-has-explicit-provenance", path=label):
                if availability == "present":
                    self.assertEqual("explicit", provenance["documentary_resolution"])

            with self.subTest(invariant="3-absent-requires-basis", path=label):
                if availability == "absent":
                    self.assertIn(transition["absence_basis"], {"superseded", "documented_absent"})

            with self.subTest(invariant="4-superseded-requires-change-ref", path=label):
                if availability == "absent" and transition.get("absence_basis") == "superseded":
                    self.assertIn("superseded_by_change_ref", transition)

            with self.subTest(invariant="5-change-ref-is-non-operative", path=label):
                ref = transition.get("superseded_by_change_ref")
                if ref is not None:
                    self.assertEqual("not_operative", self.records[ref]["normative_use"])

            with self.subTest(invariant="6-absent-has-affirmative-provenance", path=label):
                if availability == "absent":
                    self.assertEqual("explicit", provenance["documentary_resolution"])

            with self.subTest(invariant="7-not-established-carries-no-supersession", path=label):
                if availability == "not_established":
                    self.assertNotIn("superseded_by_change_ref", transition)
                    self.assertNotIn("absence_basis", transition)

            with self.subTest(invariant="8-unresolved-never-forces-absent", path=label):
                if provenance["documentary_resolution"] != "explicit":
                    self.assertNotEqual("absent", availability)

            with self.subTest(invariant="9-consistency-does-not-drive-availability", path=label):
                states = {
                    p["source_consistency"]["state"]
                    for p in self.provenance.values()
                    if p["documentary_resolution"] == "explicit"
                }
                self.assertGreater(len(states), 1)
                self.assertIn(availability, {"present", "absent", "not_established"})

            with self.subTest(invariant="12-references-resolve", path=label):
                self.assertIn(transition["provenance_ref"], self.provenance)
                if transition.get("superseded_by_change_ref") is not None:
                    self.assertIn(transition["superseded_by_change_ref"], self.records)

        with self.subTest(invariant="10-superseded-route-not-executable"):
            for record in self.records.values():
                self.assertEqual("not_operative", record["normative_use"])

        with self.subTest(invariant="11-change-records-reached-only-by-supersession"):
            for path, field, value in iter_references(DJIM):
                if value in self.records:
                    self.assertEqual(
                        "superseded_by_change_ref", path[-1],
                        f"change record reached through {path[-1]!r} at {'/'.join(str(p) for p in path)}",
                    )

    def test_historical_records_are_non_operative(self):
        """P34"""
        self.assertTrue(self.records)
        for record in self.records.values():
            with self.subTest(record=record["id"]):
                self.assertEqual("not_operative", record["normative_use"])
                self.assertEqual("2023-09-15", record["effective_date"])
                self.assertEqual("after_close", record["effective_moment"])
        for activity in DJIM["business_activity_screen"].get("historical_activities", []):
            with self.subTest(activity=activity["id"]):
                self.assertEqual("not_operative", activity["normative_use"])

    def test_no_historical_route_is_executable(self):
        """P35"""
        historical_ids = set(self.records) | {
            a["id"] for a in DJIM["business_activity_screen"].get("historical_activities", [])
        }
        targets = typed_reference_targets(DJIM)
        for screen in all_screens(DJIM):
            for path, field, value in iter_references_in(screen, targets):
                if value in historical_ids:
                    with self.subTest(screen=screen["id"], path="/".join(str(p) for p in path)):
                        self.assertEqual("superseded_by_change_ref", path[-1])
        # A historical activity is never listed among the operative exclusions.
        operative = {a["id"] for a in DJIM["business_activity_screen"]["excluded_activities"]}
        self.assertEqual(set(), operative & historical_ids)


# --------------------------------------------------------------------------
# Conditional eligibility
# --------------------------------------------------------------------------

class TestConditionalEligibility(unittest.TestCase):

    def setUp(self):
        self.conditions = DJIM["business_activity_screen"].get("conditional_eligibility", [])

    def test_incomplete_specifications_carry_no_logic(self):
        """P36"""
        self.assertTrue(self.conditions)
        incomplete = 0
        for condition in self.conditions:
            spec = condition["condition_specification"]
            if spec["completeness"] != "incomplete":
                continue
            incomplete += 1
            with self.subTest(condition=condition["id"]):
                self.assertIsNone(spec["logic"])
                self.assertIsNone(spec["clauses"])
                self.assertEqual("overrides_exclusion", condition["effect"])
        self.assertEqual(1, incomplete)

    def test_complete_specifications_require_a_clause(self):
        """P37"""
        for condition in self.conditions:
            spec = condition["condition_specification"]
            if spec["completeness"] != "complete":
                continue
            with self.subTest(condition=condition["id"]):
                self.assertIn(spec["logic"], {"all_of", "any_of"})
                self.assertIsInstance(spec["clauses"], list)
                self.assertGreaterEqual(len(spec["clauses"]), 1)
        complete_branch = SCHEMA["$defs"]["conditionSpecification"]["allOf"][1]["then"]["properties"]
        self.assertEqual(1, complete_branch["clauses"]["minItems"])
        self.assertEqual(["all_of", "any_of"], complete_branch["logic"]["enum"])

    def test_no_empty_condition_list(self):
        """P38"""
        for name, doc in RULE_DOCS.items():
            for path, node in walk(doc):
                if isinstance(node, dict) and "clauses" in node:
                    with self.subTest(rule_file=name, path="/".join(str(p) for p in path)):
                        self.assertNotEqual([], node["clauses"])
                        if node["clauses"] is None:
                            self.assertIsNone(node["logic"])
        incomplete_branch = SCHEMA["$defs"]["conditionSpecification"]["allOf"][0]["then"]["properties"]
        self.assertEqual("null", incomplete_branch["clauses"]["type"])
        self.assertEqual("null", incomplete_branch["logic"]["type"])


# --------------------------------------------------------------------------
# External classification input
# --------------------------------------------------------------------------

class TestExternalClassification(unittest.TestCase):

    def setUp(self):
        self.entry = next(
            e for e in DJIM["required_inputs"] if e["kind"] == "external_classification_assignment"
        )
        self.provenance = {e["id"]: e for e in DJIM["provenance"]}

    def test_scheme_identifier_remains_unresolved(self):
        """P40"""
        self.assertIsNone(self.entry["scheme"]["identifier"])
        self.assertEqual(
            "unresolved",
            self.provenance[self.entry["scheme"]["provenance_ref"]]["documentary_resolution"],
        )
        self.assertEqual("entity", self.entry["assignment_subject"])
        self.assertEqual("proprietary_external", self.entry["data_origin"]["semantic_source"])
        self.assertEqual("unresolved", self.entry["data_origin"]["supplied_via"])

    def test_observed_codes_are_non_exhaustive(self):
        """P41"""
        codes = self.entry["observed_codes"]
        self.assertFalse(codes["exhaustive"])
        self.assertEqual(
            "unresolved",
            self.provenance[codes["exhaustiveness_provenance_ref"]]["documentary_resolution"],
        )
        self.assertEqual(["8000", "8600"], [v["code"] for v in codes["values"]])
        refs = {v["provenance_ref"] for v in codes["values"]}
        self.assertEqual(2, len(refs), "each observed code carries its own provenance")

    def test_documentary_cardinality_remains_unresolved(self):
        """P42"""
        cardinality = self.entry["documentary_cardinality"]
        self.assertEqual("unresolved", cardinality["status"])
        self.assertEqual(
            "unresolved",
            self.provenance[cardinality["provenance_ref"]]["documentary_resolution"],
        )
        self.assertNotIn(
            "established",
            SCHEMA["$defs"]["documentaryCardinality"]["properties"]["status"]["enum"][1:],
        )

    def test_adapter_assignment_shape_remains_open(self):
        """P43"""
        contract = self.entry["adapter_contract"]
        self.assertEqual("open", contract["assignment_shape"])
        self.assertIn(contract["open_decision_ref"], registry_ids(DJIM, "open_decisions"))
        self.assertNotEqual(
            contract["open_decision_ref"], self.entry["data_origin"]["open_decision_ref"],
            "adapter shape and delivery channel are separate open decisions",
        )

    def test_no_unsourced_cardinality_assertion(self):
        """P44"""
        needle = "exactly_one_per_entity"
        for target in (SCHEMA_PATH, RULES_DIR / "djim_spdji.yaml"):
            with self.subTest(file=target.name):
                self.assertNotIn(needle, target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Purification container
# --------------------------------------------------------------------------

class TestPurification(unittest.TestCase):

    def test_purification_container_is_plural_and_empty(self):
        """P46"""
        definition = SCHEMA["properties"]["purification_methods"]
        self.assertEqual("array", definition["type"])
        self.assertIn("method_kind", SCHEMA["$defs"]["purificationMethod"]["properties"])
        self.assertGreaterEqual(
            len(SCHEMA["$defs"]["purificationMethod"]["properties"]["method_kind"]["enum"]), 2
        )
        self.assertEqual([], DJIM["purification_methods"], "no purification method is encoded")


# --------------------------------------------------------------------------
# Public-file hygiene
# --------------------------------------------------------------------------

class TestPublicFileHygiene(unittest.TestCase):

    def test_no_private_review_material_in_public_files(self):
        """P21"""
        tokens = prohibited_tokens()
        for path in PUBLIC_FILES:
            text = path.read_text(encoding="utf-8").lower()
            for label, token in tokens.items():
                with self.subTest(file=path.name, token=label):
                    self.assertNotIn(token.lower(), text)

    def test_no_new_cache_or_temporary_test_artifact(self):
        """P49"""
        self.assertEqual(
            [], repository_cache_artifacts(),
            "the suite must leave no bytecode cache inside the repository",
        )
        strays = sorted(
            str(p) for pattern in ("*.tmp", "*.out", "*.log", "test_output*", "validation_*")
            for p in REPO_ROOT.glob(pattern)
        )
        self.assertEqual([], strays, "the suite must leave no temporary artifact in the repository")
        for path in PUBLIC_FILES:
            with self.subTest(file=path.name):
                self.assertTrue(path.is_file())


# --------------------------------------------------------------------------
# Negative schema tests
# --------------------------------------------------------------------------

class TestNegativeSchema(unittest.TestCase):

    def base(self):
        return copy.deepcopy(DJIM)

    def assertRejected(self, doc, label):
        errors = list(VALIDATOR.iter_errors(doc))
        self.assertTrue(errors, f"{label}: expected the schema to reject this document")

    def leverage(self, doc):
        return next(s for s in doc["ratio_screens"] if s["id"] == "scr_djim_leverage")

    def reverse_transition(self, doc):
        return self.leverage(doc)["status_transitions"]["from_non_compliant_to_compliant"][
            "immediate_transition"
        ]

    def forward_transition(self, doc):
        return self.leverage(doc)["status_transitions"]["from_compliant_to_non_compliant"][
            "beyond_band"
        ]["immediate_transition"]

    def condition_spec(self, doc):
        return doc["business_activity_screen"]["conditional_eligibility"][0]["condition_specification"]

    def test_legacy_evaluation_frequency_rejected(self):
        """N01"""
        doc = self.base()
        self.leverage(doc)["evaluation_frequency"] = None
        self.assertRejected(doc, "legacy evaluation_frequency")

    def test_legacy_transition_buffer_rejected(self):
        """N02"""
        doc = self.base()
        self.leverage(doc)["transition_buffer"] = {
            "tolerance_band": 0.02,
            "consecutive_periods_before_flip": 3,
            "immediate_breach_beyond_band": True,
        }
        self.assertRejected(doc, "legacy transition_buffer")

    def test_missing_provenance_registry_rejected(self):
        """N03"""
        doc = self.base()
        del doc["provenance"]
        self.assertRejected(doc, "missing provenance registry")

    def test_boolean_immediate_transition_rejected(self):
        """N04"""
        doc = self.base()
        self.leverage(doc)["status_transitions"]["from_compliant_to_non_compliant"]["beyond_band"][
            "immediate_transition"
        ] = True
        self.assertRejected(doc, "boolean immediate transition")

    def test_present_with_supersession_rejected(self):
        """N05"""
        doc = self.base()
        self.forward_transition(doc)["superseded_by_change_ref"] = "chg_immediate_reentry_replaced"
        self.assertRejected(doc, "present availability carrying a supersession reference")

    def test_absent_without_basis_rejected(self):
        """N06"""
        doc = self.base()
        transition = self.reverse_transition(doc)
        del transition["absence_basis"]
        del transition["superseded_by_change_ref"]
        self.assertRejected(doc, "absent availability without an absence basis")

    def test_superseded_without_change_reference_rejected(self):
        """N07"""
        doc = self.base()
        del self.reverse_transition(doc)["superseded_by_change_ref"]
        self.assertRejected(doc, "superseded absence without a change reference")

    def test_not_established_with_supersession_rejected(self):
        """N08"""
        doc = self.base()
        transition = self.reverse_transition(doc)
        transition["availability"] = "not_established"
        del transition["absence_basis"]
        self.assertRejected(doc, "not_established availability carrying a supersession reference")

    def test_incomplete_with_empty_clause_list_rejected(self):
        """N09"""
        doc = self.base()
        self.condition_spec(doc)["clauses"] = []
        self.assertRejected(doc, "incomplete specification with an empty clause list")

    def test_incomplete_with_logic_rejected(self):
        """N10"""
        doc = self.base()
        self.condition_spec(doc)["logic"] = "all_of"
        self.assertRejected(doc, "incomplete specification carrying executable logic")

    def test_complete_with_empty_clause_list_rejected(self):
        """N11"""
        doc = self.base()
        spec = self.condition_spec(doc)
        spec["completeness"] = "complete"
        spec["logic"] = "all_of"
        spec["clauses"] = []
        self.assertRejected(doc, "complete specification with an empty clause list")

    def test_complete_without_logic_rejected(self):
        """N12"""
        doc = self.base()
        spec = self.condition_spec(doc)
        spec["completeness"] = "complete"
        spec["clauses"] = [
            {
                "id": "clause_example",
                "input_ref": "in_classification_assignment",
                "operator": "equals",
                "value": "8600",
                "provenance_ref": "pv_code_8600",
            }
        ]
        self.assertRejected(doc, "complete specification without logic")

    def test_unsourced_cardinality_key_rejected(self):
        """N13"""
        doc = self.base()
        entry = next(
            e for e in doc["required_inputs"] if e["kind"] == "external_classification_assignment"
        )
        entry["cardinality"] = "exactly_one_per_entity"
        self.assertRejected(doc, "unsourced cardinality assertion")

    def test_supplied_via_basis_rejected(self):
        """N14"""
        doc = self.base()
        doc["required_inputs"][0]["data_origin"]["supplied_via_basis"] = "project_constraint"
        self.assertRejected(doc, "supplied_via_basis")

    def test_execution_readiness_rejected(self):
        """N15"""
        doc = self.base()
        self.leverage(doc)["execution_readiness"] = {"status": "specification_complete"}
        self.assertRejected(doc, "execution_readiness")

    def test_explicit_without_source_evidence_rejected(self):
        """N16"""
        doc = self.base()
        entry = next(e for e in doc["provenance"] if e["documentary_resolution"] == "unresolved")
        entry["documentary_resolution"] = "explicit"
        entry.pop("source_evidence_refs", None)
        entry.pop("inherited_from_tracked_rule_file", None)
        self.assertRejected(doc, "explicit resolution without public source evidence")

    def test_unknown_policy_keys_rejected(self):
        """N17"""
        for key, value in (("default_verdict", "DOUBTFUL"), ("on_missing", "DOUBTFUL")):
            with self.subTest(policy_key=key):
                doc = self.base()
                self.leverage(doc)[key] = value
                self.assertRejected(doc, f"policy key {key}")


# --------------------------------------------------------------------------
# Corrective pass 2A hardening
# --------------------------------------------------------------------------

class TestCorrectiveHardening(unittest.TestCase):
    """Regression cover for the four findings raised in human diff review."""

    def base(self):
        return copy.deepcopy(DJIM)

    def assertRejected(self, doc, label):
        errors = list(VALIDATOR.iter_errors(doc))
        self.assertTrue(errors, f"{label}: expected the schema to reject this document")

    def assertAccepted(self, doc, label):
        errors = sorted(VALIDATOR.iter_errors(doc), key=lambda e: list(e.absolute_path))
        detail = "; ".join(
            "/".join(str(p) for p in e.absolute_path) + " :: " + e.message for e in errors
        )
        self.assertEqual([], errors, f"{label}: expected acceptance, got {detail}")

    def leverage(self, doc):
        return next(s for s in doc["ratio_screens"] if s["id"] == "scr_djim_leverage")

    def reverse_transition(self, doc):
        return self.leverage(doc)["status_transitions"]["from_non_compliant_to_compliant"][
            "immediate_transition"
        ]

    def expert_reviewed_doc(self, date):
        doc = self.base()
        doc["review"] = {
            "status": "expert_reviewed",
            "reviewer": "A. Reviewer",
            "scope": "rule file v1.1.0 checked against official source",
            "date": date,
        }
        return doc

    # ---- C01 / C02: closed review-status states ---------------------------

    def test_unreviewed_metadata_is_all_null(self):
        """C01"""
        for name, doc in RULE_DOCS.items():
            review = doc["review"]
            with self.subTest(rule_file=name):
                self.assertEqual("unreviewed", review["status"])
                for field in ("reviewer", "scope", "date"):
                    with self.subTest(field=field):
                        self.assertIsNone(review[field])

    def test_unreviewed_rejects_non_null_metadata(self):
        """C02"""
        for field, value in (
            ("reviewer", "A. Reviewer"),
            ("scope", "rule file v1.1.0 checked against official source"),
            ("date", "2026-08-02"),
        ):
            with self.subTest(unreviewed_with=field):
                doc = self.base()
                doc["review"][field] = value
                self.assertRejected(doc, f"unreviewed with non-null {field}")

        with self.subTest(case="expert_reviewed_complete_is_accepted"):
            doc = self.base()
            doc["review"] = {
                "status": "expert_reviewed",
                "reviewer": "A. Reviewer",
                "scope": "rule file v1.1.0 checked against official source",
                "date": "2026-08-02",
            }
            self.assertAccepted(doc, "complete expert_reviewed metadata")

        for field in ("reviewer", "scope", "date"):
            with self.subTest(expert_reviewed_missing=field):
                doc = self.base()
                doc["review"] = {
                    "status": "expert_reviewed",
                    "reviewer": "A. Reviewer",
                    "scope": "rule file v1.1.0 checked against official source",
                    "date": "2026-08-02",
                }
                doc["review"][field] = None
                self.assertRejected(doc, f"expert_reviewed with null {field}")

        # A real calendar date, not merely a YYYY-MM-DD-shaped string. The
        # pattern alone would accept 2026-02-31; `format: date` is what rejects it.
        for date, accepted in (
            ("2026-08-02", True),
            ("2028-02-29", True),      # 2028 is a leap year
            ("August 2026", False),    # wrong lexical shape
            ("2026-02-31", False),     # right shape, impossible day
            ("2026-99-99", False),     # right shape, impossible month and day
            ("0000-00-00", False),     # right shape, no such date
        ):
            with self.subTest(expert_reviewed_date=date, accepted=accepted):
                doc = self.expert_reviewed_doc(date)
                if accepted:
                    self.assertAccepted(doc, f"expert_reviewed dated {date}")
                else:
                    self.assertRejected(doc, f"expert_reviewed dated {date}")

    # ---- C03 / C04: closed immediate-transition combinations ---------------

    def test_documented_absent_with_change_ref_rejected(self):
        """C03"""
        doc = self.base()
        transition = self.reverse_transition(doc)
        transition["absence_basis"] = "documented_absent"
        self.assertRejected(doc, "documented_absent carrying a supersession reference")

        with self.subTest(case="superseded_route_still_valid"):
            self.assertAccepted(self.base(), "the operative superseded reverse route")

        with self.subTest(case="present_with_change_ref_still_rejected"):
            other = self.base()
            forward = self.leverage(other)["status_transitions"][
                "from_compliant_to_non_compliant"
            ]["beyond_band"]["immediate_transition"]
            forward["superseded_by_change_ref"] = "chg_immediate_reentry_replaced"
            self.assertRejected(other, "present availability carrying a supersession reference")

    def test_documented_absent_without_change_ref_is_legal(self):
        """C04"""
        doc = self.base()
        transition = self.reverse_transition(doc)
        transition["absence_basis"] = "documented_absent"
        del transition["superseded_by_change_ref"]
        self.assertAccepted(doc, "documented_absent without a change reference")
        # The operative DJIM route is unchanged and is NOT documented_absent.
        live = self.reverse_transition(DJIM)
        self.assertEqual("absent", live["availability"])
        self.assertEqual("superseded", live["absence_basis"])
        self.assertEqual("chg_immediate_reentry_replaced", live["superseded_by_change_ref"])
        records = {c["id"]: c for c in DJIM["methodology_change_record"]}
        self.assertEqual(
            "not_operative", records[live["superseded_by_change_ref"]]["normative_use"]
        )
        bases = [
            t.get("absence_basis") for _p, t in immediate_transitions(DJIM)
            if isinstance(t, dict)
        ]
        self.assertNotIn("documented_absent", bases, "no DJIM documented_absent instance")

    # ---- C05 / C06: threshold-level provenance is threshold-only -----------

    def tolerance_screen(self):
        return next(
            s for s in DJIM["business_activity_screen"]["tolerance_tests"]
            if s["id"] == "scr_djim_revenue_tolerance"
        )

    def test_tolerance_threshold_provenance_is_threshold_only(self):
        """C05"""
        screen = self.tolerance_screen()
        provenance = {e["id"]: e for e in DJIM["provenance"]}
        evidence = {e["id"] for e in DJIM["source_evidence"]}

        self.assertEqual(0.05, screen["threshold"])
        entry = provenance[screen["threshold_provenance_ref"]]

        self.assertEqual("explicit", entry["documentary_resolution"])
        self.assertEqual("not_assessed", entry["source_consistency"]["state"])
        self.assertTrue(entry.get("source_evidence_refs"))
        for ref in entry["source_evidence_refs"]:
            self.assertIn(ref, evidence)
        self.assertNotIn("supported_scope", entry)
        self.assertNotIn("unresolved_scope", entry)
        self.assertNotIn("inherited_from_tracked_rule_file", entry)

        scope = entry["scope_limit"].lower()
        self.assertIn("five percent", scope)
        self.assertIn("no comparator", scope)
        self.assertNotIn("partially", scope)
        # No provenance entry in the file still claims partial support here.
        self.assertNotIn(
            "pv_tolerance_threshold_partial",
            (RULES_DIR / "djim_spdji.yaml").read_text(encoding="utf-8"),
        )

    def test_tolerance_component_provenance_remains_separate(self):
        """C06"""
        screen = self.tolerance_screen()
        provenance = {e["id"]: e for e in DJIM["provenance"]}
        operands = {o["id"]: o for o in DJIM["operands"]}

        threshold_ref = screen["threshold_provenance_ref"]
        comparator_ref = screen["comparator_provenance_ref"]
        numerator_ref = operands[screen["numerator_ref"]]["documentary_basis_provenance_ref"]
        denominator = operands[screen["denominator_ref"]]
        denominator_ref = denominator["documentary_basis_provenance_ref"]
        label_ref = denominator["documentary_labels"][0]["provenance_ref"]
        equivalence_ref = denominator["equivalence_across_editions"][0]["provenance_ref"]

        self.assertEqual("<", screen["comparator"])

        for label, ref in (
            ("comparator", comparator_ref),
            ("numerator_composition", numerator_ref),
            ("denominator_composition", denominator_ref),
        ):
            with self.subTest(claim=label):
                entry = provenance[ref]
                self.assertEqual("unresolved", entry["documentary_resolution"])
                self.assertTrue(entry.get("inherited_from_tracked_rule_file"))
                self.assertEqual("not_assessed", entry["source_consistency"]["state"])
                self.assertNotIn("source_evidence_refs", entry)

        distinct = [threshold_ref, comparator_ref, numerator_ref, denominator_ref,
                    label_ref, equivalence_ref]
        self.assertEqual(
            len(distinct), len(set(distinct)),
            "the threshold provenance id must not be reused for any other claim",
        )
        self.assertEqual("explicit", provenance[label_ref]["documentary_resolution"])
        self.assertEqual("unresolved", provenance[equivalence_ref]["documentary_resolution"])

    # ---- C07 / C08: structured inherited contextual claims -----------------

    def leverage_claims(self):
        return self.leverage(DJIM).get("contextual_claims", [])

    def test_contextual_claims_are_structured_and_non_executable(self):
        """C07"""
        claims = self.leverage_claims()
        provenance = {e["id"]: e for e in DJIM["provenance"]}
        self.assertEqual(3, len(claims))

        ids = [c["id"] for c in claims]
        refs = [c["provenance_ref"] for c in claims]
        self.assertEqual(len(ids), len(set(ids)), "contextual claim ids must be unique")
        self.assertEqual(len(refs), len(set(refs)), "each claim needs its own provenance")

        allowed_keys = {"id", "summary", "provenance_ref"}
        prohibited = {
            "threshold", "comparator", "numerator_ref", "denominator_ref", "operand_refs",
            "status_transitions", "condition_specification", "logic", "clauses",
            "normative_use", "effect", "availability", "on_missing", "default_verdict",
        }
        for claim in claims:
            with self.subTest(claim=claim["id"]):
                self.assertEqual(allowed_keys, set(claim))
                self.assertEqual(set(), set(claim) & prohibited)
                self.assertTrue(claim["summary"].strip())
                entry = provenance[claim["provenance_ref"]]
                self.assertEqual("unresolved", entry["documentary_resolution"])
                self.assertEqual("not_assessed", entry["source_consistency"]["state"])
                self.assertTrue(entry["inherited_from_tracked_rule_file"])
                self.assertNotIn("source_evidence_refs", entry)
                self.assertIn("tracked rule-file content", entry["scope_limit"])

        schema_def = SCHEMA["$defs"]["contextualClaim"]
        self.assertFalse(schema_def["additionalProperties"])
        self.assertEqual(allowed_keys, set(schema_def["properties"]))

        # The three statements are no longer duplicated in the free-text description.
        description = self.leverage(DJIM)["description"].lower()
        for token in ("accounts-receivable", "march 2023", "september 2023",
                      "purification aid", "dividend"):
            with self.subTest(token=token):
                self.assertNotIn(token, description)

    def test_documentation_alignment_and_empty_purification(self):
        """C08"""
        self.assertEqual([], DJIM["purification_methods"])

        readme = README_PATH.read_text(encoding="utf-8")
        inherited_section = readme.split("**Inherited from the tracked rule file")[1]
        inherited_section = inherited_section.split("**Unresolved and recorded")[0].lower()
        for token in ("accounts-receivable", "march 2023", "september 2023", "purification aid"):
            with self.subTest(readme_inherited=token):
                self.assertIn(token, inherited_section)

        # The README must not describe the 5% threshold as partially supported.
        self.assertNotIn("**Partially supported.** The 5% revenue tolerance", readme)

        fmt = (REPO_ROOT / "docs" / "rule-file-format.md").read_text(encoding="utf-8")
        for token in ("contextual_claims", "one claim", "non-executable"):
            with self.subTest(format_doc=token):
                self.assertIn(token, fmt.lower())

    # ---- shared hygiene ---------------------------------------------------

    def test_format_checker_is_active(self):
        """Encoding hygiene; not one of the numbered corrective requirements.

        The suite's single validator must assert formats. Without this, a
        `format: date` constraint is a silent annotation and every
        impossible-date test below would pass vacuously.
        """
        self.assertIsNotNone(VALIDATOR.format_checker, "the shared validator ignores formats")
        self.assertIn("date", FORMAT_CHECKER.checkers)
        for value, expected in (
            ("2026-08-02", True),
            ("2028-02-29", True),
            ("2026-02-31", False),
            ("2026-99-99", False),
            ("0000-00-00", False),
        ):
            with self.subTest(candidate=value):
                self.assertIs(expected, FORMAT_CHECKER.conforms(value, "date"))

        review_date = SCHEMA["$defs"]["review"]["allOf"][0]["then"]["properties"]["date"]
        self.assertEqual("date", review_date["format"])
        self.assertEqual("string", review_date["type"])

    def test_public_files_have_no_bom(self):
        """Encoding hygiene; not one of the numbered corrective requirements."""
        for path in PUBLIC_FILES:
            with self.subTest(file=path.name):
                self.assertFalse(
                    path.read_bytes().startswith(b"\xef\xbb\xbf"),
                    "UTF-8 BOM found",
                )


# --------------------------------------------------------------------------
# Requirement coverage map
# --------------------------------------------------------------------------

REQUIREMENT_MAP = {
    "P01": "TestSchemaAndIdentity.test_schema_version_is_two_zero_zero",
    "P02": "TestSchemaAndIdentity.test_djim_rule_file_version",
    "P03": "TestReferentialIntegrity.test_ids_are_unique",
    "P04": "TestReferentialIntegrity.test_every_reference_resolves_to_correct_type",
    "P05": "TestReferentialIntegrity.test_edition_references_resolve",
    "P06": "TestReferentialIntegrity.test_source_evidence_references_resolve",
    "P07": "TestReferentialIntegrity.test_provenance_references_resolve",
    "P08": "TestReferentialIntegrity.test_open_decision_references_resolve",
    "P09": "TestReferentialIntegrity.test_operand_references_resolve",
    "P10": "TestReferentialIntegrity.test_input_references_resolve",
    "P11": "TestReferentialIntegrity.test_period_references_target_evaluation_period_only",
    "P12": "TestReferentialIntegrity.test_change_references_target_non_operative_records",
    "P13": "TestDocumentaryModel.test_explicit_requires_public_source_evidence",
    "P14": "TestDocumentaryModel.test_consistency_is_not_inferred_from_resolution",
    "P15": "TestDocumentaryModel.test_consistency_defaults_to_not_assessed",
    "P16": "TestDocumentaryModel.test_scoped_inconsistency_is_bound_to_the_change_record",
    "P17": "TestDataOrigin.test_data_origin_only_on_runtime_inputs",
    "P18": "TestDataOrigin.test_semantic_source_and_channel_are_separate",
    "P19": "TestDataOrigin.test_supplied_via_basis_is_absent",
    "P20": "TestDataOrigin.test_execution_readiness_is_absent",
    "P21": "TestPublicFileHygiene.test_no_private_review_material_in_public_files",
    "P22": "TestEditionsAndEvidenceBoundary.test_rule_basis_edition_resolves",
    "P23": "TestEditionsAndEvidenceBoundary.test_no_active_edition_field",
    "P24": "TestEditionsAndEvidenceBoundary.test_inherited_url_is_not_an_edition_identifier",
    "P25": "TestSchemaAndIdentity.test_review_status_remains_unreviewed",
    "P26": "TestCadenceSeparation.test_review_and_evaluation_period_are_separate_objects",
    "P27": "TestCadenceSeparation.test_no_cadence_token_under_evaluation_period",
    "P28": "TestCadenceSeparation.test_evaluation_to_review_mapping_not_established",
    "P29": "TestOperands.test_sampling_interval_remains_unresolved",
    "P30": "TestOperands.test_labels_from_different_editions_are_not_aliased",
    "P31": "TestTransitions.test_directions_are_independently_represented",
    "P32": "TestTransitions.test_availability_vocabulary_is_operational_only",
    "P33": "TestTransitions.test_transition_invariants",
    "P34": "TestTransitions.test_historical_records_are_non_operative",
    "P35": "TestTransitions.test_no_historical_route_is_executable",
    "P36": "TestConditionalEligibility.test_incomplete_specifications_carry_no_logic",
    "P37": "TestConditionalEligibility.test_complete_specifications_require_a_clause",
    "P38": "TestConditionalEligibility.test_no_empty_condition_list",
    "P39": "TestDocumentaryModel.test_no_verdict_policy_key_or_value",
    "P40": "TestExternalClassification.test_scheme_identifier_remains_unresolved",
    "P41": "TestExternalClassification.test_observed_codes_are_non_exhaustive",
    "P42": "TestExternalClassification.test_documentary_cardinality_remains_unresolved",
    "P43": "TestExternalClassification.test_adapter_assignment_shape_remains_open",
    "P44": "TestExternalClassification.test_no_unsourced_cardinality_assertion",
    "P45": "TestDocumentaryModel.test_inherited_content_is_preserved_and_unresolved",
    "P46": "TestPurification.test_purification_container_is_plural_and_empty",
    "P47": "TestEditionsAndEvidenceBoundary.test_readme_anchor_exists",
    "P48": "TestEditionsAndEvidenceBoundary.test_source_evidence_uses_the_stable_boundary",
    "P49": "TestPublicFileHygiene.test_no_new_cache_or_temporary_test_artifact",
    "N01": "TestNegativeSchema.test_legacy_evaluation_frequency_rejected",
    "N02": "TestNegativeSchema.test_legacy_transition_buffer_rejected",
    "N03": "TestNegativeSchema.test_missing_provenance_registry_rejected",
    "N04": "TestNegativeSchema.test_boolean_immediate_transition_rejected",
    "N05": "TestNegativeSchema.test_present_with_supersession_rejected",
    "N06": "TestNegativeSchema.test_absent_without_basis_rejected",
    "N07": "TestNegativeSchema.test_superseded_without_change_reference_rejected",
    "N08": "TestNegativeSchema.test_not_established_with_supersession_rejected",
    "N09": "TestNegativeSchema.test_incomplete_with_empty_clause_list_rejected",
    "N10": "TestNegativeSchema.test_incomplete_with_logic_rejected",
    "N11": "TestNegativeSchema.test_complete_with_empty_clause_list_rejected",
    "N12": "TestNegativeSchema.test_complete_without_logic_rejected",
    "N13": "TestNegativeSchema.test_unsourced_cardinality_key_rejected",
    "N14": "TestNegativeSchema.test_supplied_via_basis_rejected",
    "N15": "TestNegativeSchema.test_execution_readiness_rejected",
    "N16": "TestNegativeSchema.test_explicit_without_source_evidence_rejected",
    "N17": "TestNegativeSchema.test_unknown_policy_keys_rejected",
}


CORRECTIVE_REQUIREMENT_MAP = {
    "C01": "TestCorrectiveHardening.test_unreviewed_metadata_is_all_null",
    "C02": "TestCorrectiveHardening.test_unreviewed_rejects_non_null_metadata",
    "C03": "TestCorrectiveHardening.test_documented_absent_with_change_ref_rejected",
    "C04": "TestCorrectiveHardening.test_documented_absent_without_change_ref_is_legal",
    "C05": "TestCorrectiveHardening.test_tolerance_threshold_provenance_is_threshold_only",
    "C06": "TestCorrectiveHardening.test_tolerance_component_provenance_remains_separate",
    "C07": "TestCorrectiveHardening.test_contextual_claims_are_structured_and_non_executable",
    "C08": "TestCorrectiveHardening.test_documentation_alignment_and_empty_purification",
}


class TestRequirementCoverage(unittest.TestCase):
    """The maps are the deliverable, so a gap in either fails the suite."""

    def test_every_requirement_identifier_is_mapped_exactly_once(self):
        expected = {f"P{n:02d}" for n in range(1, 50)} | {f"N{n:02d}" for n in range(1, 18)}
        self.assertEqual(expected, set(REQUIREMENT_MAP))
        self.assertEqual(len(expected), len(REQUIREMENT_MAP))

    def test_corrective_identifiers_are_mapped_exactly_once(self):
        expected = {f"C{n:02d}" for n in range(1, 9)}
        self.assertEqual(expected, set(CORRECTIVE_REQUIREMENT_MAP))
        self.assertEqual(len(expected), len(CORRECTIVE_REQUIREMENT_MAP))
        self.assertEqual(
            set(), set(REQUIREMENT_MAP) & set(CORRECTIVE_REQUIREMENT_MAP),
            "corrective identifiers must not collide with the original map",
        )

    def test_every_mapped_test_exists(self):
        module = globals()
        combined = {**REQUIREMENT_MAP, **CORRECTIVE_REQUIREMENT_MAP}
        self.assertEqual(len(REQUIREMENT_MAP) + len(CORRECTIVE_REQUIREMENT_MAP), len(combined))
        for identifier, target in combined.items():
            with self.subTest(requirement=identifier, target=target):
                class_name, _, method_name = target.partition(".")
                method_name = method_name.split("[")[0]
                self.assertIn(class_name, module, f"no such TestCase: {class_name}")
                case = module[class_name]
                self.assertTrue(
                    isinstance(case, type) and issubclass(case, unittest.TestCase),
                    f"{class_name} is not a TestCase",
                )
                self.assertTrue(
                    hasattr(case, method_name), f"{class_name} has no method {method_name}"
                )


if __name__ == "__main__":
    unittest.main()
