from typing import Any
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

_PLAN_FILE_LOCK = threading.Lock()
    
PLAN_GENERATION_PROMPT = """You are an expert software engineer that just finished resolving an issue. Your goal is to write a detailled guide that help junior developers also solve the issue. Think of it as making a "How I fixed it" blog post. Because there is an educational goal, make sure that you don't include the solution explicitly, but rather guide the reader to find the solution by themselves. 
Write your response in the file AGENTS.md at the root of the repository.

**Issue:**
{task}

**Patch:**
{patch}

**Instructions:**
1. Analyze the patch to understand what changes were made. Look at the surrounding code if necessary to get context.
2. Understand why these changes solve the problem described, and what steps were taken to arrive at the solution.
3. Write a guide to help junior developers understand how to approach and solve similar issues.

Your output should be in the following format:
```
## Analysis
[Brief analysis of the problem in the context of your solution]

## Solution Approach
[High-level approach to solving the problem]
```
"""

@dataclass
class OraclePlannerConfig:
    generator_config: dict[str, Any]
    plan_model: str
    storage_dir: str = "plans"

class OraclePlanner(Planner):
    """Generates AGENTS.md using the oracle"""

    def __init__(self, **kwargs: Any) -> None:
        self.config = OraclePlannerConfig(**kwargs)
        self.logger = logging.getLogger("agentbench.oracle_planner")

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:

        instance_id = instance.instance_id
        task = instance.task

        agent_md = self._generate_agent_md(env, model, task, instance)

        self.logger.info(f"Writing AGENTS.md for instance {instance_id}")
        # Write the AGENTS.md file to the environment
        env.execute("rm -f AGENTS.md", timeout=False)
        env.execute(f'echo {shlex.quote(agent_md)} > AGENTS.md', timeout=False)

    def update_plan(self, **kwargs) -> None:
        pass

    def _generate_agent_md(self, env: Environment, model: Model, task, instance: Instance) -> str:

        instance_id = instance.instance_id
        patch = instance.patch
        
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
        prompt = PLAN_GENERATION_PROMPT.format(task=task, patch=patch)
        try:
            exit_status, result_diff = generator.run(task=prompt)
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
        storage_dir = storage_dir / "oracle_plans" / self.config.plan_model
        storage_dir.mkdir(parents=True, exist_ok=True)

        return storage_dir