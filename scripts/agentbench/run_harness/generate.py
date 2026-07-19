import concurrent.futures  
from collections import OrderedDict
from pathlib import Path
import json
import logging
import threading
import time
import traceback
from typing import Any, Callable
from copy import deepcopy

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from tqdm import tqdm
import fire

from agentbench import Instance
from agentbench.generators.cli_agent import APIError
from agentbench.model import get_model
from agentbench.planners import get_planner
from agentbench.generators import get_generator
from agentbench.benchmarks import get_benchmark
from agentbench.utils.log import add_file_handler, logger
from agentbench.utils.io_utils import save_traj, _compute_run_directory

from configs import (
    ALL_GENERATOR_CONFIGS,
    ALL_MODEL_CONFIGS,
    ALL_PLAN_CONFIGS,
    ALL_BENCHMARK_CONFIGS,
    is_plan_training_sequential
)

_OUTPUT_FILE_LOCK = threading.Lock()
_INSTANCE_METRICS_LOCK = threading.Lock()

MAX_RETRIES = 10
COST_UPDATE_INTERVAL_S = 15.0

# Global instance metrics used by the rich dashboard.
INSTANCE_METRICS: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_INSTANCE_METRICS_MAX_ROWS: int | None = None

def _format_cost(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"${value:.4f}"
    return "-"

# Extend these mappings to add new metrics to the rich dashboard.
INSTANCE_METRIC_COLUMNS = ["status", "cost", "runtime"]
INSTANCE_METRIC_LABELS = {
    "status": "Status",
    "cost": "Cost ($)",
    "runtime": "Runtime",
}
INSTANCE_METRIC_JUSTIFY = {"cost": "right", "runtime": "right"}
INSTANCE_METRIC_FORMATTERS: dict[str, Callable[[Any], str]] = {
    "cost": _format_cost,
}
INSTANCE_METRIC_DEFAULTS = {
    "status": "Queued",
    "cost": 0.0,
    "done": False,
    "started_at": None,
    "ended_at": None,
}

def set_instance_metrics_max_rows(max_rows: int | None) -> None:
    global _INSTANCE_METRICS_MAX_ROWS
    _INSTANCE_METRICS_MAX_ROWS = max_rows

def reset_instance_metrics() -> None:
    with _INSTANCE_METRICS_LOCK:
        INSTANCE_METRICS.clear()

def _select_instance_metrics_locked() -> list[tuple[str, dict[str, Any]]]:
    rows = list(INSTANCE_METRICS.items())
    max_rows = _INSTANCE_METRICS_MAX_ROWS
    if max_rows is None or len(rows) <= max_rows:
        return [(instance_id, dict(metrics)) for instance_id, metrics in rows]

    running_ids = [instance_id for instance_id, metrics in rows if not metrics.get("done")]
    if len(running_ids) >= max_rows:
        keep_ids = set(running_ids[-max_rows:])
    else:
        done_ids = [instance_id for instance_id, metrics in rows if metrics.get("done")]
        keep_ids = set(running_ids)
        remaining = max_rows - len(keep_ids)
        if remaining > 0:
            keep_ids.update(done_ids[-remaining:])

    return [
        (instance_id, dict(metrics))
        for instance_id, metrics in rows
        if instance_id in keep_ids
    ]

def update_instance_metrics(instance_id: str, **updates: Any) -> None:
    with _INSTANCE_METRICS_LOCK:
        metrics = INSTANCE_METRICS.setdefault(instance_id, dict(INSTANCE_METRIC_DEFAULTS))
        metrics.update(updates)

def get_instance_metrics_snapshot() -> list[tuple[str, dict[str, Any]]]:
    with _INSTANCE_METRICS_LOCK:
        return _select_instance_metrics_locked()

def get_instance_metrics_stats() -> tuple[int, float]:
    with _INSTANCE_METRICS_LOCK:
        running = 0
        total_cost = 0.0
        for metrics in INSTANCE_METRICS.values():
            if not metrics.get("done"):
                running += 1
            cost = metrics.get("cost")
            if isinstance(cost, (int, float)):
                total_cost += cost
        return running, total_cost

def _get_instance_cost(model: Any, generator: Any | None) -> float | None:
    if generator is not None and getattr(generator, "model", None) is not None:
        return getattr(generator.model, "cost", None)
    return getattr(model, "cost", None)

def _refresh_instance_cost(model: Any, generator: Any | None) -> float | None:
    get_cost = getattr(model, "get_cost", None)
    get_traces_path = getattr(model, "get_traces_path", None)
    if callable(get_cost) and callable(get_traces_path):
        try:
            traces_path = get_traces_path()
            if traces_path and Path(traces_path).exists():
                return get_cost()
        except Exception:
            pass
    return _get_instance_cost(model, generator)

def _start_cost_updater(
    instance_id: str,
    model: Any,
    get_generator: Callable[[], Any | None],
    stop_event: threading.Event,
) -> threading.Thread:
    def _loop() -> None:
        while not stop_event.wait(COST_UPDATE_INTERVAL_S):
            cost = _refresh_instance_cost(model, get_generator())
            update_instance_metrics(instance_id, cost=cost)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread

def _format_elapsed(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def _format_total_cost(value: float) -> str:
    return f"${value:07.2f}"

def _format_runtime(metrics: dict[str, Any]) -> str:
    started_at = metrics.get("started_at")
    if not isinstance(started_at, (int, float)):
        return "-"
    ended_at = metrics.get("ended_at")
    if isinstance(ended_at, (int, float)):
        elapsed = ended_at - started_at
    else:
        elapsed = time.monotonic() - started_at
    if elapsed < 0:
        elapsed = 0
    return _format_elapsed(elapsed)

def _format_metric_value(key: str, metrics: dict[str, Any]) -> str:
    if key == "runtime":
        return _format_runtime(metrics)
    formatter = INSTANCE_METRIC_FORMATTERS.get(key)
    value = metrics.get(key)
    if formatter:
        return formatter(value)
    if value is None:
        return "-"
    return str(value)

class RichProgressDashboard:
    def __init__(self, *, total: int, workers: int, dataset_name: str | None = None) -> None:
        self.total = total
        self.completed = 0
        self.workers = workers
        label = " Agentbench"
        if dataset_name:
            label = f"{label} | {dataset_name}"
        self.spinner = Spinner("dots", text=label, style="bold cyan")
        self.start_time = time.monotonic()

    def mark_completed(self) -> None:
        self.completed += 1

    def __rich__(self) -> Panel:
        rows = get_instance_metrics_snapshot()
        running, total_cost = get_instance_metrics_stats()
        queued = max(self.total - self.completed - running, 0)
        header = Table.grid(expand=True)
        header.add_column(ratio=1)
        header.add_column(justify="right")
        elapsed = _format_elapsed(time.monotonic() - self.start_time)
        header.add_row(
            self.spinner,
            (
                f"done {self.completed}/{self.total} | running {running} | queued {queued} | "
                f"{elapsed} | cost {_format_total_cost(total_cost)}"
            ),
        )

        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Instance", no_wrap=True)
        for key in INSTANCE_METRIC_COLUMNS:
            table.add_column(
                INSTANCE_METRIC_LABELS.get(key, key),
                justify=INSTANCE_METRIC_JUSTIFY.get(key, "left"),
            )

        if rows:
            for instance_id, metrics in rows:
                row = [instance_id]
                for key in INSTANCE_METRIC_COLUMNS:
                    row.append(_format_metric_value(key, metrics))
                table.add_row(*row)
        else:
            empty_row = ["-"] + ["Waiting"] + ["-"] * (len(INSTANCE_METRIC_COLUMNS) - 1)
            table.add_row(*empty_row)

        filler_rows = max(self.workers - len(rows), 0)
        for _ in range(filler_rows):
            filler = ["-"] + ["Idle"] + ["-"] * (len(INSTANCE_METRIC_COLUMNS) - 1)
            table.add_row(*filler)

        return Panel(Group(header, table), padding=(1, 1), border_style="cyan")

def _attach_rich_console(console: Console) -> None:
    for handler in logger.handlers:
        if isinstance(handler, RichHandler):
            handler.console = console

def update_preds_file(
    output_path: Path,
    instance_id: str,
    model_name: str,
    result: str,
    wall_time_seconds: float | None = None,
    cost_usd: float | None = None,
):
    """Update the output JSON file with results from a single instance."""
    with _OUTPUT_FILE_LOCK:
        output_data = {}
        if output_path.exists():
            output_data = json.loads(output_path.read_text())
        entry: dict[str, Any] = {
            "model_name_or_path": model_name,
            "instance_id": instance_id,
            "model_patch": result,
        }
        if wall_time_seconds is not None:
            entry["wall_time_seconds"] = wall_time_seconds
        if cost_usd is not None:
            entry["cost_usd"] = cost_usd
        output_data[instance_id] = entry
        output_path.write_text(json.dumps(output_data, indent=2))

def process_instance(
    instance: Instance,
    output_dir: Path,
    config: dict,
    train_plan: bool = False,
    n_tries: int = 1,
    setup_repo: bool = True,
    hard_task: bool = False,
    remove_docs: bool = False,
) -> None:
    """Process a single SWEBench instance."""

    if hard_task:
        instance.harden_task()

    instance_dir = instance.get_dir(output_dir)

    model = get_model(config=config.get("model", {}))
    planner = get_planner(planner_config=config.get("planner", {}))

    generator = None
    exit_status = "NotStarted"
    result = ""
    extra_info = {
        "generator_name": config.get("generator_name"),
        "plan_generator_name": config.get("plan_generator_name"),
    }

    start_time = time.monotonic()
    update_instance_metrics(
        instance.instance_id,
        status="Starting",
        cost=0.0,
        done=False,
        started_at=start_time,
        ended_at=None,
    )
    cost_stop_event = threading.Event()
    cost_thread = _start_cost_updater(
        instance.instance_id,
        model,
        lambda: generator,
        cost_stop_event,
    )

    try:
        for _ in range(n_tries):
            # Load the environment
            env = instance.setup(env_config=config.get("environment", {}), setup_repo=setup_repo)

            # Exectute the plan (i.e., write AGENTS.md)
            update_instance_metrics(
                instance.instance_id,
                status="Planning",
                cost=_get_instance_cost(model, generator),
                done=False,
            )
            planner.plan(env=env, model=model, instance=instance)

            if remove_docs:
                instance.remove_docs(env)

            # Reset git history to prevent cheating
            # For swebench, the docker image should already be clean
            if hasattr(instance, "_clean_git_history"):
                update_instance_metrics(
                    instance.instance_id,
                    status="Cleaning Git History",
                    cost=_get_instance_cost(model, generator),
                    done=False,
                )
                instance._clean_git_history(env)

            # Commit all changes so far to have a clean state
            env.execute("git add .")
            env.execute('git commit -m "Prepare environment for execution"')

            # Solve the instance itself
            generator = get_generator(
                generator_config=config.get("generator", {}), model=model, env=env
            )
            update_instance_metrics(
                instance.instance_id,
                status="Running",
                cost=_get_instance_cost(model, generator),
                done=False,
            )
            retry = True
            n_retries = 0
            while retry and n_retries < MAX_RETRIES:
                try:
                    exit_status, result = generator.run(instance.task)
                    retry = False
                except APIError as api_err:
                    logger.error(f"API error encountered: {api_err}")
                    model.delete_traces()
                    retry = True
                    n_retries += 1
                    update_instance_metrics(
                        instance.instance_id,
                        status=f"Retry {n_retries}/{MAX_RETRIES}",
                        cost=_get_instance_cost(model, generator),
                        done=False,
                    )
                    if n_retries >= MAX_RETRIES:
                        raise api_err
                    logger.info(f"Retrying... Attempt {n_retries+1}/{MAX_RETRIES}")

            if train_plan:
                logger.info(f"Training planner on instance {instance.instance_id}...")
                planner.update_plan(instance=instance, traces=generator.messages, result=result, base_dir=instance_dir, model=model)

            logger.info(f"Instance {instance.instance_id} finished with status {exit_status}")
            end_time = time.monotonic()
            final_cost = _get_instance_cost(model, generator) or 0.0
            extra_info.update({
                "wall_time_seconds": round(end_time - start_time, 2),
                "cost_usd": final_cost,
            })
            save_traj(
                generator=generator,
                path=instance_dir / f"{instance.instance_id}.traj.json",
                exit_status=exit_status,
                result=result,
                extra_info=extra_info,
                instance_id=instance.instance_id,
            )
            update_preds_file(
                output_dir / "preds.json",
                instance.instance_id,
                model.config.model_name,
                result,
                wall_time_seconds=extra_info.get("wall_time_seconds"),
                cost_usd=extra_info.get("cost_usd"),
            )

            update_instance_metrics(
                instance.instance_id,
                status=exit_status,
                cost=_get_instance_cost(model, generator),
                done=True,
                ended_at=time.monotonic(),
            )
            del env  # Ensure environment is cleaned up

    except Exception as e:
        logger.error(f"Error processing instance {instance.instance_id}: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        end_time = time.monotonic()
        extra_info = {
            "generator_name": config.get("generator_name"),
            "plan_generator_name": config.get("plan_generator_name"),
            "traceback": traceback.format_exc(),
            "wall_time_seconds": round(end_time - start_time, 2),
            "cost_usd": _get_instance_cost(model, generator) or 0.0,
        }
        update_instance_metrics(
            instance.instance_id,
            status=exit_status,
            cost=_get_instance_cost(model, generator),
            done=True,
            error=result,
            ended_at=time.monotonic(),
        )
    finally:
        cost_stop_event.set()
        cost_thread.join(timeout=2)


def generate_baseline(
    output: Path | str,
    workers: int,
    config: dict,
    redo_existing: bool = False,
    train_plan: bool = False,
    setup_repo: bool = True,
    hard_task: bool = False,
    remove_docs: bool = False,
    n_tries: int = 1,
    progress: str = "tqdm",
) -> None:

    if isinstance(output, str):
        output_path = Path(output)
    else:
        output_path = output
    output_path.mkdir(parents=True, exist_ok=True)
    
    add_file_handler(output_path / "agentbench.log")
    logger.info(f"Results will be saved to {output_path}")

    progress_mode = (progress or "tqdm").lower()
    if progress_mode not in ("tqdm", "rich"):
        raise ValueError(f"Unknown progress mode: {progress}")
    reset_instance_metrics()
    set_instance_metrics_max_rows(workers if progress_mode == "rich" else None)
    dataset_name = None
    if isinstance(config, dict):
        dataset_name = config.get("benchmark", {}).get("dataset_name")

    # Loading the benchmark
    benchmark = get_benchmark(config["benchmark"])
    instances = benchmark.get_instances()
    if not redo_existing and (output_path / "preds.json").exists():
        existing_instances = list(
            json.loads((output_path / "preds.json").read_text()).keys()
        )
        logger.info(f"Skipping {len(existing_instances)} existing instances")
        instances = [
            instance
            for instance in instances
            if instance.instance_id not in existing_instances
        ]
    logger.info(f"Running on {len(instances)} instances...")

    model_server = get_model(config["model"])
    model_server.serve()

    def process_futures_tqdm(future_to_id: dict[concurrent.futures.Future, str]) -> None:
        total = len(future_to_id)
        with tqdm(total=total, desc="Processing", unit="task") as pbar:
            for future in concurrent.futures.as_completed(future_to_id):
                try:
                    future.result()
                except concurrent.futures.CancelledError:
                    instance_id = future_to_id[future]
                    update_instance_metrics(instance_id, status="Cancelled", done=True)
                except Exception as e:
                    instance_id = future_to_id[future]
                    logger.error(
                        f"Error in future for instance {instance_id}: {e}",
                        exc_info=True,
                    )
                finally:
                    pbar.update(1)

    def process_futures_rich(future_to_id: dict[concurrent.futures.Future, str]) -> None:
        total = len(future_to_id)
        console = Console()
        _attach_rich_console(console)
        dashboard = RichProgressDashboard(
            total=total,
            workers=workers,
            dataset_name=dataset_name,
        )
        with Live(
            dashboard,
            console=console,
            refresh_per_second=6,
            transient=False,
            redirect_stdout=True,
            redirect_stderr=True,
        ):
            for future in concurrent.futures.as_completed(future_to_id):
                try:
                    future.result()
                except concurrent.futures.CancelledError:
                    instance_id = future_to_id[future]
                    update_instance_metrics(instance_id, status="Cancelled", done=True)
                except Exception as e:
                    instance_id = future_to_id[future]
                    logger.error(
                        f"Error in future for instance {instance_id}: {e}",
                        exc_info=True,
                    )
                finally:
                    dashboard.mark_completed()

    def process_futures(future_to_id: dict[concurrent.futures.Future, str]) -> None:
        if progress_mode == "rich":
            process_futures_rich(future_to_id)
        else:
            process_futures_tqdm(future_to_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_id = {
            executor.submit(
                process_instance, instance, output_path, config, train_plan, n_tries, setup_repo=setup_repo, hard_task=hard_task, remove_docs=remove_docs
            ): instance.instance_id
            for instance in instances
        }

        try:
            process_futures(future_to_id)
        except KeyboardInterrupt:
            logger.info(
                "Cancelling all pending jobs. Press ^C again to exit immediately."
            )
            for f in future_to_id:
                if not f.running() and not f.done():
                    f.cancel()
            remaining = {f: iid for f, iid in future_to_id.items() if not f.done()}
            process_futures(remaining)

    model_server.stop()



def main(
    plan_type: str,
    exec_model: str,
    generator: str,
    run_id: int = 0,
    plan_model: str | None = None,
    plan_generator: str | None = None,
    output_dir: str = "output",
    dataset_name: str = "nmuendler/SWE-bench_Verified_shuffle",
    benchmark: str = "swebench",
    filter_spec: str = "",
    slice_spec: str = "0:100",
    split: str = "test",
    workers: int = 2,
    progress: str = "rich",
    plan_args: dict = {},
    train_plan: bool = False,
    continuous_training: bool = False,
    port: int = 18080,
    setup_repo: bool = True,
    hard_task: bool = False,
    remove_docs: bool = False,
    exec_model_api_base: str | None = None,
    debug: bool = False,
) -> None:

    if remove_docs:
        logger.info("Documentation files will be removed from the repositories.")

    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode is ON")
    
    if isinstance(plan_args, str):
        import yaml
        plan_args = yaml.safe_load(plan_args)

    if plan_args is None:
        plan_args = {}

    output_path = Path(output_dir)
    if isinstance(train_plan, str):
        train_plan = train_plan.lower() in ("yes", "true", "t", "1")

    if train_plan or continuous_training:
        if is_plan_training_sequential(plan_type):
            if workers > 1:
                logger.error(f"Training {plan_type} is not thread-safe; setting workers to 1") 
            workers = 1  # Training plans is not thread-safe

    config = {
        "model": deepcopy(ALL_MODEL_CONFIGS[exec_model]),
        "planner": deepcopy(ALL_PLAN_CONFIGS[plan_type]),
        "generator": deepcopy(ALL_GENERATOR_CONFIGS[generator]),
        "benchmark": deepcopy(ALL_BENCHMARK_CONFIGS[benchmark]),
    }

    if "generator_config" in config["planner"]:
        if not config["planner"]["generator_config"]:
            logger.info("Copying generator config to planner config")
            config["planner"]["generator_config"] = config["generator"]
        


    # Default classes if not specified
    if "model_class" not in config["model"]:
        config["model"]["model_class"] = "litellm_server"
    if "planner_class" not in config["planner"]:
        config["planner"]["planner_class"] = "baseline_planner"
    if "generator_class" not in config["generator"]:
        config["generator"]["generator_class"] = "cli_agent"


    # If litellm_server, set the port
    if config["model"]["model_class"] == "litellm_server":
        config["model"]["port"] = port

    if exec_model_api_base is not None:
        config["model"]["api_base"] = exec_model_api_base

    # Add plan model to planner config
    if plan_model is None:
        plan_model = exec_model
    else: # We need to initialize the model server in advance + use special port to avoid conflicts
        plan_model_config = deepcopy(ALL_MODEL_CONFIGS[plan_model])
        if "model_class" not in plan_model_config:
            plan_model_config["model_class"] = "litellm_server"
        plan_model_config["port"] = port + 1 # Offset port to avoid conflicts
        logger.info(f"Starting plan model server on port {plan_model_config['port']}")
        plan_model_obj = get_model(config=plan_model_config)    
        plan_model_obj.serve()
        config["planner"]["model_config"] = plan_model_config # Update the config with the port
    config["planner"]["plan_model"] = plan_model


    # Add generator model to planner config
    if plan_generator is None:
        plan_generator = generator
    plan_generator_config = deepcopy(ALL_GENERATOR_CONFIGS[plan_generator])
    if "generator_class" not in plan_generator_config:
        plan_generator_config["generator_class"] = "cli_agent"
    config["planner"]["generator_config"] = plan_generator_config

    # Record which agent harness (generator) produced each trajectory
    config["generator_name"] = generator
    config["plan_generator_name"] = plan_generator


    if continuous_training:
        config["planner"]["storage_dir"] = f"{config['planner']['storage_dir']}/{dataset_name.replace('/', '_')}/{plan_generator}/run_{run_id}"
    else:
        config["planner"]["storage_dir"] = f"{config['planner']['storage_dir']}/{dataset_name.replace('/', '_')}/{plan_generator}"
    config["planner"].update(plan_args) # Add any additional plan args that we want to be dynamic

    main_dir = _compute_run_directory(
        output_dir=output_path,
        dataset_name=dataset_name,
        plan_type=plan_type,
        generator=generator,
        exec_model=exec_model,
        run_id=run_id,
        planner_config=config["planner"],
        kind="agentbench",
        train_plan=train_plan,
        continuous_training=continuous_training,
    )

    # Setup benchmark config
    config["benchmark"]["dataset_name"] = dataset_name
    config["benchmark"]["filter_spec"] = filter_spec
    config["benchmark"]["slice_spec"] = slice_spec

    
    main_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting benchmark with config:\n{config}\nOutput dir: {main_dir}. Setting up repo: {setup_repo}")

    train_plan = train_plan or continuous_training

    generate_baseline(
        output=main_dir,
        workers=workers,
        config=config,
        train_plan=train_plan,
        setup_repo=setup_repo,
        hard_task=hard_task,
        remove_docs=remove_docs,
        progress=progress,
    )

    if 'plan_model_obj' in locals():
        plan_model_obj.stop()  # Stop the plan model server

if __name__ == "__main__":
    fire.Fire(main)
