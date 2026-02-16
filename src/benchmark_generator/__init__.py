from typing import Protocol

from pathlib import Path

from agentbench import Model, Environment, Generator
from benchmark_generator.pull_request import PullRequestInstance

class Agent(Protocol):

    model: Model
    env: Environment
    generator: Generator

    def process_pr(self, pr: PullRequestInstance, output_path: Path) -> PullRequestInstance: ...