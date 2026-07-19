from dataclasses import dataclass
import json
import shlex
import logging

from agentbench import Planner, Environment, Model, Instance


@dataclass
class CuratedPlannerConfig:
    manifest_path: str
    """Path to a JSON manifest: {instance_id: {condition_key: content}}."""
    condition: str
    """Which condition_key to inject for this run, e.g. "k1c", "k2b", "k2a", "k1a", "k1b"."""
    storage_dir: str = "output/plans"
    """Unused, kept for interface parity with other planners."""


class CuratedPlanner(Planner):
    """Injects pre-curated AGENTS.md/CLAUDE.md content (K1/K2 family) from a manifest.

    Unlike InitPlanner (LLM-generated) or HumanPlanner (fetched from future git commits),
    the content here comes from the M1-C descriptive/procedural curation of the real
    DEV-context files. One manifest holds every condition variant per instance; which
    variant gets injected is a config toggle (`condition`), not a code change.
    """

    def __init__(self, **kwargs) -> None:
        self.config = CuratedPlannerConfig(**kwargs)
        self.logger = logging.getLogger(f"agentbench.curated_planner.{self.config.condition}")
        with open(self.config.manifest_path) as f:
            self._manifest: dict[str, dict[str, str]] = json.load(f)

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:
        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)

        entry = self._manifest.get(instance.instance_id)
        if entry is None:
            raise KeyError(
                f"No curated manifest entry for instance {instance.instance_id} "
                f"in {self.config.manifest_path}"
            )

        content = entry.get(self.config.condition, "")
        if not content.strip():
            # Empty by design for "no file" conditions (e.g. K1a) — repo stays stripped.
            self.logger.info(
                f"Condition '{self.config.condition}' is empty for {instance.instance_id}; "
                "leaving repo without AGENTS.md/CLAUDE.md."
            )
            return

        env.execute(f"echo {shlex.quote(content)} > AGENTS.md", timeout=False)
        env.execute(f"echo {shlex.quote(content)} > CLAUDE.md", timeout=False)

    def update_plan(self, **kwargs) -> None:
        pass
