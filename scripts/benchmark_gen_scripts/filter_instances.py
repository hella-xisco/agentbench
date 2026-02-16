import concurrent.futures
import json
from pathlib import Path
from typing import Any
from tqdm import tqdm
import threading
import fire

from benchmark_generator.config import (
    FILTERED_INSTANCES_DIR_NAME,
    INSTANCES_DIR_NAME,
    DEFAULT_OUTPUT_DIR,
    maybe_get_repo_config,
)
from benchmark_generator.pull_request import PullRequestInstance
from agentbench.utils.log import logger
from agentbench.model import get_model

from configs import ALL_MODEL_CONFIGS, ALL_GENERATOR_CONFIGS


_OUTPUT_FILE_LOCK = threading.Lock()

def verify_instance(
    config: dict,
    pr: PullRequestInstance,
    docker_image: str,
) -> tuple[bool, PullRequestInstance]:
    """Return True if an instance is acceptable, False otherwise."""

    try:
        instance_obj =  pr.to_agentbench(
            docker_image=docker_image,
        )
        
        test_before_patch = instance_obj.solve(
            "", Path("/tmp"), run_id=0, run_repo_test=False
        )
    
        if test_before_patch:
            logger.warning(
                "Rejecting instance %s: tests do not fail before applying the patch.",
                instance_obj.instance_id,
            )
            return False, pr

        test_after_patch = instance_obj.solve(
            pr.clean_pr_patch, Path("/tmp"), run_id=0, run_repo_test=False
        )
        logger.info(f"Instance {instance_obj.instance_id}: test before patch: {test_before_patch}, test after patch: {test_after_patch}")

        
        if not test_after_patch:
            logger.warning(
                "Rejecting instance %s: tests do not pass after applying the patch.",
                instance_obj.instance_id,
            )
            return False, pr

        # Store the repo test after patch results
        pr.repo_test_after_pr_patch = instance_obj._run_repo_test_only(instance_obj.setup({}))

        # Check that at least one test passed (otherwise, it is likely that it is ill-set up)
        if not any(pr.repo_test_after_pr_patch.values()):
            logger.warning(
                "Rejecting instance %s: no repo tests passed after applying the patch.",
                instance_obj.instance_id,
            )
            return False, pr

    except Exception as e:
        logger.error(f"Error while verifying instance {pr.number}: {e}")
        return False, pr
    
    return True, pr



def filter_instances(
    config: dict[str, Any],
    docker_image: str,
    input_dir: Path,
    output_dir: Path,
    force: bool,
    workers: int,
    limit: int,
    pr_numbers: list[int] | None = None,
    model_port: int = 18081,
):

    # Fetch PRs from input
    pr_files = sorted(input_dir.glob("*.json"))

    if pr_numbers:
        normalized_numbers: list[int] = []
        for n in pr_numbers:
            try:
                n_int = int(n)
            except (TypeError, ValueError):
                continue
            if n_int not in normalized_numbers:
                normalized_numbers.append(n_int)
        by_number = {int(p.stem): p for p in pr_files}
        pr_files = [by_number[n] for n in normalized_numbers if n in by_number]

    # Fetch already outputted PRs
    already_processed = sorted(output_dir.glob("*.json"))

    if not force:
        processed_pr_numbers = {
            int(p.stem) for p in already_processed
        }
        pr_files = [
            p for p in pr_files if int(p.stem) not in processed_pr_numbers
        ]
    
    # Load PR instances
    pr_instances: list[PullRequestInstance] = []
    for pr_file in pr_files:
        
        with pr_file.open("r", encoding="utf-8") as f:
            pr_data = json.load(f)
            pr_instance = PullRequestInstance.from_dict(pr_data)

            pr_instances.append(pr_instance)
            if limit > 0 and len(pr_instances) >= limit:
                break

    logger.info(f"Filtering {len(pr_instances)} instances from {input_dir} to {output_dir}.")

    if not pr_instances:
        logger.info("No instances to filter.")
        return

    # Start the model server
    model = get_model(config["model"])
    model.update_port(model_port)  # Use a different port to avoid conflicts 
    model.serve()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for pr in pr_instances:
            futures.append(
                executor.submit(
                    verify_instance,
                    config,
                    pr,
                    docker_image,
                )
            )

        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Filtering instances",
        ):
            is_accepted, processed_pr = future.result()
            if is_accepted:
                output_path = output_dir / f"{processed_pr.number}.json"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with _OUTPUT_FILE_LOCK:
                    with output_path.open("w", encoding="utf-8") as f:
                        json.dump(processed_pr.to_dict(), f, indent=2)

    # Stop the model server
    model.stop()


def main(
    model: str,
    generator: str,
    repo: str,
    output: str = DEFAULT_OUTPUT_DIR,
    limit: int = -1,
    workers: int = 4,
    repo_config: str | None = None,
    pr_numbers: list[int] | None = None,
    model_port: int = 18081,
) -> dict[str, Any]:
    config_entry = maybe_get_repo_config(repo_config or repo)
    if config_entry:
        docker_image = config_entry.docker_image

    base_output = Path(output) / config_entry.slug

    input_dir = base_output / INSTANCES_DIR_NAME
    output_dir = base_output / FILTERED_INSTANCES_DIR_NAME

    config = {
        "model": ALL_MODEL_CONFIGS[model],
        "generator": ALL_GENERATOR_CONFIGS[generator],
    }

    if "model_class" not in config["model"]:
        config["model"]["model_class"] = "litellm_server"

    filter_instances(
        config=config,
        docker_image=docker_image,
        input_dir=input_dir,
        output_dir=output_dir,
        force=False,
        workers=workers,
        limit=limit,
        pr_numbers=pr_numbers,
        model_port=model_port,
    )
    

if __name__ == "__main__":
    fire.Fire(main)
