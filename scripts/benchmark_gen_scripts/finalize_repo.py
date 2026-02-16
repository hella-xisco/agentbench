from __future__ import annotations

import json
from pathlib import Path

import fire
from datasets import Dataset

from benchmark_generator.config import (
    FILTERED_INSTANCES_DIR_NAME,
    DEFAULT_OUTPUT_DIR,
    maybe_get_repo_config,
    available_repo_configs,
)

def sanitize_repo_test_results(example):
    repo_test_after_pr_patch = example["repo_test_after_pr_patch"]
    repo_test_after_pr_patch = {k: v for k, v in repo_test_after_pr_patch.items() if v is not None}
    example["repo_test_after_pr_patch"] = str(repo_test_after_pr_patch) # Has to be str to be pushed to hub without errors
    return example


def finalize_repo(
    repo: str | None = None,
    dataset_name: str | None = None,
    output: str = DEFAULT_OUTPUT_DIR,
) -> None:
    config_entry = maybe_get_repo_config(repo)
    if not config_entry:
        available = ", ".join(sorted(available_repo_configs()))
        raise ValueError(
            "Unknown repository. Pass --repo or --repo-config matching one of: "
            f"{available}"
        )

    repo = config_entry.repo
    dataset_id = dataset_name or config_entry.dataset_name
    if not dataset_id:
        raise ValueError(
            "No dataset name provided. Set dataset_name in the repo config or "
            "pass --dataset_name explicitly."
        )

    base_output = Path(output) / config_entry.slug
    output_dir = base_output / FILTERED_INSTANCES_DIR_NAME

    # Fetch PRs from input
    print(f"Loading processed PRs from {output_dir}...")
    pr_files = sorted(output_dir.glob("*.json"))

    dataset = []
    for pr_file in pr_files:

        with pr_file.open("r", encoding="utf-8") as f:
            pr_data = json.load(f)

            repo_format = repo.replace("/", "_")

            pr_data["docker_image"] = config_entry.docker_image
            pr_data["repo"] = repo_format
            pr_data["instance_id"] = f"{repo_format}-{pr_data['number']}"

            dataset.append(pr_data)

    dataset.sort(key=lambda x: int(x["number"]))

    dataset = Dataset.from_list(dataset)
    dataset = dataset.map(sanitize_repo_test_results)
    dataset.push_to_hub(dataset_id, private=False)
    print(f"Pushed {len(dataset)} instances to {dataset_id}")


if __name__ == "__main__":
    fire.Fire(finalize_repo)
