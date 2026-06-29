"""Injectable I/O adapter protocol for the project-setup runner.

Every user-facing interaction — interview questions, gate confirmations, and
agent-steered step hand-offs — goes through an ``InterviewIO`` implementation.
Tests inject a ``ScriptedIO`` double so no stdin/stdout is required.  The live
CLI injects a ``TerminalIO``.

Standard library only (no third-party deps).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
# Protocol                                                                     #
# --------------------------------------------------------------------------- #
@runtime_checkable
class InterviewIO(Protocol):
    """Injectable I/O boundary for all human-facing interactions.

    All methods have deliberate signatures that are easy to fake in tests.
    """

    def ask(self, input_spec: dict[str, Any], default: Any) -> Any:
        """Ask the user for a single answer value.

        Parameters
        ----------
        input_spec:
            An ``InputSpec``-shaped dict (keys: ``key``, ``type``, ``prompt``,
            ``choices``, ``required``).
        default:
            The resolved default from the layering model (may be ``None``).

        Returns
        -------
        Any
            The user's raw answer (before coercion).  An empty return yields
            *default*.
        """
        ...

    def confirm(self, item: dict[str, Any]) -> bool:
        """Ask the user to confirm a proposed file write.

        Parameters
        ----------
        item:
            A ``Diff``-shaped dict (keys: ``path``, ``kind``, ``preview``).

        Returns
        -------
        bool
            ``True`` = user confirmed, ``False`` = user skipped.
        """
        ...

    def agent_step(
        self,
        steering_path: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Hand a kind=agent step to the agent and return its decision.

        Parameters
        ----------
        steering_path:
            Relative path to the steering markdown file (from the module root).
        context:
            Arbitrary context dict the agent may use (plan fragment, ids, …).

        Returns
        -------
        dict
            Must contain at least:
            - ``"answers_to_persist"`` — ``{key: {"value": Any, "source": "agent-steered"}}``
            - ``"message"`` — human-readable description of the decision.
        """
        ...

    def notify(self, msg: str) -> None:
        """Emit an informational message to the user (no response expected)."""
        ...


