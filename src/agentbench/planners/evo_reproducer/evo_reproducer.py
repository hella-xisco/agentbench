from typing import Any, List
from dataclasses import dataclass
from pathlib import Path
import threading
import json
import logging
import shlex
import os

from agentbench import Planner, Environment, Model, Instance
from agentbench.utils.io_utils import parse_traces_to_md
from .prompts import GENERATOR_PROMPT, SUMMARIZER_PROMPT
from .utils import parse_rules, update_rules

_PLAN_FILE_LOCK = threading.Lock()

@dataclass
class EvoReproducerPlannerConfig:
    generator_config: dict[str, Any]
    plan_model: str
    experience_history: int = None
    storage_dir: str = "plans"

class EvoReproducerPlanner(Planner):

    def __init__(self, **kwargs) -> None:
        self.config = EvoReproducerPlannerConfig(**kwargs)  
        self.logger = logging.getLogger("agentbench.evo_reproducer_planner")


    def plan(self, env: Environment, model: Model, instance: Instance) -> None:

        instance_id = instance.instance_id
        repo = instance_id.rsplit("-", 1)[0]

        experience = self._load_experience(repo=repo, history=self.config.experience_history)
        generator_prompt = GENERATOR_PROMPT.format(experience=experience)

        self.logger.info(f"Writing experiences to AGENTS.md for instance {instance_id}")
        # Write the AGENTS.md file to the environment
        env.execute(f'echo {shlex.quote(generator_prompt)} > AGENTS.md', timeout=False)
        env.execute(f'echo {shlex.quote(generator_prompt)} > CLAUDE.md', timeout=False)

    def update_plan(self, instance: Instance, traces: List[dict], model: Model, **kwargs) -> None:

        instance_id = instance.instance_id
        repo = instance_id.rsplit("-", 1)[0]

        previous_experience = self._load_experience(repo=repo)

        traj_md = parse_traces_to_md(traces) 

        prompt = SUMMARIZER_PROMPT.format(
            repo=repo,
            issue=instance.task,
            trajectory=traj_md,
            golden_test_patch=instance.patch,
            previous_exp=previous_experience
        )
        self.logger.debug(f"Summarizer prompt for instance {instance_id}:\n{prompt}")
        message = [{"role": "user", "content": prompt}]

        response = model.query(messages=message)
        output = response.choices[0].message.content
        self.logger.debug(f"LLM output for instance {instance_id}:\n{output}")

        self.logger.info(f"Extending experience based on instance {instance_id}")
        self._extend_rules(output)


    def _extend_rules(self, llm_output) -> List[str]:

        with _PLAN_FILE_LOCK:

            storage_dir = self._get_storage_path()
            experience_file = storage_dir / "experience.json"

            if experience_file.exists():
                with open(experience_file, 'r') as f:
                    rule_items_with_count = json.loads(f.read())
            else:
                rule_items_with_count = {}
            
            parsed_operations = parse_rules(llm_output)
            max_num_rules = 5
            # update the rule_items with counter
            rule_items_with_count = update_rules(rule_items_with_count, parsed_operations, list_full = max_num_rules+5 <= len(rule_items_with_count))

            # Update the main experience file
            with open(experience_file, 'w') as f:
                f.write(json.dumps(rule_items_with_count, ensure_ascii=False, indent=2, sort_keys=True))
                f.write("\n")

            # Add to history
            history_dir = storage_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            history_index = 1
            # Find the next available history index
            while (history_dir / f"experience_{history_index}.json").exists():
                history_index += 1
            history_file = history_dir / f"experience_{history_index}.json"
            with open(history_file, 'w') as f:
                f.write(json.dumps(rule_items_with_count, ensure_ascii=False, indent=2, sort_keys=True))
                f.write("\n")
            

    def _load_experience(self, repo: str, history: int = None) -> str:

        storage_path = self._get_storage_path()

        if history is not None:
            self.logger.info(f"Loading experience from history {history} for repo {repo}")
            storage_path = storage_path / "history"
            experience_file = storage_path / f"experience_{history}.json"
        else:
            self.logger.info(f"Loading latest (history not set) experience for repo {repo}")
            experience_file = storage_path / "experience.json"

        # if we have this file
        if os.path.exists(experience_file):
            with open(experience_file, 'r') as f:
                previous_exp = json.loads(f.read())
        else:
            self.logger.error(f"No experience file found in {storage_path}. Using empty experience.")
            previous_exp = {}
        general_exp = ''
        if 'general' in previous_exp:
            general_exp = previous_exp['general']
        # add \n and numbers to general_exp
        general_exp = '\n'.join([f'{i}. {line[0]}' for i, line in enumerate(general_exp, start=1)])
        repo_exp = ''
        if repo in previous_exp:
            repo_exp = previous_exp[repo]
        repo_exp = '\n'.join([f'{i}. {line[0]}' for i, line in enumerate(repo_exp, start=1)])
        previous_exp_txt = 'For all repositories:\n' + general_exp + '\n\n' + 'For ' + repo + ':\n' + repo_exp

        return previous_exp_txt

    def _get_storage_path(self) -> Path:
        
        storage_dir = Path(self.config.storage_dir)
        storage_dir = storage_dir / "evo_reproducer" / self.config.plan_model
        storage_dir.mkdir(parents=True, exist_ok=True)

        return storage_dir