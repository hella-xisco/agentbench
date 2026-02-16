from typing import Any, List
from pathlib import Path
from dataclasses import dataclass
import threading
import jsonlines
import logging
import shlex

from agentbench import Planner, Environment, Model, Generator, Instance
from agentbench.utils.io_utils import parse_traces_to_md
from .prompts import GENERATOR_PROMPT, CURATOR_PROMPT

_PLAN_FILE_LOCK = threading.Lock()

def extract_cheatsheet(
    response: str,
    old_cheatsheet: str,
) -> str:
    """
    Extracts the cheatsheet from the model response.
    
    Arguments:
        response : str : The response from the model.
        old_cheatsheet : str : The old cheatsheet to return if the new one is not found.

    Returns:
        str : The extracted cheatsheet (if not found, returns the old cheatsheet).
    """
    response = response.strip()
    # <cheatsheet> (content) </cheatsheet>
    if "<cheatsheet>" in response:
        try:
            txt = response.split("<cheatsheet>")[1].strip()
            txt = txt.split("</cheatsheet>")[0].strip()
            return txt
        except:
            return old_cheatsheet
    else:
        return old_cheatsheet
    

@dataclass
class DCPlannerConfig:
    generator_config: dict[str, Any]
    plan_model: str
    storage_dir: str = "plans"
    cheatsheet_history: int = None


