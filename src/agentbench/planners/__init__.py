"""Planner implementations for AgentBench."""

import copy
import importlib

from agentbench import Planner

_PLANNER_MAPPING = {
    "baseline_planner": "agentbench.planners.baseline.BaselinePlanner",
    "dc_planner": "agentbench.planners.dynamic_cheatsheet.dynamic_cheatsheet.DCPlanner",
    "oracle_planner": "agentbench.planners.oracle.OraclePlanner",
    "evo_reproducer_planner": "agentbench.planners.evo_reproducer.evo_reproducer.EvoReproducerPlanner",
    "ace_planner": "agentbench.planners.ace.ace.ACEPlanner",
    "no_plan": "agentbench.planners.no_plan.NoPlanPlanner",
    "human_planner": "agentbench.planners.human_planner.HumanPlanner",
    "init_planner": "agentbench.planners.init_planner.InitPlanner",
    "curated_planner": "agentbench.planners.curated_planner.CuratedPlanner",
}


def get_planner_class(spec: str) -> type[Planner]:
    full_path = _PLANNER_MAPPING.get(spec, spec)
    try:
        module_name, class_name = full_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as e:
        msg = f"Unknown planner type: {spec} (resolved to {full_path}, available: {_PLANNER_MAPPING})"
        more = f" ({e})" if str(e) else ""
        raise ValueError(msg + more) from e


def get_planner(planner_config: dict) -> Planner:
    config = copy.deepcopy(planner_config)
    planner_class = config.pop("planner_class", None)
    assert planner_class is not None, "planner_class must be specified in planner_config"
    return get_planner_class(planner_class)(**config)
