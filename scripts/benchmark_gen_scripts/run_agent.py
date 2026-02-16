import concurrent.futures
from tqdm import tqdm
import threading
from pathlib import Path
import json
import fire

from benchmark_generator.config import (
    DEFAULT_OUTPUT_DIR,
    PR_CACHE_DIR_NAME,
    TRIAGE_RESULTS_DIR_NAME,
    SETUP_RESULTS_DIR_NAME,
    INSTANCES_DIR_NAME,
    STATEMENTS_DIR_NAME,
    maybe_get_repo_config,
)

from agentbench.utils.log import logger
from agentbench.generators import get_generator
from agentbench.model import get_model
from agentbench.environments.docker import DockerEnvironment

from configs import (
    ALL_GENERATOR_CONFIGS,
    ALL_MODEL_CONFIGS,
)


from benchmark_generator.agents.triage_agent import TriageAgent
from benchmark_generator.agents.statement_agent import StatementAgent
from benchmark_generator.agents.instance_agent import InstanceAgent
from benchmark_generator.agents.setup_agent import SetupAgent

from benchmark_generator.pull_request import PullRequestInstance

_OUTPUT_FILE_LOCK = threading.Lock()

def default_filter(pr: PullRequestInstance) -> bool:
    """Default filter that accepts all PRs."""
    return True

def setup_filter(pr: PullRequestInstance) -> bool:
    """Filter to select PRs that were marked as suitable during triage."""
    return pr.is_suitable

def statement_filter(pr: PullRequestInstance) -> bool:
    """Filter to select PRs that were marked as suitable during triage."""
    return pr.setup_commands is not None and pr.repo_test_commands is not None and pr.repo_test_runner is not None

def instance_filter(pr: PullRequestInstance) -> bool:
    """Filter to select PRs that have generated statements."""
    return pr.problem_description is not None


# We map the agent type to the: Agents, PR input dir, PR output dir
AGENT_MAPPER = {
    "triage": (TriageAgent, PR_CACHE_DIR_NAME, TRIAGE_RESULTS_DIR_NAME, default_filter),
    "setup": (SetupAgent, TRIAGE_RESULTS_DIR_NAME, SETUP_RESULTS_DIR_NAME, setup_filter),
    "statement": (StatementAgent, SETUP_RESULTS_DIR_NAME, STATEMENTS_DIR_NAME, statement_filter),
    "instance": (InstanceAgent, STATEMENTS_DIR_NAME, INSTANCES_DIR_NAME, instance_filter),
}

def _run_agent_on_pr(
    config: dict,
    pr: PullRequestInstance,
    docker_image: str,
    output_path: Path,
    agent_type: str,
    model_port: int,
) -> PullRequestInstance:
    model_cfg = config["model"]
    generator_cfg = config["generator"]

    model = get_model(model_cfg)
    model.update_port(model_port) 

    env = DockerEnvironment(image=docker_image, timeout=1800*4, cwd="/testbed")
    generator = get_generator(generator_cfg, model=model, env=env)

    agent_class = AGENT_MAPPER[agent_type][0]
    agent = agent_class(model=model, env=env, generator=generator)

    try:
        processed_pr = agent.process_pr(pr, output_path=output_path)
    except Exception as e:
        logger.error(f"Error processing PR #{pr.number} with agent {agent_type}: {e}")
        processed_pr = pr  # Return the original PR instance on error


    return processed_pr


def run_agent_on_prs(
    config: dict,
    repo: str,
    docker_image: str,
    output: Path,
    limit: int,
    force: bool,
    workers: int,
    agent_type: str,
    model_port: int = 18081,
    pr_numbers: list[int] | None = None,
) -> None:

    AgentClass, input_dir_name, output_dir_name, filter = AGENT_MAPPER[agent_type]

    # Fetch PRs from input
    input_pr_dir = output / input_dir_name
    pr_files = sorted(input_pr_dir.glob("*.json"))

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
    output_results_dir = output / output_dir_name
    already_processed = sorted(output_results_dir.glob("*.json"))

    if not force:
        processed_pr_numbers = {
            int(p.stem) for p in already_processed
        }
        pr_files = [
            p for p in pr_files if int(p.stem) not in processed_pr_numbers
        ]

    # Load (valid) PR instances
    pr_instances: list[PullRequestInstance] = []
    for pr_file in pr_files:
        
        with pr_file.open("r", encoding="utf-8") as f:
            pr_data = json.load(f)
            pr_instance = PullRequestInstance.from_dict(pr_data)

            if filter(pr_instance):
                pr_instances.append(pr_instance)
                if limit > 0 and len(pr_instances) >= limit:
                    break

    if not pr_instances:
        logger.info(
            "No PRs to process for agent %s (repo %s).", agent_type, repo
        )
        return

    # Start the model server
    model = get_model(config["model"])
    model.update_port(model_port)  # Use a different port to avoid conflicts 
    model.serve()

    logger.info(f"Processing {len(pr_instances)} PRs from repo {repo} with agent {agent_type}.")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for pr in pr_instances:
            futures.append(
                executor.submit(
                    _run_agent_on_pr,
                    config,
                    pr,
                    docker_image,
                    output,
                    agent_type,
                    model_port,
                )
            )

        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc=f"Processing PRs with agent {agent_type}",
        ):
            processed_pr = future.result()
            output_path = output_results_dir / f"{processed_pr.number}.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with _OUTPUT_FILE_LOCK:
                with output_path.open("w", encoding="utf-8") as f:
                    json.dump(processed_pr.to_dict(), f, indent=2)

    # Stop the model server
    model.stop()

def main(
    agent_type: str,
    model: str,
    generator: str,
    repo: str | None = None,
    docker_image: str | None = None,
    output: str = DEFAULT_OUTPUT_DIR,
    limit: int = 20,
    force: bool = False,
    workers: int = 8,
    repo_config: str | None = None,
    model_port: int = 18081,
    pr_numbers: list[int] | None = None,
) -> None:
    config_entry = maybe_get_repo_config(repo_config or repo)
    if config_entry:
        repo = repo or config_entry.repo
        docker_image = docker_image or config_entry.docker_image
        if output == DEFAULT_OUTPUT_DIR or not output:
            output = config_entry.output_dir

    if not repo:
        raise ValueError("You must provide a repository via --repo or --repo-config.")
    if not docker_image:
        raise ValueError("You must provide --docker_image or configure one in repo_config.")

    if isinstance(output, str):
        output = Path(output)
    output = output / repo.replace("/", "_")
    output.mkdir(parents=True, exist_ok=True)

    config = {
        "model": ALL_MODEL_CONFIGS[model],
        "generator": ALL_GENERATOR_CONFIGS[generator],
    }

    if "model_class" not in config["model"]:
        config["model"]["model_class"] = "litellm_server"

    run_agent_on_prs(
        config=config,
        repo=repo,
        docker_image=docker_image,
        output=output,
        limit=limit,
        force=force,
        workers=workers,
        agent_type=agent_type,
        model_port=model_port,
        pr_numbers=pr_numbers,
    )


if __name__ == "__main__":
    fire.Fire(main)
