from typing import Any, List, Optional, Sequence
from pathlib import Path
from dataclasses import dataclass
import threading
import json
import logging
import shlex

from agentbench import Planner, Environment, Model, Instance
from agentbench.utils.io_utils import parse_traces_to_md
from agentbench.utils.diff_file import DiffFile
from agentbench.utils.others import retry
from .playbook import Playbook
from .prompts import (
    CURATOR_PROMPT,
    REFLECTOR_PROMPT,
    REFLECTOR_SYSTEM_PROMPT,
    GENERATOR_PROMPT,
)
from .roles import ReflectorOutput, BulletTag, CuratorOutput, safe_json_loads
from .delta import DeltaBatch


_PLAN_FILE_LOCK = threading.Lock()

@dataclass
class ACEPlannerConfig:
    plan_model: str
    storage_dir: str = "plans"
    playbook_history: int = None


class ACEPlanner(Planner):
    """Generates AGENTS.md plans from Agent Context Engineering (ACE)."""

    def __init__(self, **kwargs: Any) -> None:
        self.config = ACEPlannerConfig(**kwargs)
        self.logger = logging.getLogger("agentbench.ace_planner")
        self.logger.debug("Initialized ACEPlanner with config: %s", self.config)
        self.max_retries = 3

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:
        instance_id = instance.instance_id

        playbook = self._load_playbook(self.config.playbook_history, repo=instance.repo)
        self.logger.debug(
            "Loaded playbook stats for planning: %s",
            playbook.stats(),
        )

        generator_prompt = GENERATOR_PROMPT.format(
            playbook=playbook.as_prompt() or "(empty playbook)",
        )

        self.logger.info(f"Writing AGENTS.md for instance {instance_id}.")

        # Sometimes the playbook is too large; we write in chunks
        for file_path in ("AGENTS.md", "CLAUDE.md"):
            # 1) truncate the file
            env.execute(f": > {shlex.quote(file_path)}", timeout=False)

            # 2) append in safe-sized chunks
            CHUNK_SIZE = 60_000  # adjust down if you still hit limits
            for i in range(0, len(generator_prompt), CHUNK_SIZE):
                chunk = generator_prompt[i:i + CHUNK_SIZE]
                env.execute(
                    f"printf %s {shlex.quote(chunk)} >> {shlex.quote(file_path)}",
                    timeout=False
                )

    def _reflector_analysis(
        self,
        task: str,
        generator_output: str,
        result: str,
        ground_truth: str,
        feedback: str,
        previous_playbook: Playbook,
        model: Model,
    ) -> ReflectorOutput:
        base_prompt = REFLECTOR_PROMPT.format(
            question=task,
            traces=generator_output,
            prediction=result,
            ground_truth=ground_truth,
            feedback=feedback,
            playbook=previous_playbook.as_prompt() or "(empty playbook)",
        )
        result: Optional[ReflectorOutput] = None
        prompt = base_prompt
        last_error: Optional[Exception] = None


        for attempt in range(self.max_retries):
            self.logger.debug(
                "Reflector attempt %d/%d for task snippet=%s",
                attempt + 1,
                self.max_retries,
                task[:80].replace("\n", " "),
            )
            messages = [
                {"role": "system", "content": REFLECTOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            response = model.query(messages=messages)
            try:
                data = safe_json_loads(response.choices[0].message.content)
                bullet_tags: List[BulletTag] = []
                tags_payload = data.get("bullet_tags", [])
                if isinstance(tags_payload, Sequence):
                    for item in tags_payload:
                        if isinstance(item, dict) and "id" in item and "tag" in item:
                            bullet_tags.append(
                                BulletTag(
                                    id=str(item["id"]), tag=str(item["tag"]).lower()
                                )
                            )
                candidate = ReflectorOutput(
                    reasoning=str(data.get("reasoning", "")),
                    error_identification=str(data.get("error_identification", "")),
                    root_cause_analysis=str(data.get("root_cause_analysis", "")),
                    correct_approach=str(data.get("correct_approach", "")),
                    key_insight=str(data.get("key_insight", "")),
                    bullet_tags=bullet_tags,
                    raw=data,
                )
                result = candidate
                # Early exit if we already have actionable output
                if bullet_tags or candidate.key_insight:
                    self.logger.info(
                        "Reflector produced actionable output with %d tags.",
                        len(bullet_tags),
                    )
                    self.logger.debug(f"Raw reflector output: {data}")
                    return candidate
                break
            except ValueError as err:
                last_error = err
                if attempt + 1 >= self.max_retries:
                    break
                self.logger.warning(
                    "Reflector returned invalid JSON (attempt %d/%d). Retrying.",
                    attempt + 1,
                    self.max_retries,
                )
                prompt = (
                    base_prompt + "\n\nPlease output valid JSON, escape double quotes, "
                    "and do not include any additional explanatory text."
                )
        if result is None:
            self.logger.error("Reflector failed to produce a valid result after retries.")
            raise RuntimeError("Reflector failed to produce a result.") from last_error
        return result
    
    def _curator_analysis(self, reflection: ReflectorOutput, playbook: Playbook, task: str, model: Model) -> CuratorOutput:

        curator_prompt = CURATOR_PROMPT.format(
            reflection=json.dumps(reflection.raw, ensure_ascii=False, indent=2),
            playbook=playbook.as_prompt() or "(empty playbook)",
            question_context=task,
        )
        prompt = curator_prompt
        last_error: Optional[Exception] = None


        for attempt in range(self.max_retries):
            self.logger.debug(
                "Curator attempt %d/%d for task snippet=%s",
                attempt + 1,
                self.max_retries,
                task[:80].replace("\n", " "),
            )
            messages = [
                {"role": "system", "content": REFLECTOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            response = model.query(messages=messages)
            try:
                data = safe_json_loads(response.choices[0].message.content)
                delta = DeltaBatch.from_json(data)
                self.logger.info(
                    "Curator produced delta with %d operations.",
                    len(delta.operations),
                )
                self.logger.debug(f"Raw curator output: {data}")
                return CuratorOutput(delta=delta, raw=data)
            except ValueError as err:
                last_error = err
                if attempt + 1 >= self.max_retries:
                    break
                self.logger.warning(
                    "Curator returned invalid JSON (attempt %d/%d). Retrying.",
                    attempt + 1,
                    self.max_retries,
                )
                prompt = (
                    curator_prompt + "\n\nPlease output valid JSON, escape double quotes, "
                    "and do not include any additional explanatory text."
                )
        self.logger.error("Curator failed to produce valid JSON after retries.")
        raise RuntimeError("Curator failed to produce valid JSON.") from last_error

    @retry(n_attempts=5)
    def _main_update_code(self, task: str, generator_output: str, result: str, ground_truth: str, feedback: str, previous_playbook: Playbook, model: Model) -> Playbook:
        reflector_output = self._reflector_analysis(
            task=task,
            generator_output=generator_output,
            result=result,
            ground_truth=ground_truth,
            feedback=feedback,
            previous_playbook=previous_playbook,
            model=model,
        )

        curator_output = self._curator_analysis(
            reflection=reflector_output,
            playbook=previous_playbook,
            task=task,
            model=model,
        )
        previous_playbook.apply_delta(curator_output.delta)
        return previous_playbook

    def update_plan(
        self,
        instance: Instance,
        traces: List[dict],
        result: str,
        base_dir: Path,
        model: Model,
        **kwargs: Any,
    ) -> None:
        
        task = instance.task
        ground_truth = instance.patch
        self.logger.info("Updating plan for instance %s.", instance.instance_id)
        self.logger.debug("Received %d trace messages.", len(traces))

        feedback = instance.solve(result, base_dir, run_id=0)

        if feedback:
            feedback = "All tests passed."
            self.logger.info(
                "Instance %s tests succeeded. Proceeding with reflector/curator.",
                instance.instance_id,
            )
        else:
            feedback = "Some tests failed. The patch did not fix the issue."
            self.logger.warning(
                "Instance %s tests failed. Capturing failure context.",
                instance.instance_id,
            )

        # Remove useless files from the diff
        result = DiffFile.from_text(result).get_cleaned_diff()
        self.logger.debug(f"Cleaned diff {result}")

        previous_playbook = (
            self._load_playbook(repo=instance.repo)
        )  # when updating plan, always load latest playbook
        self.logger.debug(
            "Previous playbook stats before update: %s",
            previous_playbook.stats(),
        )
        generator_output = parse_traces_to_md(
            traces, include_system=False, markdown=False
        )
        self.logger.debug(
            "Parsed generator output length=%d characters.",
            len(generator_output),
        )

        previous_playbook = self._main_update_code(
            task=task,
            generator_output=generator_output,
            result=result,
            ground_truth=ground_truth,
            feedback=feedback,
            previous_playbook=previous_playbook,
            model=model,
        )

        self.logger.info(
            "Applied curator delta to playbook for instance %s.",
            instance.instance_id,
        )
        self.logger.debug(
            "Updated playbook stats after applying delta: %s",
            previous_playbook.stats(),
        )

        self._store_playbook(previous_playbook, repo=instance.repo)

    
    def _store_playbook(self, playbook: Playbook, repo: str) -> None:

        repo = repo.replace("/", "_")

        with _PLAN_FILE_LOCK:
            self.logger.debug("Persisting playbook to storage.")
            storage_dir = self._get_storage_path()
            playbook_path = storage_dir / f"playbook_{repo}.json"
            playbook.save_to_file(playbook_path)

            self.logger.info(f"Stored playbook at {playbook_path}")


            playbook_history_dir = storage_dir / "playbook_history"
            playbook_history_dir.mkdir(parents=True, exist_ok=True)
            history_index = 1
            # Find the next available history index
            while (playbook_history_dir / f"playbook_{history_index}_{repo}.json").exists():
                history_index += 1
            history_path = playbook_history_dir / f"playbook_{history_index}_{repo}.json"
            playbook.save_to_file(history_path)
            self.logger.info(f"Stored playbook history at {history_path}")
            self.logger.debug(
                "Playbook stats after storage: %s",
                playbook.stats(),
            )

    def _load_playbook(self, playbook_history: int = None, repo: str = None) -> Playbook:

        repo = repo.replace("/", "_")

        storage_dir = self._get_storage_path()
        if playbook_history is not None:
            playbook_path = (
                storage_dir / "playbook_history" / f"playbook_{playbook_history}_{repo}.json"
            )
            self.logger.info(
                "Loading playbook history index %s from %s.",
                playbook_history,
                playbook_path,
            )
        else:
            playbook_path = storage_dir / f"playbook_{repo}.json"
            self.logger.debug("Loading latest playbook from %s.", playbook_path)

        if not playbook_path.exists():
            self.logger.error(
                f"No playbook_{repo}.json found in {storage_dir}. Using empty playbook."
            )
            return Playbook()

        playbook = Playbook.load_from_file(playbook_path)
        self.logger.debug(
            "Loaded playbook stats: %s",
            playbook.stats(),
        )
        return playbook

    def _get_storage_path(self) -> Path:
        storage_dir = Path(self.config.storage_dir)
        storage_dir = storage_dir / "ace_playbook" / self.config.plan_model
        storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Resolved storage path: %s.", storage_dir)

        return storage_dir
