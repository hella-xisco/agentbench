from dataclasses import dataclass
import json
import re
import shlex
import logging

from agentbench import Planner, Environment, Model, Instance


@dataclass
class CuratedPlannerConfig:
    manifest_path: str
    """Path to a JSON manifest: {instance_id: {condition_key: content}}."""
    condition: str
    """Which condition_key to inject for this run: "k0d", "k1", "k1s", "k2", "k2s"."""
    storage_dir: str = "output/plans"
    """Unused, kept for interface parity with other planners."""


# Skill conditions get their content written as SKILL.md into every discovery
# path the delivery gate verified (2026-08-16_02: all three populated, Pi 3/3
# spontaneous activation); which one the agent reads is itself a finding.
SKILL_DIRS = (".claude/skills", ".agents/skills", ".pi/skills")


class CuratedPlanner(Planner):
    """Injects pre-curated context (M1-C output) from a manifest.

    Conditions:
      k0d      -- original DEV file verbatim, written as AGENTS.md
      k1 / k2  -- curated procedural / descriptive content, written as AGENTS.md
      k1s / k2s -- identical content wrapped as SKILL.md (frontmatter carries
                   the skill name), written into all SKILL_DIRS; no AGENTS.md.

    Empty content ("") is a deliberate empty cell (e.g. tinygrad k1: no
    procedural statements exist) -- the repo stays stripped. A *missing*
    condition key is an error, so a run against an incomplete manifest fails
    loudly instead of silently degrading to K0.
    """

    def __init__(self, **kwargs) -> None:
        self.config = CuratedPlannerConfig(**kwargs)
        self.logger = logging.getLogger(f"agentbench.curated_planner.{self.config.condition}")
        with open(self.config.manifest_path) as f:
            self._manifest: dict[str, dict[str, str]] = json.load(f)

    def _write_file(self, env: Environment, path: str, content: str) -> None:
        # printf instead of echo: sh's echo interprets backslash escapes.
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        if parent:
            env.execute(f"mkdir -p {shlex.quote(parent)}", timeout=False)
        env.execute(f"printf '%s' {shlex.quote(content)} > {shlex.quote(path)}", timeout=False)

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:
        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)

        entry = self._manifest.get(instance.instance_id)
        if entry is None:
            raise KeyError(
                f"No curated manifest entry for instance {instance.instance_id} "
                f"in {self.config.manifest_path}"
            )
        if self.config.condition not in entry:
            raise KeyError(
                f"Manifest entry for {instance.instance_id} has no condition "
                f"'{self.config.condition}' -- refusing to run against an incomplete manifest."
            )

        content = entry[self.config.condition]
        if not content.strip():
            self.logger.info(
                f"Condition '{self.config.condition}' is empty by design for "
                f"{instance.instance_id}; leaving repo without context file."
            )
            return

        if self.config.condition.endswith("s"):
            m = re.search(r"^name:\s*(\S+)", content, re.M)
            if not m:
                raise ValueError(
                    f"Skill content for {instance.instance_id}/{self.config.condition} "
                    "has no 'name:' frontmatter line."
                )
            skill_name = m.group(1)
            for d in SKILL_DIRS:
                self._write_file(env, f"{d}/{skill_name}/SKILL.md", content)
        else:
            self._write_file(env, "AGENTS.md", content)

    def update_plan(self, **kwargs) -> None:
        pass
