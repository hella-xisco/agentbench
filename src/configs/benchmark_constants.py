PLACEHOLDER = ""

SWE_BENCH_CONFIG = {
    "benchmark_class": "swebench",
    "dataset_name": PLACEHOLDER,
    "filter_spec": PLACEHOLDER,
    "slice_spec": PLACEHOLDER,
    "split": "test",
    "shuffle": False,
}

AGENTBENCH_CONFIG = {
    "benchmark_class": "agentbench",
    "dataset_name": PLACEHOLDER,
    "filter_spec": PLACEHOLDER,
    "slice_spec": PLACEHOLDER,
    "split": "train",
    "shuffle": False,
}

ALL_BENCHMARK_CONFIGS = {
    "swebench": SWE_BENCH_CONFIG,
    "agentbench": AGENTBENCH_CONFIG,
}
