import csv
import json
import sys
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fire
from datasets import load_dataset
from tqdm import tqdm

from configs import ALL_PLAN_CONFIGS, ALL_MODEL_CONFIGS
from agentbench.utils.diff_file import DiffFile
from agentbench.utils.trace import Trace
from agentbench.utils.io_utils import _compute_run_directory

from agentbench.model import get_model
from agentbench import Model

@dataclass(frozen=True)
class DiffLineSummary:
    total_added: int
    total_removed: int
    lines_changed: int
    lines_added: int
    lines_removed: int
    hunks: int


IS_PLAN_LS = False


DIFF_METRICS: dict[str, Callable[[DiffLineSummary], int]] = {
    "lines_changed": lambda summary: summary.lines_changed,
    "lines_added": lambda summary: summary.lines_added,
    "lines_removed": lambda summary: summary.lines_removed,
}

PATCH_METRIC_COLUMNS = [f"patch_{name}" for name in DIFF_METRICS]
MODEL_PATCH_METRIC_COLUMNS = [f"model_patch_{name}" for name in DIFF_METRICS]

CSV_COLUMNS = [
    "plan_model",
    "exec_model",
    "plan_type",
    "plan_args",
    "run_id",
    "generator",
    "dataset_name",
    "execution_cost",
    "instance_id",
    "resolved",
    "pass_tests",
    "fail_tests",
    "difficulty",
    "patch_length",
    "num_files_changed",
    *PATCH_METRIC_COLUMNS,
    *MODEL_PATCH_METRIC_COLUMNS,
    "log_dir",
    "number_steps",
    "number_tool_calls",
    "number_errors",
    "exit_code",
    "tool_calls",
    "sys_prompt_size",
    "number_steps_first_read",
    "cost_first_read",
    "prompt_tokens_first_read",
    "completion_tokens_first_read",
    "is_plan_ls",
    "reasoning_tokens",
]

CSV_KEY_FIELDS = [
    "plan_model",
    "exec_model",
    "plan_type",
    "plan_args",
    "run_id",
    "generator",
    "dataset_name",
    "instance_id",
    "log_dir",
]

MODEL_CONFIG = dict(ALL_MODEL_CONFIGS["gpt-oss-120b-high"])
if "model_class" not in MODEL_CONFIG:
    MODEL_CONFIG["model_class"] = "litellm_server"
MODEL = get_model(MODEL_CONFIG)
MODEL.serve()


def _load_plan_args(plan_args: Any) -> dict[str, Any]:
    if isinstance(plan_args, dict):
        return plan_args
    if isinstance(plan_args, str) and plan_args.strip():
        import yaml

        loaded = yaml.safe_load(plan_args)
        if isinstance(loaded, dict):
            return loaded
        
    return {}


def _format_plan_args(plan_args: dict[str, Any]) -> str:
    try:
        return json.dumps(plan_args, sort_keys=True)
    except TypeError:
        return repr(plan_args)


