from agentbench import Planner, Environment, Model, Instance

class NoPlanPlanner(Planner):
    """A planner that does nothing."""

    def __init__(self, **kwargs) -> None:
        pass

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:
        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)

    def update_plan(self, **kwargs) -> None:
        pass