# --------------------------------------------------------------------------- #
# TerminalIO — live interactive adapter                                        #
# --------------------------------------------------------------------------- #
class TerminalIO:
    """Interactive CLI adapter: prompts the user via stdin/stdout."""

    def ask(self, input_spec: dict[str, Any], default: Any) -> Any:
        type_ = input_spec.get("type", "string")
        prompt_text = input_spec.get("prompt", input_spec.get("key", "?"))
        choices = input_spec.get("choices")
        key = input_spec.get("key", "?")

        # Format the prompt line
        if choices:
            choices_str = ", ".join(str(c) for c in choices)
            prompt_line = f"{prompt_text} [{choices_str}]"
        else:
            prompt_line = str(prompt_text)

        if default is not None:
            prompt_line += f" (default: {default!r})"
        prompt_line += ": "

        # For bool/choice/multichoice give extra guidance
        if type_ == "bool":
            prompt_line = f"{prompt_text} [y/n]"
            if default is not None:
                prompt_line += f" (default: {'y' if default else 'n'})"
            prompt_line += ": "

        raw = input(prompt_line).strip()

        if raw == "" and default is not None:
            return default

        # Light coercion at the IO boundary (full coerce happens in answers.py)
        if type_ == "bool":
            if raw.lower() in ("y", "yes", "true", "1"):
                return True
            if raw.lower() in ("n", "no", "false", "0"):
                return False
            return default

        if type_ in ("list", "multichoice") and raw:
            return [v.strip() for v in raw.split(",") if v.strip()]

        return raw if raw else default

    def ask_non_interactive(self, input_spec: dict[str, Any], default: Any) -> Any:
        """Non-interactive resolution: return the provided default WITHOUT
        prompting (never blocks on stdin). The pipeline calls this when run with
        --non-interactive so a CLI/CI invocation uses flag/home/project/default
        values rather than hanging. A required input with no resolvable default
        will be caught by the validate-closed gate (MISSING_ANSWER), which is the
        correct, actionable failure.
        """
        return default

    def confirm(self, item: dict[str, Any]) -> bool:
        path = item.get("path", "?")
        kind = item.get("kind", "?")
        preview = item.get("preview", "")
        # Soft gates (spec 004 FR-004) default to Yes and prompt [Y/n]; everything
        # else (file writes, hard gates) keeps the safe [y/N] default-No.
        default_yes = bool(item.get("default_yes", False))
        print(f"\n  [{kind.upper()}] {path}")
        if preview:
            # indent preview lines
            for line in str(preview).splitlines()[:3]:
                print(f"    {line}")
        if default_yes:
            raw = input("  Proceed? [Y/n]: ").strip().lower()
            return raw in ("", "y", "yes")
        prompt = "  Proceed? [y/N]: " if kind == "gate" else "  Write this file? [y/N]: "
        raw = input(prompt).strip().lower()
        return raw in ("y", "yes")

    def agent_step(
        self,
        steering_path: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        # In the terminal adapter we cannot actually invoke a sub-agent;
        # this is the human-in-the-loop fallback.
        print(f"\n[AGENT STEP] Steering: {steering_path}")
        print("  This step requires agent-steered input.")
        print("  Context:", context)
        print("  (No sub-agent available in terminal mode; skipping.)")
        return {"answers_to_persist": {}, "message": "skipped (no agent available)"}

    def notify(self, msg: str) -> None:
        print(msg)


# --------------------------------------------------------------------------- #
# ScriptedIO — test double (deterministic, no stdin)                          #
# --------------------------------------------------------------------------- #
class ScriptedIO:
    """Deterministic test double for ``InterviewIO``.

    Answers are looked up by ``module_id.key`` (set before use) or by a
    global key.  If neither is present the declared default is returned.

    Usage::

        io = ScriptedIO(answers={"core-identity.name": "acme"})
        io.confirmations = {"all": True}   # confirm every proposed write

    All interactions are recorded in ``.log`` for assertions.
    """

    def __init__(
        self,
        answers: dict[str, Any] | None = None,
        confirmations: dict[str, bool] | None = None,
        agent_responses: dict[str, dict[str, Any]] | None = None,
        default_confirm: bool = True,
    ) -> None:
        self.answers: dict[str, Any] = answers or {}
        self.confirmations: dict[str, bool] = confirmations or {}
        self.agent_responses: dict[str, dict[str, Any]] = agent_responses or {}
        self.default_confirm = default_confirm
        self.log: list[dict[str, Any]] = []

    def ask(self, input_spec: dict[str, Any], default: Any) -> Any:
        key = input_spec.get("key", "")
        # Try exact key, then fall back to default
        if key in self.answers:
            value = self.answers[key]
        else:
            value = default
        self.log.append({"op": "ask", "key": key, "value": value})
        return value

    def confirm(self, item: dict[str, Any]) -> bool:
        path = item.get("path", "")
        if path in self.confirmations:
            result = self.confirmations[path]
        elif "all" in self.confirmations:
            result = self.confirmations["all"]
        else:
            result = self.default_confirm
        self.log.append({"op": "confirm", "path": path, "result": result})
        return result

    def agent_step(
        self,
        steering_path: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.agent_responses.get(
            steering_path,
            {"answers_to_persist": {}, "message": "scripted-no-op"},
        )
        self.log.append({
            "op": "agent_step",
            "steering_path": steering_path,
            "response": response,
        })
        return response

    def notify(self, msg: str) -> None:
        self.log.append({"op": "notify", "msg": msg})


# --------------------------------------------------------------------------- #
# FileAnswersIO — production answer-driven adapter (non-interactive)          #
# --------------------------------------------------------------------------- #
class FileAnswersIO:
    """Production non-interactive IO adapter driven by a pre-collected answers dict.

    The agent collects all answers up front (interview + agent-steered decisions),
    writes them to a JSON/TOML file, and passes the file to ``--answers``. This
    adapter reads that dict and never calls ``input()``.

    Lookup order for ``ask``:
      1. ``"{module_id}.{key}"`` when ``module_id`` is present in *input_spec*.
      2. Bare ``"{key}"`` — fallback for shared defaults.
      3. The *default* argument.

    Gates are driven by the per-action flags (``active_flags``) and the
    ``non_interactive=True`` path in ``executor.run_gate_step``, which honours
    ``allow_flag``/``skip_flag`` + hardness semantics without prompting.
    ``confirm`` returns ``False`` so that any residual interactive confirm call
    (e.g. a file-write confirm) safe-skips; the answer-driven path passes
    ``non_interactive=True`` to ``run_pipeline`` so hard-gate decisions are made
    in ``run_gate_step`` — not here.

    The ``enabled`` module-selection list may be supplied separately because its
    source is a top-level key in the answers file, not a ``module_id.key`` entry.

    All interactions are recorded in ``.log`` for assertions (mirrors ScriptedIO).
    Stdlib only.
    """

    _ENABLED_KEY = "enabled"

    #: Marker queried by run_agent_phase to skip live agent calls when
    #: all answers are pre-frozen. Additive — does not break the protocol.
    is_answer_driven: bool = True

    def __init__(
        self,
        answers: dict[str, Any] | None = None,
        enabled: list[str] | None = None,
        active_flags: frozenset[str] | None = None,
    ) -> None:
        self.answers: dict[str, Any] = answers or {}
        self.enabled: list[str] | None = enabled
        self.active_flags: frozenset[str] = active_flags or frozenset()
        self.log: list[dict[str, Any]] = []

    def ask(self, input_spec: dict[str, Any], default: Any) -> Any:
        key = input_spec.get("key", "")
        module_id = input_spec.get("module_id", "")

        # Special case: module-selection "enabled" question — return the
        # pre-supplied enabled list so the agent's confirmed module set is honored.
        if key == self._ENABLED_KEY and self.enabled is not None:
            self.log.append({"op": "ask", "key": key, "module_id": module_id, "value": self.enabled, "source": "enabled"})
            return self.enabled

        # Resolve module_id.key first (FR-003), then bare key, then default.
        if module_id:
            qualified = f"{module_id}.{key}"
            if qualified in self.answers:
                value = self.answers[qualified]
                self.log.append({"op": "ask", "key": key, "module_id": module_id, "value": value, "source": "qualified"})
                return value

        if key in self.answers:
            value = self.answers[key]
            self.log.append({"op": "ask", "key": key, "module_id": module_id, "value": value, "source": "bare"})
            return value

        self.log.append({"op": "ask", "key": key, "module_id": module_id, "value": default, "source": "default"})
        return default

    # Non-interactive ask alias so pipeline._interview_module's non-interactive
    # branch (which calls ask_non_interactive when available) also goes through
    # our answer-lookup instead of the TerminalIO default-only path.
    def ask_non_interactive(self, input_spec: dict[str, Any], default: Any) -> Any:
        return self.ask(input_spec, default)

    def confirm(self, item: dict[str, Any]) -> bool:
        """Never prompt. Return False (safe-skip default for non-interactive use).

        In answer-driven mode run_pipeline is called with non_interactive=True,
        so run_gate_step handles hard/soft gate semantics via flags — this method
        is only reached for file-write confirms, which should safe-skip (the
        pipeline writes files through the python-step path, not through io.confirm).
        """
        path = item.get("path", "")
        self.log.append({"op": "confirm", "path": path, "result": False})
        return False

    def agent_step(
        self,
        steering_path: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """No-op: agent-steered answers are pre-seeded in the answers dict.

        Returns an empty ``answers_to_persist`` so the agent-phase fold loop
        short-circuits (reproduce.py line ~661: ``if not atp: continue``).
        """
        self.log.append({"op": "agent_step", "steering_path": steering_path})
        return {"answers_to_persist": {}, "message": "answer-driven: agent-steered answers pre-seeded"}

    def notify(self, msg: str) -> None:
        print(msg)
        self.log.append({"op": "notify", "msg": msg})
