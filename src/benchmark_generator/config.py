from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


# Shared file and directory names used across the benchmark generator pipeline.
DEFAULT_OUTPUT_DIR = "benchmark_with_features"
PR_CACHE_DIR_NAME = "pr_cache"
TRIAGE_RESULTS_DIR_NAME = "triage_results"
SETUP_RESULTS_DIR_NAME = "setup_results"
STATEMENTS_DIR_NAME = "statements"
INSTANCES_DIR_NAME = "generated_instances"
FILTERED_INSTANCES_DIR_NAME = "filtered_instances"

TRIAGE_RESULTS_FILENAME = "triage_results.json"
STATEMENTS_FILENAME = "instances_statements.json"
GENERATED_INSTANCES_FILENAME = "generated_instances.jsonl"
FILTERED_INSTANCES_FILENAME = "filtered_instances.json"


@dataclass(frozen=True)
class BenchmarkRepoConfig:
    """Configuration for a single repository benchmark run."""

    repo: str
    docker_image: str
    dataset_name: str | None = None
    output_dir: str = DEFAULT_OUTPUT_DIR

    @property
    def slug(self) -> str:
        return self.repo.replace("/", "_")

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir) / self.slug

    @property
    def pr_cache_dir(self) -> Path:
        return self.output_path / PR_CACHE_DIR_NAME

    @property
    def triage_results_path(self) -> Path:
        return self.output_path / TRIAGE_RESULTS_FILENAME

    @property
    def statements_path(self) -> Path:
        return self.output_path / STATEMENTS_FILENAME

    @property
    def generated_instances_path(self) -> Path:
        return self.output_path / GENERATED_INSTANCES_FILENAME

    @property
    def filtered_instances_path(self) -> Path:
        return self.output_path / FILTERED_INSTANCES_FILENAME


BENCHMARK_REPO_CONFIGS: Dict[str, BenchmarkRepoConfig] = {    "opshin/opshin": BenchmarkRepoConfig(
        repo="opshin/opshin",
        docker_image="tgloaguen/agentbenchx86_opshin_opshin:latest",
        dataset_name="Grogros/test_planbench",
    ),

}


def get_repo_config(repo_slug: str) -> BenchmarkRepoConfig:
    try:
        return BENCHMARK_REPO_CONFIGS[repo_slug]
    except KeyError as exc:
        raise KeyError(
            f"Unknown benchmark repo config '{repo_slug}'. "
            f"Available keys: {', '.join(sorted(BENCHMARK_REPO_CONFIGS))}"
        ) from exc


def maybe_get_repo_config(repo_slug: str | None) -> BenchmarkRepoConfig | None:
    if not repo_slug:
        return None
    try:
        return get_repo_config(repo_slug)
    except KeyError:
        return None


def available_repo_configs() -> Iterable[str]:
    return BENCHMARK_REPO_CONFIGS.keys()
