#!/usr/bin/env python3
"""Contract and Beads 1.1.0 tests for orchestration decision policy."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REFERENCES = HERE.parent / "references"
BEADS_STORE = REFERENCES / "beads-store.md"
LIFECYCLE = REFERENCES / "lifecycle.md"
MESSAGE_GRAMMAR = REFERENCES / "message-grammar.md"


class PolicyError(ValueError):
    pass


def parse_record(body: str) -> tuple[str, dict[str, str]]:
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    if not lines or ":" in lines[0]:
        raise PolicyError("record kind is missing")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            raise PolicyError(f"unlabeled record line: {line}")
        key, value = (part.strip() for part in line.split(":", 1))
        if key in fields:
            raise PolicyError(f"duplicate field: {key}")
        fields[key] = value
    return lines[0], fields


def require_fields(fields: dict[str, str], required: set[str]) -> None:
    missing = required - fields.keys()
    empty = {key for key in required & fields.keys() if not fields[key]}
    if missing or empty:
        raise PolicyError(f"missing={sorted(missing)} empty={sorted(empty)}")


def objective_trigger(value: str) -> None:
    if value.strip().lower() in {"", "later", "if needed", "tbd", "none"}:
        raise PolicyError("revisit trigger is not objective")


def validate_local_decision(body: str) -> None:
    kind, fields = parse_record(body)
    if kind != "LOCAL_DECISION":
        raise PolicyError("wrong local decision kind")
    require_fields(
        fields,
        {"owner", "scope", "decision", "rationale", "evidence", "status"},
    )
    if fields["status"] not in {"accepted", "provisional"}:
        raise PolicyError("invalid local decision status")
    if fields["status"] == "provisional":
        require_fields(fields, {"revisit"})
        objective_trigger(fields["revisit"])


def validate_ambiguity(body: str) -> None:
    kind, fields = parse_record(body)
    if kind != "AMBIGUITY":
        raise PolicyError("wrong ambiguity kind")
    require_fields(
        fields,
        {"owner", "scope", "evidence", "unknown", "default", "bounds", "revisit"},
    )
    objective_trigger(fields["revisit"])


def validate_waiting_human(body: str) -> None:
    kind, fields = parse_record(body)
    if kind != "WAITING_HUMAN":
        raise PolicyError("wrong waiting-human kind")
    require_fields(fields, {"owner", "scope", "question", "impact", "resume"})


def validate_autonomous_default(**conditions: bool) -> None:
    required_true = {
        "reversible",
        "local",
        "bounded",
        "policy_compatible",
        "preserves_intent",
    }
    required_false = {"external", "security", "financial", "legal", "cross_boundary"}
    if any(not conditions.get(key, False) for key in required_true):
        raise PolicyError("autonomous default fails a safety condition")
    if any(conditions.get(key, False) for key in required_false):
        raise PolicyError("autonomous default crosses a waiting-human boundary")


def validate_material_promotion(material: bool, promoted_as: str | None) -> None:
    if material and promoted_as not in {"comment", "decision"}:
        raise PolicyError("material message was not promoted")


def validate_decision_edges(edge_types: list[str]) -> None:
    if "blocks" in edge_types:
        raise PolicyError("decision policy uses a blocking edge")
    if not edge_types or any(
        edge not in {"relates-to", "validates"} for edge in edge_types
    ):
        raise PolicyError("decision policy has an invalid affected-bead edge")


def choose_canonical(candidates: list[dict]) -> str:
    keys = {candidate["key"] for candidate in candidates}
    if len(keys) != 1 or "" in keys:
        raise PolicyError("candidates must share one nonempty decision_key")
    by_id = {candidate["id"]: candidate for candidate in candidates}
    accepted = [
        candidate for candidate in candidates if candidate["disposition"] == "accepted"
    ]
    if not accepted:
        raise PolicyError("no accepted decision candidate")

    def walk(candidate_id: str, path: set[str]) -> None:
        if candidate_id in path:
            raise PolicyError("supersession cycle")
        candidate = by_id[candidate_id]
        for target in candidate.get("supersedes", []):
            if target not in by_id or by_id[target]["key"] != candidate["key"]:
                raise PolicyError("invalid supersedes target")
            walk(target, path | {candidate_id})

    for candidate in candidates:
        walk(candidate["id"], set())

    accepted_ids = {candidate["id"] for candidate in accepted}
    accepted_targets = {
        target
        for candidate in accepted
        for target in candidate.get("supersedes", [])
        if target in accepted_ids
    }
    if accepted_targets:
        heads = [
            candidate
            for candidate in accepted
            if candidate["id"] not in accepted_targets
        ]
        if not heads:
            raise PolicyError("supersession chain has no accepted head")
        return max(heads, key=lambda item: (item["created_at"], item["id"]))["id"]
    return min(accepted, key=lambda item: (item["created_at"], item["id"]))["id"]


def section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    end = text.index(next_heading, start)
    return text[start:end]


def schema_fields(text: str, heading: str, record_kind: str) -> set[str]:
    start = text.index(heading)
    fence = text.index("```text", start) + len("```text")
    end = text.index("```", fence)
    kind, fields = parse_record(text[fence:end])
    if kind != record_kind:
        raise PolicyError(f"expected {record_kind}, got {kind}")
    return set(fields)


class DecisionPolicyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = BEADS_STORE.read_text(encoding="utf-8")
        cls.lifecycle = LIFECYCLE.read_text(encoding="utf-8")
        cls.grammar = MESSAGE_GRAMMAR.read_text(encoding="utf-8")

    def test_carrier_table_and_promotion_boundary_are_cross_file_invariants(self):
        carrier = section(
            self.store,
            "## Coordination and policy carriers",
            "## Local decision comments",
        )
        for row in (
            "Work-bead comment",
            "`decision` bead",
            "Message wisp",
            "Artifact / `output_ref`",
        ):
            self.assertIn(row, carrier)
        self.assertIn("No promotion means no policy action", carrier)
        self.assertIn(
            "A material message not promoted has no policy effect", self.grammar
        )
        self.assertIn("Acknowledgement or compaction never deletes", carrier)
        self.assertIn("does not require Gas Town", self.grammar)

    def test_documented_records_have_complete_schemas(self):
        self.assertEqual(
            schema_fields(self.store, "## Local decision comments", "LOCAL_DECISION"),
            {
                "owner",
                "scope",
                "decision",
                "rationale",
                "evidence",
                "status",
                "revisit",
            },
        )
        self.assertEqual(
            schema_fields(
                self.lifecycle,
                "## Human-in-the-loop and safe autonomy",
                "WAITING_HUMAN",
            ),
            {"owner", "scope", "question", "impact", "resume"},
        )
        self.assertEqual(
            schema_fields(
                self.lifecycle,
                "## Durable ambiguity and autonomous defaults",
                "AMBIGUITY",
            ),
            {"owner", "scope", "evidence", "unknown", "default", "bounds", "revisit"},
        )

    def test_decision_links_are_nonblocking_and_disposition_is_explicit(self):
        decision = section(
            self.store,
            "## Cross-boundary decision beads",
            "## Prerequisite",
        )
        self.assertIn("decision_owner", decision)
        self.assertIn("acceptance:", decision)
        self.assertIn("decision_disposition", decision)
        self.assertIn("--type relates-to", decision)
        self.assertIn("--type validates", decision)
        self.assertNotIn("<decision-bead> --type blocks", decision)
        self.assertIn("newest accepted unsuperseded head", decision)
        self.assertIn("earliest candidate", decision)
        self.assertIn("canonical_decision", decision)
        self.assertIn("read both beads back", decision)

    def test_waiting_human_state_can_resume_without_polling(self):
        waiting = section(
            self.lifecycle,
            "## Human-in-the-loop and safe autonomy",
            "## Durable ambiguity and autonomous defaults",
        )
        for contract in (
            "state=waiting_human",
            "state:waiting_human",
            "status `in_progress`",
            "bd gate create --type=human",
            "does not poll",
            "unrelated nodes returned by `bd ready`",
            "state=working",
            "state=pending",
        ):
            self.assertIn(contract, waiting)

    def test_material_message_without_promotion_is_rejected(self):
        with self.assertRaises(PolicyError):
            validate_material_promotion(True, None)
        validate_material_promotion(True, "comment")
        validate_material_promotion(True, "decision")

    def test_blocking_decision_edge_is_rejected(self):
        with self.assertRaises(PolicyError):
            validate_decision_edges(["blocks"])
        validate_decision_edges(["relates-to", "validates"])

    def test_ambiguity_missing_field_and_empty_triggers_are_rejected(self):
        valid = (
            "AMBIGUITY\nowner: coder\nscope: work/resource\n"
            "evidence: test result\nunknown: platform behavior\n"
            "default: preserve state\nbounds: local rollback before report\n"
            "revisit: dependency work.2 enters reported"
        )
        validate_ambiguity(valid)
        with self.assertRaises(PolicyError):
            validate_ambiguity(valid.replace("unknown: platform behavior\n", ""))
        with self.assertRaises(PolicyError):
            validate_ambiguity(valid.replace("dependency work.2 enters reported", ""))

    def test_empty_question_and_provisional_revisit_are_rejected(self):
        with self.assertRaises(PolicyError):
            validate_waiting_human(
                "WAITING_HUMAN\nowner: orch\nscope: work\nquestion: \n"
                "impact: work held\nresume: wake coder"
            )
        with self.assertRaises(PolicyError):
            validate_local_decision(
                "LOCAL_DECISION\nowner: coder\nscope: work\ndecision: keep API\n"
                "rationale: compatibility\nevidence: test\nstatus: provisional\nrevisit: "
            )

    def test_canonical_selection_is_deterministic(self):
        old = {
            "id": "d1",
            "key": "route",
            "created_at": "2026-07-22T01:00:00Z",
            "disposition": "accepted",
            "supersedes": [],
        }
        new = {
            "id": "d2",
            "key": "route",
            "created_at": "2026-07-22T02:00:00Z",
            "disposition": "accepted",
            "supersedes": [],
        }
        self.assertEqual(choose_canonical([new, old]), "d1")
        self.assertEqual(choose_canonical([new | {"supersedes": ["d1"]}, old]), "d2")
        self.assertEqual(
            choose_canonical([old, new | {"created_at": old["created_at"]}]), "d1"
        )
        with self.assertRaises(PolicyError):
            choose_canonical(
                [old | {"supersedes": ["d2"]}, new | {"supersedes": ["d1"]}]
            )

    def test_nonaccepted_supersession_does_not_activate_explicit_selection(self):
        old = {
            "id": "d1",
            "key": "route",
            "created_at": "2026-07-22T01:00:00Z",
            "disposition": "accepted",
            "supersedes": [],
        }
        new = old | {
            "id": "d2",
            "created_at": "2026-07-22T02:00:00Z",
        }
        rejected = old | {
            "id": "d3",
            "created_at": "2026-07-22T03:00:00Z",
            "disposition": "rejected",
            "supersedes": ["d1"],
        }

        self.assertEqual(choose_canonical([old, new, rejected]), "d1")

    def test_unsafe_autonomous_default_is_rejected(self):
        safe = {
            "reversible": True,
            "local": True,
            "bounded": True,
            "policy_compatible": True,
            "preserves_intent": True,
            "external": False,
            "security": False,
            "financial": False,
            "legal": False,
            "cross_boundary": False,
        }
        validate_autonomous_default(**safe)
        for unsafe in ("reversible", "local", "bounded", "preserves_intent"):
            with self.subTest(unsafe=unsafe), self.assertRaises(PolicyError):
                validate_autonomous_default(**(safe | {unsafe: False}))
        for unsafe in ("external", "security", "financial", "legal", "cross_boundary"):
            with self.subTest(unsafe=unsafe), self.assertRaises(PolicyError):
                validate_autonomous_default(**(safe | {unsafe: True}))


class BeadsDecisionPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        cache_root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(
            prefix="decision-policy-", dir=cache_root
        )
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        version = subprocess.run(
            ["bd", "version"], capture_output=True, text=True, check=True, timeout=15
        ).stdout
        self.assertIn("version 1.1.0", version)
        subprocess.run(
            [
                "bd",
                "init",
                "--prefix",
                "dp",
                "--skip-hooks",
                "--skip-agents",
                "--non-interactive",
                "--role",
                "maintainer",
                "--sandbox",
            ],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def bd(
        self,
        *args: str,
        actor: str = "test-orchestrator",
        expect_json: bool = True,
    ):
        env = os.environ.copy()
        env.update(
            {
                "BEADS_ACTOR": actor,
                "BD_JSON_ENVELOPE": "1",
                "BD_NO_PAGER": "1",
                "BD_NON_INTERACTIVE": "1",
            }
        )
        process = subprocess.run(
            ["bd", *args, "--json"],
            cwd=self.repo,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        if not expect_json:
            return None
        payload = json.loads(process.stdout)
        self.assertEqual(payload["schema_version"], 1)
        return payload["data"]

    def create_task(self, title: str, epic: str) -> str:
        return self.bd("create", "--title", title, "--type", "task", "--parent", epic)[
            "id"
        ]

    def create_decision(self, title: str, epic: str, key: str) -> str:
        metadata = json.dumps(
            {
                "decision_key": key,
                "decision_owner": "test-orchestrator",
                "decision_disposition": "accepted",
            },
            sort_keys=True,
        )
        return self.bd(
            "create",
            "--title",
            title,
            "--type",
            "decision",
            "--parent",
            epic,
            "--description",
            title,
            "--design",
            "Evidence-backed test decision.",
            "--acceptance",
            "Read-back matches the expected disposition.",
            "--metadata",
            metadata,
        )["id"]

    def decision_candidates(self, epic: str, key: str) -> list[dict]:
        candidates = []
        decisions = self.bd("list", "--type", "decision", "--parent", epic, "--all")
        for decision in decisions:
            metadata = decision.get("metadata", {})
            if metadata.get("decision_key") != key:
                continue
            shown = self.bd("show", decision["id"])[0]
            candidates.append(
                {
                    "id": shown["id"],
                    "key": metadata["decision_key"],
                    "created_at": shown["created_at"],
                    "disposition": metadata["decision_disposition"],
                    "supersedes": [
                        dependency["id"]
                        for dependency in shown.get("dependencies", [])
                        if dependency["dependency_type"] == "supersedes"
                    ],
                }
            )
        return candidates

    def has_edge(self, source: str, target: str, edge_type: str) -> bool:
        shown = self.bd("show", source)[0]
        return (target, edge_type) in {
            (dependency["id"], dependency["dependency_type"])
            for dependency in shown.get("dependencies", [])
        }

    def settle_noncanonical(self, loser: str, canonical: str, disposition: str) -> dict:
        canonical_before = self.bd("show", canonical)[0]
        self.assertEqual(
            canonical_before["metadata"]["decision_disposition"], "accepted"
        )
        loser_before = self.bd("show", loser)[0]
        expected_metadata = {
            "decision_disposition": disposition,
            "canonical_decision": canonical,
        }
        if any(
            loser_before["metadata"].get(key) != value
            for key, value in expected_metadata.items()
        ):
            self.bd(
                "update",
                loser,
                "--set-metadata",
                f"decision_disposition={disposition}",
                "--set-metadata",
                f"canonical_decision={canonical}",
            )

        if disposition == "duplicate":
            source, target, edge_type = loser, canonical, "relates-to"
            reason = f"duplicate of {canonical}"
        else:
            source, target, edge_type = canonical, loser, "supersedes"
            reason = f"superseded by {canonical}"
        if not self.has_edge(source, target, edge_type):
            self.bd("dep", "add", source, target, "--type", edge_type)

        loser_after_links = self.bd("show", loser)[0]
        canonical_after_links = self.bd("show", canonical)[0]
        for key, value in expected_metadata.items():
            self.assertEqual(loser_after_links["metadata"][key], value)
        self.assertTrue(self.has_edge(source, target, edge_type))
        self.assertEqual(
            canonical_after_links["metadata"]["decision_disposition"], "accepted"
        )
        if (
            loser_after_links["status"] == "closed"
            and loser_after_links["close_reason"] != reason
        ):
            for label in ("decision-repair", "non-work"):
                if label not in loser_after_links.get("labels", []):
                    self.bd("label", "add", loser, label)
                    loser_after_links = self.bd("show", loser)[0]
            self.assertTrue(
                {"decision-repair", "non-work"}.issubset(
                    loser_after_links.get("labels", [])
                )
            )
            canonical_before_reopen = self.bd("show", canonical)[0]
            self.assertEqual(
                canonical_before_reopen["metadata"]["decision_disposition"],
                "accepted",
            )
            self.bd(
                "reopen",
                loser,
                "--reason",
                "repair stale decision close reason",
            )
            self.bd("close", loser, "--reason", reason)

        loser_after_links = self.bd("show", loser)[0]
        if loser_after_links["status"] != "closed":
            if "decision-repair" in loser_after_links.get("labels", []):
                self.assertIn("non-work", loser_after_links.get("labels", []))
                for key, value in expected_metadata.items():
                    self.assertEqual(loser_after_links["metadata"][key], value)
                self.assertTrue(self.has_edge(source, target, edge_type))
                canonical_during_repair = self.bd("show", canonical)[0]
                self.assertEqual(
                    canonical_during_repair["metadata"]["decision_disposition"],
                    "accepted",
                )
            self.bd("close", loser, "--reason", reason)

        loser_after = self.bd("show", loser)[0]
        canonical_after = self.bd("show", canonical)[0]
        self.assertEqual(loser_after["status"], "closed")
        self.assertEqual(loser_after["close_reason"], reason)
        for key, value in expected_metadata.items():
            self.assertEqual(loser_after["metadata"][key], value)
        self.assertTrue(self.has_edge(source, target, edge_type))
        self.assertEqual(
            canonical_after["metadata"]["decision_disposition"], "accepted"
        )
        self.assertNotIn("canonical_decision", canonical_after["metadata"])
        return loser_after

    def assert_repair_recovery(
        self, loser: str, canonical: str, disposition: str, epic: str
    ) -> None:
        repaired = self.settle_noncanonical(loser, canonical, disposition)
        self.assertTrue(
            {"decision-repair", "non-work"}.issubset(repaired.get("labels", []))
        )
        repeated = self.settle_noncanonical(loser, canonical, disposition)
        self.assertEqual(repeated["updated_at"], repaired["updated_at"])

        self.bd(
            "reopen",
            loser,
            "--reason",
            "simulate crash after decision repair reopen",
        )
        interrupted = self.bd("show", loser)[0]
        self.assertEqual(interrupted["status"], "open")
        self.assertTrue(
            {"decision-repair", "non-work"}.issubset(interrupted.get("labels", []))
        )
        selectable = {
            item["id"]
            for item in self.bd(
                "ready", "--parent", epic, "--exclude-label", "non-work"
            )
        }
        self.assertNotIn(loser, selectable)

        recovered = self.settle_noncanonical(loser, canonical, disposition)
        self.assertEqual(recovered["status"], "closed")
        rerun = self.settle_noncanonical(loser, canonical, disposition)
        self.assertEqual(rerun["updated_at"], recovered["updated_at"])
        canonical_after = self.bd("show", canonical)[0]
        self.assertEqual(
            canonical_after["metadata"]["decision_disposition"], "accepted"
        )
        self.assertNotIn("canonical_decision", canonical_after["metadata"])

    def test_duplicate_disposition_is_durable_and_idempotent(self):
        epic = self.bd("create", "--title", "Run", "--type", "epic")["id"]
        first = self.create_decision("Decision: first", epic, "shared-route")
        second = self.create_decision("Decision: second", epic, "shared-route")
        canonical = choose_canonical(self.decision_candidates(epic, "shared-route"))
        loser = second if canonical == first else first

        self.bd(
            "update",
            loser,
            "--set-metadata",
            "decision_disposition=duplicate",
        )
        resolved = self.settle_noncanonical(loser, canonical, "duplicate")
        repeated = self.settle_noncanonical(loser, canonical, "duplicate")

        self.assertEqual(repeated["updated_at"], resolved["updated_at"])
        self.assertEqual(
            choose_canonical(self.decision_candidates(epic, "shared-route")),
            canonical,
        )

    def test_superseded_disposition_is_durable_and_idempotent(self):
        epic = self.bd("create", "--title", "Run", "--type", "epic")["id"]
        old = self.create_decision("Decision: old", epic, "shared-contract")
        replacement = self.create_decision(
            "Decision: replacement", epic, "shared-contract"
        )
        self.bd("dep", "add", replacement, old, "--type", "supersedes")
        canonical = choose_canonical(self.decision_candidates(epic, "shared-contract"))
        self.assertEqual(canonical, replacement)

        resolved = self.settle_noncanonical(old, canonical, "superseded")
        repeated = self.settle_noncanonical(old, canonical, "superseded")

        self.assertEqual(repeated["updated_at"], resolved["updated_at"])
        self.assertEqual(
            choose_canonical(self.decision_candidates(epic, "shared-contract")),
            canonical,
        )

    def test_closed_duplicate_with_stale_reason_is_repaired_and_resumable(self):
        epic = self.bd("create", "--title", "Run", "--type", "epic")["id"]
        first = self.create_decision("Decision: first", epic, "repair-route")
        second = self.create_decision("Decision: second", epic, "repair-route")
        canonical = choose_canonical(self.decision_candidates(epic, "repair-route"))
        loser = second if canonical == first else first
        self.bd("close", loser, "--reason", "accepted and verified")

        stale = self.bd("show", loser)[0]
        self.assertEqual(stale["status"], "closed")
        self.assertEqual(stale["close_reason"], "accepted and verified")
        self.assert_repair_recovery(loser, canonical, "duplicate", epic)

    def test_closed_superseded_with_stale_reason_is_repaired_and_resumable(self):
        epic = self.bd("create", "--title", "Run", "--type", "epic")["id"]
        old = self.create_decision("Decision: old", epic, "repair-contract")
        replacement = self.create_decision(
            "Decision: replacement", epic, "repair-contract"
        )
        self.bd("dep", "add", replacement, old, "--type", "supersedes")
        canonical = choose_canonical(self.decision_candidates(epic, "repair-contract"))
        self.assertEqual(canonical, replacement)
        self.bd("close", old, "--reason", "accepted and verified")

        stale = self.bd("show", old)[0]
        self.assertEqual(stale["status"], "closed")
        self.assertEqual(stale["close_reason"], "accepted and verified")
        self.assert_repair_recovery(old, canonical, "superseded", epic)

    def test_comment_decision_ambiguity_and_waiting_human_flow(self):
        epic = self.bd("create", "--title", "Run", "--type", "epic")["id"]
        work = self.create_task("Affected work", epic)
        validator = self.create_task("Validation work", epic)
        unrelated = self.create_task("Unrelated work", epic)

        local = (
            "LOCAL_DECISION\nowner: coder-local\nscope: work/source\n"
            "decision: preserve existing format\nrationale: compatibility\n"
            "evidence: formatter test passed\nstatus: accepted"
        )
        validate_local_decision(local)
        self.bd("comment", work, local, actor="coder-local")
        comments = self.bd("comments", work)
        self.assertEqual(comments[-1]["author"], "coder-local")
        self.assertEqual(comments[-1]["text"], local)

        decision_metadata = json.dumps(
            {
                "decision_key": "shared-output-format",
                "decision_owner": "test-orchestrator",
                "decision_disposition": "accepted",
            },
            sort_keys=True,
        )
        decision = self.bd(
            "create",
            "--title",
            "Decision: shared output format",
            "--type",
            "decision",
            "--parent",
            epic,
            "--description",
            "Preserve one output format across both work beads.",
            "--design",
            "Compatibility tests are the evidence and rollback boundary.",
            "--acceptance",
            "Both consumers pass their format tests.",
            "--metadata",
            decision_metadata,
        )["id"]
        self.bd("dep", "add", work, decision, "--type", "relates-to")
        self.bd("dep", "add", validator, decision, "--type", "validates")
        validate_decision_edges(["relates-to", "validates"])

        ready = {
            item["id"] for item in self.bd("ready", "--parent", epic, "--type", "task")
        }
        self.assertTrue({work, validator, unrelated}.issubset(ready))
        shown_decision = self.bd("show", decision)[0]
        self.assertEqual(shown_decision["status"], "open")

        blocking_control = self.create_task("Blocking control", epic)
        blocker = self.create_task("True blocker", epic)
        self.bd("dep", "add", blocking_control, blocker, "--type", "blocks")
        ready_with_blocker = {
            item["id"] for item in self.bd("ready", "--parent", epic, "--type", "task")
        }
        self.assertTrue(
            {work, validator, unrelated, blocker}.issubset(ready_with_blocker)
        )
        self.assertNotIn(blocking_control, ready_with_blocker)
        self.bd("close", blocker, "--reason", "blocking control released")
        ready_after_blocker = {
            item["id"] for item in self.bd("ready", "--parent", epic, "--type", "task")
        }
        self.assertIn(blocking_control, ready_after_blocker)

        shown_work = self.bd("show", work)[0]
        self.assertIn(
            (decision, "relates-to"),
            {(dep["id"], dep["dependency_type"]) for dep in shown_work["dependencies"]},
        )
        self.bd("close", decision, "--reason", "accepted and verified")
        shown_decision = self.bd("show", decision)[0]
        self.assertEqual(shown_decision["status"], "closed")
        self.assertEqual(shown_decision["metadata"]["decision_disposition"], "accepted")

        ambiguity = (
            "AMBIGUITY\nowner: coder-local\nscope: two consumers\n"
            "evidence: one consumer test passed\nunknown: second consumer behavior\n"
            "default: preserve existing format\nbounds: no schema changes\n"
            f"revisit: {validator} enters reported"
        )
        validate_ambiguity(ambiguity)
        self.bd("comment", work, ambiguity, actor="coder-local")
        ambiguity_metadata = json.dumps(
            {
                "decision_key": "format-ambiguity",
                "decision_owner": "test-orchestrator",
                "decision_disposition": "proposed",
                "ambiguity_owner": "coder-local",
                "ambiguity_scope": f"{work},{validator}",
                "ambiguity_evidence": "one consumer test passed",
                "ambiguity_unknown": "second consumer behavior",
                "ambiguity_default": "preserve existing format",
                "ambiguity_bounds": "no schema changes",
                "ambiguity_revisit": f"{validator} enters reported",
            },
            sort_keys=True,
        )
        promoted = self.bd(
            "create",
            "--title",
            "Decision: format ambiguity",
            "--type",
            "decision",
            "--parent",
            epic,
            "--description",
            "Promote the local ambiguity before it affects validation work.",
            "--design",
            "Keep the reversible format while the second consumer is unknown.",
            "--acceptance",
            f"Revisit when {validator} enters reported.",
            "--metadata",
            ambiguity_metadata,
        )["id"]
        self.bd("dep", "add", work, promoted, "--type", "relates-to")
        self.bd("dep", "add", validator, promoted, "--type", "validates")
        shown_promoted = self.bd("show", promoted)[0]
        self.assertEqual(shown_promoted["metadata"]["ambiguity_owner"], "coder-local")

        waiting = self.create_task("Needs human intent", epic)
        waiting_record = (
            "WAITING_HUMAN\nowner: test-orchestrator\nscope: waiting/resource\n"
            "question: choose format A or B\nimpact: waiting work is held\n"
            "resume: resolve the human gate and return the bead to pending"
        )
        validate_waiting_human(waiting_record)
        self.bd("comment", waiting, waiting_record)
        self.bd(
            "set-state", waiting, "state=waiting_human", "--reason", "format choice"
        )
        self.bd("update", waiting, "--status", "in_progress")
        gate = self.bd(
            "gate",
            "create",
            "--type",
            "human",
            "--blocks",
            waiting,
            "--reason",
            "choose format A or B",
        )["id"]

        held = self.bd("show", waiting)[0]
        self.assertEqual(held["status"], "in_progress")
        self.assertIn("state:waiting_human", held["labels"])
        ready = {
            item["id"] for item in self.bd("ready", "--parent", epic, "--type", "task")
        }
        self.assertIn(unrelated, ready)
        self.assertNotIn(waiting, ready)

        self.bd(
            "comment", waiting, "HUMAN_ANSWER\nanswer: format A\nref: user response"
        )
        self.bd(
            "gate",
            "resolve",
            gate,
            "--reason",
            "human selected format A",
            expect_json=False,
        )
        self.bd("update", waiting, "--status", "open")
        self.bd(
            "set-state", waiting, "state=pending", "--reason", "human answer recorded"
        )
        resumed = self.bd("show", waiting)[0]
        self.assertEqual(resumed["status"], "open")
        self.assertIn("state:pending", resumed["labels"])
        ready = {
            item["id"] for item in self.bd("ready", "--parent", epic, "--type", "task")
        }
        self.assertIn(waiting, ready)


if __name__ == "__main__":
    unittest.main()
