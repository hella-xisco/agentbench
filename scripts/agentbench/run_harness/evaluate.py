import fire
from pathlib import Path
import json
from typing import Any
from copy import deepcopy

from agentbench.benchmarks import get_benchmark
from agentbench.utils.io_utils import _compute_run_directory


from configs import (
    ALL_GENERATOR_CONFIGS,
    ALL_MODEL_CONFIGS,
    ALL_PLAN_CONFIGS,
    ALL_BENCHMARK_CONFIGS,
)


MAX_RETRIES = 10


def _compute_pr_patch_run_directory(
    *,
    output_dir: Path,
    dataset_name: str,
    kind: str,
    tag: str = "pr_patch",
) -> Path:
    dataset_segment = dataset_name.replace("/", "_")
    run_dir = output_dir / kind / dataset_segment 
    return run_dir / tag 

def main(
    plan_type: str | None = None,
    exec_model: str | None = None,
    generator: str | None = None,
    dataset_name: str = "eth-sri/agentbench",
    benchmark: str = "agentbench",
    use_pr_patch: bool = False,
    run_id: int = 0,
    plan_model: str | None = None,
    plan_generator: str | None = None,
    output_dir: str = "output",
    workers: int = 8,
    plan_args: Any = None,
) -> None:
    
    if isinstance(plan_args, str):
        import yaml
        plan_args = yaml.safe_load(plan_args)

    if plan_args is None:
        plan_args = {}

    output_path = Path(output_dir)

    storage_generator = "pr_patch" if use_pr_patch else generator

    if use_pr_patch:
        model_config = deepcopy(ALL_MODEL_CONFIGS.get(exec_model, {}))
        generator_config = deepcopy(ALL_GENERATOR_CONFIGS.get(generator, {}))
        config = {"benchmark": deepcopy(ALL_BENCHMARK_CONFIGS[benchmark])}
    else:
        model_config = deepcopy(ALL_MODEL_CONFIGS[exec_model])
        generator_config = deepcopy(ALL_GENERATOR_CONFIGS[generator])

        config = {
            "model": model_config,
            "planner": deepcopy(ALL_PLAN_CONFIGS[plan_type]),
            "generator": generator_config,
            "benchmark": deepcopy(ALL_BENCHMARK_CONFIGS[benchmark]),
        }

        if "generator_config" in config["planner"]:
            if not config["planner"]["generator_config"]:
                config["planner"]["generator_config"] = config["generator"]

        # Default classes if not specified
        if "model_class" not in config["model"]:
            config["model"]["model_class"] = "litellm_server"
        if "planner_class" not in config["planner"]:
            config["planner"]["planner_class"] = "baseline_planner"
        if "generator_class" not in config["generator"]:
            config["generator"]["generator_class"] = "cli_agent"

        # Add plan model to planner config (for logging purposes)
        if plan_model is None:
            plan_model = exec_model
        config["planner"]["plan_model"] = plan_model
        config["planner"]["storage_dir"] = (
            f"{config['planner']['storage_dir']}/{dataset_name.replace('/', '_')}/{storage_generator}"
        )
        config["planner"].update(plan_args) # Add any additional plan args that we want to be dynamic

    # Add plan model to planner config
    if plan_model is None:
        plan_model = exec_model
    else: # We need to initialize the model server in advance + use special port to avoid conflicts
        plan_model_config = deepcopy(ALL_MODEL_CONFIGS[plan_model])
        if "model_class" not in plan_model_config:
            plan_model_config["model_class"] = "litellm_server"
        config["planner"]["model_config"] = plan_model_config # Update the config with the port
    config["planner"]["plan_model"] = plan_model


    # Add generator model to planner config
    if plan_generator is None:
        plan_generator = generator
    plan_generator_config = deepcopy(ALL_GENERATOR_CONFIGS[plan_generator])
    if "generator_class" not in plan_generator_config:
        plan_generator_config["generator_class"] = "cli_agent"
    config["planner"]["generator_config"] = plan_generator_config


    if use_pr_patch:
        main_dir = _compute_pr_patch_run_directory(
            output_dir=output_path,
            dataset_name=dataset_name,
            kind="swebench",
        )
        preds_dir = _compute_pr_patch_run_directory(
            output_dir=output_path,
            dataset_name=dataset_name,
            kind="agentbench",
        )
    else:
        main_dir = _compute_run_directory(
            output_dir=output_path,
            dataset_name=dataset_name,
            plan_type=plan_type,
            generator=generator,
            exec_model=exec_model,
            run_id=run_id,
            planner_config=config["planner"],
            kind="swebench",
            train_plan=False,
        )

        preds_dir = _compute_run_directory(
            output_dir=output_path,
            dataset_name=dataset_name,
            plan_type=plan_type,
            generator=generator,
            exec_model=exec_model,
            run_id=run_id,
            planner_config=config["planner"],
            kind="agentbench",
            train_plan=False,
        )

    # Setup benchmark config
    config["benchmark"]["dataset_name"] = dataset_name
    config["benchmark"]["filter_spec"] = ""
    config["benchmark"]["slice_spec"] = None

    # Load the benchmark
    benchmark = get_benchmark(config["benchmark"])

    if use_pr_patch:
        instances = getattr(benchmark, "instances", None)
        if instances is None:
            instances = benchmark.get_instances()
        preds = {}
        for instance in instances:
            if instance.patch is None:
                raise ValueError(
                    f"Instance '{instance.instance_id}' is missing clean_pr_patch data."
                )
            preds[instance.instance_id] = {
                "model_name_or_path": "pr_patch",
                "instance_id": instance.instance_id,
                "model_patch": instance.patch,
            }
        preds_dir.mkdir(parents=True, exist_ok=True)
        preds_path = preds_dir / "preds.json"
        with open(preds_path, "w") as f:
            json.dump(preds, f, indent=2)
    else:
        # Load the predictions
        preds_path = preds_dir / "preds.json"
        if not preds_path.exists():
            raise FileNotFoundError(f"Predictions file not found at {preds_path}")
        with open(preds_path, "r") as f:
            preds = json.load(f)

    benchmark.solve(
        patch_diffs=preds,
        base_dir=main_dir,
        run_id=run_id,
        workers=workers,
    )


if __name__ == "__main__":
    fire.Fire(main)