def _resolve_planner_config(
    plan_type: str,
    plan_model: str | None,
    exec_model: str,
    plan_args: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    try:
        base_config = dict(ALL_PLAN_CONFIGS[plan_type])
    except KeyError as exc:  # pragma: no cover - configuration error
        raise ValueError(f"Unknown plan_type: {plan_type}") from exc

    base_config.update(plan_args)
    resolved_plan_model = plan_model or exec_model
    base_config.setdefault("plan_model", resolved_plan_model)
    return base_config, resolved_plan_model


_PATCH_HEADER_PREFIXES = (
    "diff --git ",
    "index ",
    "new file mode ",
    "deleted file mode ",
    "similarity index ",
    "rename from ",
    "rename to ",
    "Binary files ",
    "GIT binary patch",
)


def _summarize_cleaned_diff(cleaned: str) -> DiffLineSummary:
    if not cleaned:
        return DiffLineSummary(
            total_added=0,
            total_removed=0,
            lines_changed=0,
            lines_added=0,
            lines_removed=0,
            hunks=0,
        )

    total_added = 0
    total_removed = 0
    lines_changed = 0
    lines_added = 0
    lines_removed = 0
    hunks = 0
    hunk_added = 0
    hunk_removed = 0
    in_hunk = False

    def flush_hunk() -> None:
        nonlocal total_added, total_removed, lines_changed, lines_added, lines_removed
        nonlocal hunk_added, hunk_removed
        modified = min(hunk_added, hunk_removed)
        lines_changed += modified
        lines_added += hunk_added - modified
        lines_removed += hunk_removed - modified
        total_added += hunk_added
        total_removed += hunk_removed
        hunk_added = 0
        hunk_removed = 0

    for line in cleaned.splitlines():
        if line.startswith("@@"):
            if in_hunk:
                flush_hunk()
            in_hunk = True
            hunks += 1
            continue
        if line.startswith(_PATCH_HEADER_PREFIXES):
            if in_hunk:
                flush_hunk()
                in_hunk = False
            continue
        if not in_hunk:
            continue
        if line.startswith("+"):
            hunk_added += 1
        elif line.startswith("-"):
            hunk_removed += 1

    if in_hunk:
        flush_hunk()

    return DiffLineSummary(
        total_added=total_added,
        total_removed=total_removed,
        lines_changed=lines_changed,
        lines_added=lines_added,
        lines_removed=lines_removed,
        hunks=hunks,
    )


def _summarize_diff_lines(patch: str) -> DiffLineSummary:
    diff = DiffFile.from_text(patch)
    return _summarize_cleaned_diff(diff.get_cleaned_diff())


def _metric_defaults(prefix: str, default_value: int) -> dict[str, int]:
    return {f"{prefix}_{metric}": default_value for metric in DIFF_METRICS}


def _extract_patch_metrics_from_summary(
    summary: DiffLineSummary, prefix: str
) -> dict[str, int]:
    return {
        f"{prefix}_{metric}": extractor(summary)
        for metric, extractor in DIFF_METRICS.items()
    }


def _extract_patch_metrics(patch: Any, prefix: str) -> dict[str, int]:
    if not isinstance(patch, str):
        return _metric_defaults(prefix, -1)
    summary = _summarize_diff_lines(patch)
    return _extract_patch_metrics_from_summary(summary, prefix)


def _summarize_tests(tests_status: Any) -> tuple[int, int]:
    passed = 0
    failed = 0
    if isinstance(tests_status, Mapping):
        for details in tests_status.values():
            if not isinstance(details, Mapping):
                continue
            passed += len(details.get("success") or [])
            failed += len(details.get("failure") or [])
    return passed, failed


def _get_instance_value(instance: Any, key: str, default: Any = None) -> Any:
    if isinstance(instance, Mapping):
        return instance.get(key, default)
    return getattr(instance, key, default)


def _get_instance_patch(instance: Any) -> Any:
    patch = _get_instance_value(instance, "patch", None)
    if patch is None:
        if isinstance(instance, Mapping):
            patch = instance.get("clean_pr_patch")
        else:
            patch = getattr(instance, "clean_pr_patch", None)
    return patch


def _extract_report_payload(report: Any, instance_id: str) -> Mapping[str, Any]:
    if not isinstance(report, Mapping):
        return {}
    payload = report.get(instance_id)
    if isinstance(payload, Mapping):
        return payload
    if any(
        key in report
        for key in (
            "resolved",
            "tests_status",
            "model_patch",
            "repo_test_passed",
            "instance_test_passed",
        )
    ):
        return report
    return {}


def _resolve_reported_result(payload: Mapping[str, Any]) -> bool:
    resolved = payload.get("resolved")
    return bool(
        resolved
        or (
            payload.get("repo_test_passed") is not None
            and payload.get("instance_test_passed") is not None
            and bool(payload.get("repo_test_passed"))
            and bool(payload.get("instance_test_passed"))
        )
    )


def _summarize_instance_patch(
    patch: Any,
) -> tuple[dict[str, int], int, int]:
    if not isinstance(patch, str):
        return _metric_defaults("patch", -1), -1, -1
    diff = DiffFile.from_text(patch)
    cleaned_patch = diff.get_cleaned_diff()
    patch_metrics = _extract_patch_metrics_from_summary(
        _summarize_cleaned_diff(cleaned_patch), "patch"
    )
    return patch_metrics, len(cleaned_patch), len(diff)


def _summarize_trace(trace: Trace | None, gold_patch: str) -> dict[str, Any]:
    if trace is None:
        return {
            "execution_cost": 0.0,
            "number_steps": 0,
            "number_tool_calls": 0,
            "number_errors": 0,
            "exit_code": {},
            "tool_calls": set(),
            "sys_prompt_size": 0,
        }

    gold_patch = DiffFile.from_text(gold_patch, clean_diff=False)

    result: dict[str, Any] = {"execution_cost": 0.0, "number_steps": 0, "number_tool_calls": 0}
    result["execution_cost"] = trace.get_cost()
    result["number_steps"] = sum(
        1 for message in trace.messages if "assistant" in (message.get("role") or "")
    )
    tool_call_count = len(trace.tool_uses)
    if tool_call_count == 0 and trace.tool_calls:
        tool_call_count = len(trace.tool_calls)
    result["number_tool_calls"] = tool_call_count
    try:
        result["sys_prompt_size"] = len(trace.user_components[0].message)
    except IndexError:
        result["sys_prompt_size"] = 0

    result["tool_calls"] = {tool_component.tool_name for tool_component in trace.tool_components}
    result["number_errors"] = len(trace.get_error_tool_components())
    result["exit_code"] = extrace_trace_exit_codes(trace)


    # Get the first index 
    first_read = trace.get_first_read_file(gold_patch.get_file_names())
    if first_read:
        result["number_steps_first_read"] = first_read.get("number_steps", 0)
        result["cost_first_read"] = first_read.get("cost", 0.0)
        result["prompt_tokens_first_read"] = first_read.get("prompt_tokens", 0)
        result["completion_tokens_first_read"] = first_read.get("completion_tokens", 0)

    # Compute reasoning tokens
    token_usage = trace.get_token_usage()
    reasoning_tokens = 0
    for key, value in token_usage.items():
        reasoning_tokens += value.reasoning_tokens
    result["reasoning_tokens"] = reasoning_tokens

    return result    


def is_plan_ls(plan: str | None, model: Model) -> str:
    prompt = f"""You will be given a string that contains instructions for coding agents to work in a repository. Your goal is to analyze whether those instructions contain an extensive overview of the repository structure.
    
    Answer in this JSON format:
    {{
        "contains_overview": true/false 
        "reasoning": "explanation text"
    }}

    Here is the plan:
    ```
    {plan}
    ```
    """

    response = model.query([{"role": "user", "content": prompt}])

    return response


def analyze_instance(
    instance: Any,
    trace: Trace | None,
    report: Any,
    plan: str | None,
    model: Model | None = None,
) -> dict[str, Any]:
    """Return per-instance metrics for the CSV output."""
    instance_id = _get_instance_value(instance, "instance_id", "")
    patch = _get_instance_patch(instance)
    difficulty = _get_instance_value(instance, "difficulty", "unknown")

    payload = _extract_report_payload(report, instance_id)
    passed, failed = _summarize_tests(payload.get("tests_status"))
    resolved = _resolve_reported_result(payload)

    patch_metrics, patch_length, num_files_changed = _summarize_instance_patch(patch)

    model_patch = payload.get("model_patch")
    gold_patch = patch if isinstance(patch, str) else ""
    if not isinstance(model_patch, str) and trace is not None:
        submission = trace.info.get("submission")
        if isinstance(submission, str):
            model_patch = submission

    plan_text = plan if isinstance(plan, str) else ""
    row = {
        "instance_id": instance_id,
        "resolved": resolved,
        "pass_tests": passed,
        "fail_tests": failed,
        "difficulty": str(difficulty),
        "patch_length": patch_length,
        "num_files_changed": num_files_changed,
        **patch_metrics,
        **_extract_patch_metrics(model_patch, "model_patch"),
    }
    row.update(_summarize_trace(trace, gold_patch))
    if model is None:
        model = MODEL


    if IS_PLAN_LS:
        if len(plan_text.strip()) == 0:
            row["is_plan_ls"] = "{contains_overview: false, reasoning: 'no plan provided'}"
        else:
            row["is_plan_ls"] = is_plan_ls(plan_text, model)
    else:
        row["is_plan_ls"] = "N/A"

    return row


def load_instance_lookup(
    dataset_name: str, skip: int
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Load instance patch metadata keyed by instance_id."""
    instances: dict[str, dict[str, Any]] = {}
    skip_ids: set[str] = set()

    try:
        dataset = load_dataset(dataset_name)
    except Exception as exc:  # pragma: no cover - network failure
        print(f"Warning: failed to load dataset {dataset_name}: {exc}", file=sys.stderr)
        return instances, skip_ids

    if isinstance(dataset, Mapping):
        splits = dataset.items()
    else:
        splits = [("default", dataset)]

    for split_name, split in splits:
        if not hasattr(split, "__iter__"):
            continue
        for row in split:
            instance_id = row.get("instance_id")
            if not instance_id:
                continue

            patch = row.get("patch")
            if patch is None:
                patch = row.get("clean_pr_patch")
            instances[instance_id] = {
                "instance_id": instance_id,
                "patch": patch,
                "difficulty": str(row.get("difficulty", "unknown")),
            }

            if split_name == "test" and len(skip_ids) < skip:
                skip_ids.add(instance_id)

    if skip and not skip_ids:
        for instance_id in instances:
            skip_ids.add(instance_id)
            if len(skip_ids) >= skip:
                break

    return instances, skip_ids


def _plan_storage_subdir(
    plan_type: str, planner_config: Mapping[str, Any]
) -> Path | None:
    prompt_type = planner_config.get("prompt_type")
    plan_model = planner_config.get("plan_model")

    if plan_type == "baseline":
        if prompt_type and plan_model:
            return Path("baseline_plans") / prompt_type / plan_model
        return None
    if plan_type in {"codex_planner", "claude_planner", "qwen_planner"}:
        if prompt_type and plan_model:
            return Path("init_planner") / prompt_type / plan_model
        return None
    if plan_type == "oracle":
        if plan_model:
            return Path("oracle_plans") / plan_model
        return None
    if plan_type == "human_planner":
        return Path("human_plans")

    return None


def load_plan_lookup(
    *,
    plan_type: str,
    planner_config: Mapping[str, Any],
    dataset_name: str,
    plan_generator: str | None,
    run_id: int | None,
) -> dict[str, str]:
    subdir = _plan_storage_subdir(plan_type, planner_config)
    if subdir is None:
        return {}

    base_dir = Path(planner_config.get("storage_dir", "output/plans"))
    dataset_segment = dataset_name.replace("/", "_")
    candidate_roots: list[Path] = []
    base_roots: list[Path] = []
    if plan_generator:
        base_roots.append(base_dir / dataset_segment / plan_generator)
    base_roots.append(base_dir / dataset_segment)
    base_roots.append(base_dir)
    run_segment = f"run_{run_id}" if run_id is not None else None
    for root in base_roots:
        if run_segment:
            candidate_roots.append(root / run_segment)
        candidate_roots.append(root)

    for root in candidate_roots:
        plan_path = root / subdir / "extracted_plans.json"
        if not plan_path.exists():
            continue
        try:
            data = json.loads(plan_path.read_text())
        except Exception as exc:  # pragma: no cover - malformed json
            print(f"Warning: failed to parse {plan_path}: {exc}", file=sys.stderr)
            continue
        if isinstance(data, Mapping):
            return {
                str(instance_id): str(plan_text)
                for instance_id, plan_text in data.items()
                if isinstance(instance_id, str)
            }
        
    print(f"Warning: no plan lookup found for {plan_type} in {base_dir}", file=sys.stderr)

    return {}


def extrace_trace_exit_codes(trace: Trace) -> dict[int, int]:
    exit_code_counts: dict[int, int] = {}
    for tool_component in trace.tool_components:
        if tool_component.tool_name in {"Bash", "run_shell_command", "shell"}:
            exit_code = tool_component.extract_exit_code()
            if exit_code is not None:
                exit_code_counts[exit_code] = exit_code_counts.get(exit_code, 0) + 1
    return exit_code_counts


def load_traces(exec_root: Path) -> dict[str, Trace]:
    if not exec_root.exists():
        print(f"Warning: execution directory not found: {exec_root}", file=sys.stderr)
        return {}

    traces: dict[str, Trace] = {}
    for traj_path in exec_root.glob("**/*.traj.json"):
        name = traj_path.name
        instance_id = name[:-10] if name.endswith(".traj.json") else traj_path.stem
        try:
            traces[instance_id] = Trace.from_path(traj_path)
        except Exception as exc:  # pragma: no cover - malformed json
            print(f"Warning: unable to read trajectory {traj_path}: {exc}", file=sys.stderr)
    return traces


def _analyze_instance_task(
    base_row: Mapping[str, Any],
    instance: Any,
    trace: Trace | None,
    payload: Mapping[str, Any],
    plan_text: str | None,
    model: Model | None = None,
) -> dict[str, Any]:
    row = dict(base_row)
    row.update(analyze_instance(instance, trace, payload, plan_text, model=model))
    return row


def collect_instance_rows(
    report_paths: list[Path],
    instance_lookup: Mapping[str, Any],
    skip_ids: set[str],
    base_row: dict[str, Any],
    trace_lookup: Mapping[str, Trace],
    plan_lookup: Mapping[str, str],
    max_workers: int = 4,
    model: Model | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_instances: set[str] = set()
    tasks: list[tuple[Any, Trace | None, Mapping[str, Any], str | None]] = []

    for report_path in report_paths:
        try:
            data = json.loads(report_path.read_text())
        except Exception as exc:  # pragma: no cover - malformed json
            print(f"Warning: failed to parse {report_path}: {exc}", file=sys.stderr)
            continue

        if not isinstance(data, Mapping):
            continue

        for instance_id, payload in data.items():
            if not isinstance(payload, Mapping):
                continue
            if instance_id in skip_ids or instance_id in seen_instances:
                continue

            instance = instance_lookup.get(
                instance_id, {"instance_id": instance_id, "patch": None, "difficulty": "unknown"}
            )
            trace = trace_lookup.get(instance_id)
            plan_text = plan_lookup.get(instance_id)
            tasks.append((instance, trace, payload, plan_text))
            seen_instances.add(instance_id)

    if not tasks:
        return rows

    workers = max(1, max_workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _analyze_instance_task,
                base_row,
                instance,
                trace,
                payload,
                plan_text,
                model=model,
            )
            for instance, trace, payload, plan_text in tasks
        ]

        for future in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Analyzing instances",
            unit="instance",
        ):
            rows.append(future.result())

    return rows


def append_rows_to_csv(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("Warning: no rows found to append.", file=sys.stderr)
        return

    file_exists = csv_path.exists()
    existing_keys: set[tuple[str, ...]] = set()

    if file_exists:
        with csv_path.open("r", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = tuple(row.get(field, "") for field in CSV_KEY_FIELDS)
                existing_keys.add(key)

    new_rows: list[dict[str, Any]] = []
    duplicate_instances: set[str] = set()

    for row in rows:
        key = tuple(str(row[field]) for field in CSV_KEY_FIELDS)
        if key in existing_keys:
            duplicate_instances.add(row["instance_id"])
            continue
        existing_keys.add(key)
        new_rows.append(row)

    if duplicate_instances:
        joined = ", ".join(sorted(duplicate_instances))
        print(f"Warning: skipped duplicate CSV entries for {joined}", file=sys.stderr)

    if not new_rows:
        return

    new_rows.sort(key=lambda item: item["instance_id"])

    mode = "a" if file_exists else "w"
    with csv_path.open(mode, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)


def main(
    plan_type: str,
    exec_model: str,
    generator: str,
    skip: int = 0,
    csv: Path | None = "results.csv",
    run_id: int = 0,
    plan_model: str | None = None,
    plan_generator: str | None = None,
    output_dir: str = "output",
    dataset_name: str = "nmuendler/SWE-bench_Verified_shuffle",
    plan_args: Any = None,
    max_workers: int = 4,
) -> str:
    if isinstance(csv, str):
        csv_path = Path(csv)
    elif csv is None:
        csv_path = Path("results.csv")
    else:
        csv_path = csv

    plan_args_dict = _load_plan_args(plan_args)
    plan_args_text = _format_plan_args(plan_args_dict) if plan_args_dict else ""
    planner_config, resolved_plan_model = _resolve_planner_config(
        plan_type, plan_model, exec_model, plan_args_dict
    )
    if plan_generator is None:
        plan_generator = generator

    output_path = Path(output_dir)
    log_dir = _compute_run_directory(
        output_dir=output_path,
        dataset_name=dataset_name,
        plan_type=plan_type,
        generator=generator,
        exec_model=exec_model,
        run_id=run_id,
        planner_config=planner_config,
        kind="swebench",
    )

    exec_root = _compute_run_directory(
        output_dir=output_path,
        dataset_name=dataset_name,
        plan_type=plan_type,
        generator=generator,
        exec_model=exec_model,
        run_id=run_id,
        planner_config=planner_config,
        kind="agentbench",
    )

    if not log_dir.exists():  # pragma: no cover - missing logs
        raise FileNotFoundError(f"log directory not found: {log_dir}")

    instance_lookup, skip_ids = load_instance_lookup(dataset_name, skip)

    report_paths = sorted(log_dir.rglob("report.json"))
    if not report_paths:  # pragma: no cover - missing reports
        print(f"Warning: no report.json files found under {log_dir}", file=sys.stderr)

    trace_lookup = load_traces(exec_root)
    plan_lookup = load_plan_lookup(
        plan_type=plan_type,
        planner_config=planner_config,
        dataset_name=dataset_name,
        plan_generator=plan_generator,
        run_id=run_id,
    )

    base_row = {
        "plan_model": resolved_plan_model,
        "exec_model": exec_model,
        "plan_type": plan_type,
        "plan_args": plan_args_text,
        "run_id": int(run_id),
        "generator": generator,
        "dataset_name": dataset_name,
        "execution_cost": 0.0,
        "resolved": False,
        "pass_tests": 0,
        "fail_tests": 0,
        "difficulty": "unknown",
        "patch_length": -1,
        "num_files_changed": -1,
        **_metric_defaults("patch", -1),
        **_metric_defaults("model_patch", -1),
        "log_dir": str(log_dir),
        "instance_id": "",
    }

    rows = collect_instance_rows(
        report_paths,
        instance_lookup,
        skip_ids,
        base_row,
        trace_lookup,
        plan_lookup,
        max_workers=max_workers,
        model=MODEL,
    )
    append_rows_to_csv(csv_path, rows)
    return str(csv_path)


if __name__ == "__main__":
    fire.Fire(main)
