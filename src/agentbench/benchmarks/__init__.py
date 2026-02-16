import copy
import importlib

from agentbench import Benchmark

_BENCHMARK_MAPPING = {
    "swebench": "agentbench.benchmarks.swebench.SweBench",
    "agentbench": "agentbench.benchmarks.agentbench.AgentbenchBenchmark",
}


def get_benchmark_class(spec: str) -> type[Benchmark]:
    full_path = _BENCHMARK_MAPPING.get(spec, spec)
    try:
        module_name, class_name = full_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as e:
        msg = f"Unknown benchmark type: {spec} (resolved to {full_path}, available: {_BENCHMARK_MAPPING})"
        raise ValueError(msg) from e


def get_benchmark(benchmark_config: dict) -> Benchmark:
    config = copy.deepcopy(benchmark_config)
    benchmark_class = config.pop("benchmark_class", None)
    assert benchmark_class is not None, "benchmark_class must be specified in benchmark_config"
    return get_benchmark_class(benchmark_class)(**config)
