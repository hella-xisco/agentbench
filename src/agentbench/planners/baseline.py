from typing import Any, List
from pathlib import Path
from dataclasses import dataclass
import threading
import json
import logging
import shlex

from agentbench import Planner, Environment, Model, Instance
from agentbench.generators import get_generator
from agentbench.planners.utils.plan_extractor import extract_plan_from_patch
from agentbench.utils.io_utils import save_traj
from agentbench.utils.others import retry

_PLAN_FILE_LOCK = threading.Lock()


_CODEX_INIT_PROMPT = """Generate a file named AGENTS.md that serves as a contributor guide for this repository.
    Your goal is to produce a clear, concise, and well-structured document with descriptive headings and actionable explanations for each section.
    Follow the outline below, but adapt as needed — add sections if relevant, and omit those that do not apply to this project.
    
    Document Requirements
    
    - Title the document "Repository Guidelines".
    - Use Markdown headings (#, ##, etc.) for structure.
    - Keep the document concise. 200-400 words is optimal.
    - Keep explanations short, direct, and specific to this repository.
    - Provide examples where helpful (commands, directory paths, naming patterns).
    - Maintain a professional, instructional tone.
    
    Recommended Sections
    
    Project Structure & Module Organization
    
    - Outline the project structure, including where the source code, tests, and assets are located.
    
    Build, Test, and Development Commands
    
    - List key commands for building, testing, and running locally (e.g., npm test, make build).
    - Briefly explain what each command does.
    
    Coding Style & Naming Conventions
    
    - Specify indentation rules, language-specific style preferences, and naming patterns.
    - Include any formatting or linting tools used.
    
    Testing Guidelines
    
    - Identify testing frameworks and coverage requirements.
    - State test naming conventions and how to run tests.
    
    Commit & Pull Request Guidelines
    
    - Summarize commit message conventions found in the project’s Git history.
    - Outline pull request requirements (descriptions, linked issues, screenshots, etc.).
    
    (Optional) Add other sections if relevant, such as Security & Configuration Tips, Architecture Overview, or Agent-Specific Instructions."""

_PROMPT_TYPES = {
    "codex_init": _CODEX_INIT_PROMPT, 
}

@dataclass
class BaselinePlannerConfig:
    generator_config: dict[str, Any]
    prompt_type: str
    plan_model: str
    storage_dir: str = "plans"


class BaselinePlanner(Planner):
    """Generates AGENTS.md plans similarly to /init from CodexCLI"""

    def __init__(self, **kwargs: Any) -> None:
        self.config = BaselinePlannerConfig(**kwargs)
        self.logger = logging.getLogger("agentbench.baseline_planner")

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:

        instance_id = instance.instance_id

        agent_md = self._generate_agent_md(env, model, instance_id)

        self.logger.info(f"Writing AGENTS.md for instance {instance_id}")
        # Write the AGENTS.md file to the environment
        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)
        env.execute(f'echo {shlex.quote(agent_md)} > AGENTS.md', timeout=False)
        env.execute(f'echo {shlex.quote(agent_md)} > CLAUDE.md', timeout=False)

    def update_plan(self, **kwargs) -> None:
        pass
    
    @retry(5)
    def _generate_agent_md(self, env: Environment, model: Model, instance_id: str) -> str:
        
        # Try to load the AGENTS.md file if it exists
        agent_md = self._load_agent_md(instance_id)
        if agent_md is not None:
            return agent_md
        
        # Otherwise, generate a new AGENTS.md file
        self.logger.warning(f"No existing AGENTS.md found for {instance_id}. Generating a new one.")
        storage_path = self._get_storage_path()
        traj_path = storage_path / instance_id / f"{instance_id}_traj.json"
        generator_config = self.config.generator_config
        generator = get_generator(generator_config=generator_config, model=model, env=env)
        prompt = _PROMPT_TYPES.get(self.config.prompt_type, "")
        try:
            exit_status, result_diff = generator.run(task=prompt)

            # Clean the repo
            env.execute("git clean -fd", timeout=False)

            save_traj(
                generator=generator,
                path=traj_path,
                exit_status=exit_status,
                result=result_diff,
            )
        except Exception as e:
            self.logger.exception(f"Error generating AGENTS.md for instance {instance_id}: {e}")
            raise RuntimeError(f"Error generating AGENTS.md for instance {instance_id}: {e}") from e
        
        agents_md = extract_plan_from_patch(result_diff)
        if len(agents_md.strip()) == 0:
            raise RuntimeError(f"Extracted AGENTS.md is empty for instance {instance_id}")
        
        
        self._store_agent_md(instance_id, agents_md)
        return agents_md


    def _store_agent_md(self, instance_id: str, agent_md: str) -> None:

        with _PLAN_FILE_LOCK:
            
            storage_dir = self._get_storage_path()
            extracted_plans = storage_dir / "extracted_plans.json"

            if extracted_plans.exists():
                with open(extracted_plans, "r") as f:
                    plans = json.load(f)
            else:
                plans = {}

            plans[instance_id] = agent_md

            with open(extracted_plans, "w") as f:
                json.dump(plans, f, indent=2)

    def _load_agent_md(self, instance_id: str) -> str | None:
        
        storage_dir = self._get_storage_path()
        extracted_plans = storage_dir / "extracted_plans.json"

        if not extracted_plans.exists():
            return None

        with open(extracted_plans, "r") as f:
            plans = json.load(f)

        return plans.get(instance_id, None)
        

    def _get_storage_path(self) -> Path:
        
        storage_dir = Path(self.config.storage_dir)
        storage_dir = storage_dir / "baseline_plans" / self.config.prompt_type / self.config.plan_model
        storage_dir.mkdir(parents=True, exist_ok=True)

        return storage_dir