class DCPlanner(Planner):
    """Generates AGENTS.md plans from dynamic cheatsheet
    
    For more information, see: https://github.com/suzgunmirac/dynamic-cheatsheet
    """

    def __init__(self, **kwargs: Any) -> None:
        self.config = DCPlannerConfig(**kwargs)
        self.logger = logging.getLogger("agentbench.dc_planner")

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:

        instance_id = instance.instance_id

        cheatsheet = self._load_cheatsheet(cheatsheet_history=self.config.cheatsheet_history, repo=instance.repo)
        generator_prompt = GENERATOR_PROMPT.replace("[[CHEATSHEET]]", cheatsheet)

        self.logger.info(f"Writing cheatsheet to AGENTS.md for instance {instance_id}")
        # Write the AGENTS.md file to the environment
        env.execute(f'echo {shlex.quote(generator_prompt)} > AGENTS.md', timeout=False)
        env.execute(f'echo {shlex.quote(generator_prompt)} > CLAUDE.md', timeout=False)

    def _add_cheatsheet_to_env(self, env: Environment, cheatsheet: str) -> None:
        # Remove any existing AGENTS.md file
        env.execute("rm -f AGENTS.md", timeout=False)
        # Write the cheatsheet to AGENTS.md in the environment
        env.execute(f'echo {shlex.quote(cheatsheet)} > AGENTS.md', timeout=False)

    def update_plan(self, instance: Instance, traces: List[dict], model: Model, **kwargs) -> None:

        instance_id = instance.instance_id
        task = instance.task

        previous_cheatsheet = self._load_cheatsheet(repo=instance.repo)

        generator_output = parse_traces_to_md(traces)

        # STEP 2: Run the cheatsheet extraction model with the generator output and the current cheatsheet
        cheatsheet_prompt = CURATOR_PROMPT.replace("[[QUESTION]]", task).replace("[[MODEL_ANSWER]]", generator_output).replace("[[PREVIOUS_CHEATSHEET]]", previous_cheatsheet)

        cheatsheet_history = [{"role": "user", "content": cheatsheet_prompt}]

        
        cheatsheet_output = model.query(messages=cheatsheet_history)
        self.logger.debug(f"Cheatsheet model output: {cheatsheet_output}")

        new_cheatsheet = extract_cheatsheet(response=cheatsheet_output, old_cheatsheet=previous_cheatsheet)

        step = {
            "messages": traces,
            "current_cheatsheet": previous_cheatsheet,
            "new_cheatsheet": new_cheatsheet,
        }
        self._store_cheatsheet(new_cheatsheet, repo=instance.repo)
        self._store_training_trace(instance_id=instance_id, trace=step)

    def train(self, env: Environment, generator: Generator, model: Model, instance: Instance, n_rounds: int = 1, add_previous_answers_to_cheatsheet: bool = False) -> None:
        """Solve the instance and update the cheatsheet"""

        instance_id = instance.instance_id
        task = instance.task
        self.logger.info(f"Training on instance {instance_id}")

        cheatsheet = self._load_cheatsheet(repo=instance.repo)

        previous_answers = []

        rounds_completed = self._skip_round(instance_id=instance_id)
        if rounds_completed >= n_rounds:
            self.logger.info(f"Skipping instance {instance_id} as it has already been trained for {rounds_completed} rounds")
            return

        round = rounds_completed
        failures = 0
        max_failures = 3

        while round < max(1, n_rounds):
            self.logger.info(f"Round {round+1}/{n_rounds} for instance {instance_id}")
            try:
                ## STEP 1: Run the generator model with the input text and the cheatsheet
                generator_cheatsheet_content = cheatsheet
                
                # If there are previous answers, add them to the cheatsheet content for the generator
                if round > 0 and add_previous_answers_to_cheatsheet:
                    previous_answers_txt = f"PREVIOUS ANSWERS:\n{'; '.join(previous_answers)}"
                    generator_cheatsheet_content = f"{generator_cheatsheet_content}\n\n{previous_answers_txt}"


                generator_prompt = GENERATOR_PROMPT.replace("[[CHEATSHEET]]", generator_cheatsheet_content)
                current_cheatsheet = cheatsheet


                # Run the generator model
                self._add_cheatsheet_to_env(env, cheatsheet=generator_prompt)
                _, generator_answer = generator.run(task=task)

                traces = generator.messages
                generator_output = parse_traces_to_md(traces)

                ## STEP 2: Run the cheatsheet extraction model with the generator output and the current cheatsheet
                cheatsheet_prompt = CURATOR_PROMPT.replace("[[QUESTION]]", task).replace("[[MODEL_ANSWER]]", generator_output).replace("[[PREVIOUS_CHEATSHEET]]", current_cheatsheet)

                cheatsheet_history = [{"role": "user", "content": cheatsheet_prompt}]

                cheatsheet_output = model.query(messages=cheatsheet_history)
                #cheatsheet_output = model.query(messages=cheatsheet_history)
                self.logger.debug(f"Cheatsheet model output: {cheatsheet_output}")

                # Extract the new cheatsheet from the output (if present); otherwise, return the old cheatsheet
                new_cheatsheet = extract_cheatsheet(response=cheatsheet_output, old_cheatsheet=current_cheatsheet)
                cheatsheet = new_cheatsheet

                previous_answers.append(f"Round {round+1}: {generator_answer}")
            
                step = {
                    "round": round,
                    "generator_prompt": generator_prompt,
                    "messages": traces,
                    "responses": generator.model.responses,
                    "generator_answer": generator_answer,
                    "current_cheatsheet": current_cheatsheet,
                    "new_cheatsheet": new_cheatsheet,
                }

                self._store_cheatsheet(cheatsheet, repo=instance.repo)
                self._store_training_trace(instance_id=instance_id, trace=step)

                # Clear the generator traces and responses for the next round
                generator.messages = []
                generator.model.responses = []
                round += 1

            except Exception as e:
                failures += 1
                
                generator.messages = []
                generator.model.responses = []

                if failures >= max_failures:
                    raise RuntimeError(f"Max failures reached during training on instance {instance_id}, round {round+1}: {e}") from e
                self.logger.exception(f"Error during training on instance {instance_id}, round {round+1}: {e}")
                #raise RuntimeError(f"Error during training on instance {instance_id}, round {round+1}: {e}") from e
                
        
    def _skip_round(self, instance_id: str) -> None:
        with _PLAN_FILE_LOCK:
            trace_path = self._get_storage_path() / instance_id 
            trace_file = trace_path / f"{instance_id}_training_trace.jsonl"

            # Load existing traces
            existing_traces = 0
            if trace_file.exists():
                with jsonlines.open(trace_file, "r") as reader:
                    for _ in reader:
                        existing_traces += 1

        return existing_traces



    def _store_training_trace(self, instance_id: str, trace: dict) -> None:
        with _PLAN_FILE_LOCK:
            trace_path = self._get_storage_path() / instance_id 
            trace_file = trace_path / f"{instance_id}_training_trace.jsonl"

            # Ensure the directory exists and the file exists
            trace_path.mkdir(parents=True, exist_ok=True)
            if not trace_file.exists():
                trace_file.write_text("")

            with jsonlines.open(trace_file, "a") as writer:
                writer.write(trace)

    def _store_cheatsheet(self, cheatsheet: str, repo: str) -> None:

        repo = repo.replace("/", "_")

        with _PLAN_FILE_LOCK:
            
            storage_dir = self._get_storage_path()
            cheatsheet_path = storage_dir / f"cheatsheet_{repo}.txt"

            # Ensure the directory exists
            storage_dir.mkdir(parents=True, exist_ok=True)

            with open(cheatsheet_path, "w") as f:
                f.write(cheatsheet)

            # Add the cheatsheet to history
            cheatsheet_history_dir = storage_dir / "cheatsheet_history"
            cheatsheet_history_dir.mkdir(parents=True, exist_ok=True)
            history_index = 1
            # Find the next available history index
            while (cheatsheet_history_dir / f"cheatsheet_{history_index}_{repo}.txt").exists():
                history_index += 1
            with open(cheatsheet_history_dir / f"cheatsheet_{history_index}_{repo}.txt", "w") as f:
                f.write(cheatsheet)

    def _load_cheatsheet(self, cheatsheet_history: int = None, repo: str = None) -> str | None:

        repo = repo.replace("/", "_")
        
        storage_dir = self._get_storage_path()
        if cheatsheet_history is not None:
            cheatsheet_path = storage_dir / "cheatsheet_history" / f"cheatsheet_{cheatsheet_history}_{repo}.txt"
        else:
            cheatsheet_path = storage_dir / f"cheatsheet_{repo}.txt"

        if not cheatsheet_path.exists():
            self.logger.error(f"No cheatsheet_{repo}.txt found in {storage_dir}. Using empty cheatsheet.")
            return "(empty)"

        with open(cheatsheet_path, "r") as f:
            return f.read()
        

    def _get_storage_path(self) -> Path:
        
        storage_dir = Path(self.config.storage_dir)
        storage_dir = storage_dir / "dynamic_cheatsheet" / self.config.plan_model
        storage_dir.mkdir(parents=True, exist_ok=True)

        return storage_dir