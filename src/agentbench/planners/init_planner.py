from typing import Any
from pathlib import Path
from dataclasses import dataclass
import threading
import json
import logging
import shlex

from agentbench import Planner, Environment, Model, Instance
from agentbench.generators import get_generator
from agentbench.model import get_model
from agentbench.planners.utils.plan_extractor import extract_plan_from_patch
from agentbench.utils.io_utils import save_traj
from agentbench.utils.others import retry

_PLAN_FILE_LOCK = threading.Lock()


_CODEX_INIT_PROMPT = """Generate a file named AGENTS.md that serves as a contributor guide for this repository.
    Your goal is to produce a clear, concise, and well-structured document with descriptive headings and actionable explanations for each section.
    Follow the outline below, but adapt as needed — add sections if relevant, and omit those that do not apply to this project.
    
    Document Requirements
    
    - Title the document "Repository Guidelines".
    - Use Markdown headings (#, ##, etc.) for structure.
    - Keep the document concise. 200-400 words is optimal.
    - Keep explanations short, direct, and specific to this repository.
    - Provide examples where helpful (commands, directory paths, naming patterns).
    - Maintain a professional, instructional tone.
    
    Recommended Sections
    
    Project Structure & Module Organization
    
    - Outline the project structure, including where the source code, tests, and assets are located.
    
    Build, Test, and Development Commands
    
    - List key commands for building, testing, and running locally (e.g., npm test, make build).
    - Briefly explain what each command does.
    
    Coding Style & Naming Conventions
    
    - Specify indentation rules, language-specific style preferences, and naming patterns.
    - Include any formatting or linting tools used.
    
    Testing Guidelines
    
    - Identify testing frameworks and coverage requirements.
    - State test naming conventions and how to run tests.
    
    Commit & Pull Request Guidelines
    
    - Summarize commit message conventions found in the project’s Git history.
    - Outline pull request requirements (descriptions, linked issues, screenshots, etc.).
    
    (Optional) Add other sections if relevant, such as Security & Configuration Tips, Architecture Overview, or Agent-Specific Instructions."""

_CLAUDE_CODE_INIT_PROMPT = """Please analyze this codebase and create a CLAUDE.md file, which will be given to future instances of Claude Code to operate in this repository.

What to add:
1. Commands that will be commonly used, such as how to build, lint, and run tests. Include the necessary commands to develop in this codebase, such as how to run a single test.
2. High-level code architecture and structure so that future instances can be productive more quickly. Focus on the "big picture" architecture that requires reading multiple files to understand.

Usage notes:
- If there's already a CLAUDE.md, suggest improvements to it.
- When you make the initial CLAUDE.md, do not repeat yourself and do not include obvious instructions like "Provide helpful error messages to users", "Write unit tests for all new utilities", "Never include sensitive information (API keys, tokens) in code or commits".
- Avoid listing every component or file structure that can be easily discovered.
- Don't include generic development practices.
- If there are Cursor rules (in .cursor/rules/ or .cursorrules) or Copilot rules (in .github/copilot-instructions.md), make sure to include the important parts.
- If there is a README.md, make sure to include the important parts.
- Do not make up information such as "Common Development Tasks", "Tips for Development", "Support and Documentation" unless this is expressly included in other files that you read.
- Be sure to prefix the file with the following text:

```
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
```"""

_QWEN_INIT_PROMPT = """You are Qwen Code, an interactive CLI agent. Analyze the current directory and generate a comprehensive AGENTS.md file to be used as instructional context for future interactions.

**Analysis Process:**

1.  **Initial Exploration:**
    *   Start by listing the files and directories to get a high-level overview of the structure.
    *   Read the README file (e.g., \`README.md\`, \`README.txt\`) if it exists. This is often the best place to start.

2.  **Iterative Deep Dive (up to 10 files):**
    *   Based on your initial findings, select a few files that seem most important (e.g., configuration files, main source files, documentation).
    *   Read them. As you learn more, refine your understanding and decide which files to read next. You don't need to decide all 10 files at once. Let your discoveries guide your exploration.

3.  **Identify Project Type:**
    *   **Code Project:** Look for clues like \`package.json\`, \`requirements.txt\`, \`pom.xml\`, \`go.mod\`, \`Cargo.toml\`, \`build.gradle\`, or a \`src\` directory. If you find them, this is likely a software project.
    *   **Non-Code Project:** If you don't find code-related files, this might be a directory for documentation, research papers, notes, or something else.

**AGENTS.md Content Generation:**

**For a Code Project:**

*   **Project Overview:** Write a clear and concise summary of the project's purpose, main technologies, and architecture.
*   **Building and Running:** Document the key commands for building, running, and testing the project. Infer these from the files you've read (e.g., \`scripts\` in \`package.json\`, \`Makefile\`, etc.). If you can't find explicit commands, provide a placeholder with a TODO.
*   **Development Conventions:** Describe any coding styles, testing practices, or contribution guidelines you can infer from the codebase.

**For a Non-Code Project:**

*   **Directory Overview:** Describe the purpose and contents of the directory. What is it for? What kind of information does it hold?
*   **Key Files:** List the most important files and briefly explain what they contain.
*   **Usage:** Explain how the contents of this directory are intended to be used.

**Final Output:**

Write the complete content to the `AGENTS.md` file. The output must be well-formatted Markdown."""

_GEMINI_INIT_PROMPT="""You are an AI agent that brings the power of Gemini directly into the terminal. Your task is to analyze the current directory and generate a comprehensive GEMINI.md file to be used as instructional context for future interactions.

**Analysis Process:**

1.  **Initial Exploration:**
    *   Start by listing the files and directories to get a high-level overview of the structure.
    *   Read the README file (e.g., \`README.md\`, \`README.txt\`) if it exists. This is often the best place to start.

2.  **Iterative Deep Dive (up to 10 files):**
    *   Based on your initial findings, select a few files that seem most important (e.g., configuration files, main source files, documentation).
    *   Read them. As you learn more, refine your understanding and decide which files to read next. You don't need to decide all 10 files at once. Let your discoveries guide your exploration.

3.  **Identify Project Type:**
    *   **Code Project:** Look for clues like \`package.json\`, \`requirements.txt\`, \`pom.xml\`, \`go.mod\`, \`Cargo.toml\`, \`build.gradle\`, or a \`src\` directory. If you find them, this is likely a software project.
    *   **Non-Code Project:** If you don't find code-related files, this might be a directory for documentation, research papers, notes, or something else.

**GEMINI.md Content Generation:**

**For a Code Project:**

*   **Project Overview:** Write a clear and concise summary of the project's purpose, main technologies, and architecture.
*   **Building and Running:** Document the key commands for building, running, and testing the project. Infer these from the files you've read (e.g., \`scripts\` in \`package.json\`, \`Makefile\`, etc.). If you can't find explicit commands, provide a placeholder with a TODO.
*   **Development Conventions:** Describe any coding styles, testing practices, or contribution guidelines you can infer from the codebase.

**For a Non-Code Project:**

*   **Directory Overview:** Describe the purpose and contents of the directory. What is it for? What kind of information does it hold?
*   **Key Files:** List the most important files and briefly explain what they contain.
*   **Usage:** Explain how the contents of this directory are intended to be used.

**Final Output:**

Write the complete content to the \`GEMINI.md\` file. The output must be well-formatted Markdown."""

_PROMPT_TYPES = {
    "codex_agentsmd": _CODEX_INIT_PROMPT, 
    "claude_agentsmd": _CLAUDE_CODE_INIT_PROMPT,
    "qwen_agentsmd": _QWEN_INIT_PROMPT,
    "gemini_agentsmd": _GEMINI_INIT_PROMPT,
}

@dataclass
class InitPlannerConfig:
    generator_config: dict[str, Any]
    model_config: dict[str, Any]
    prompt_type: str 
    plan_model: str
    storage_dir: str = "plans"


class InitPlanner(Planner):
    """Generates AGENTS.md plans similarly to /init from CodexCLI"""

    def __init__(self, **kwargs: Any) -> None:
        self.config = InitPlannerConfig(**kwargs)
        self.logger = logging.getLogger(f"agentbench.init_planner.{self.config.prompt_type}")

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:

        instance_id = instance.instance_id

        # Write the AGENTS.md file to the environment
        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)

        agent_md = self._generate_agent_md(env, model, instance_id)
        self.logger.info(f"Writing AGENTS.md for instance {instance_id}")

        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)
  
        env.execute(f'echo {shlex.quote(agent_md)} > AGENTS.md', timeout=False)
        env.execute(f'echo {shlex.quote(agent_md)} > CLAUDE.md', timeout=False)

    def update_plan(self, **kwargs) -> None:
        pass
    
    @retry(5)
    def _generate_agent_md(self, env: Environment, model: Model, instance_id: str) -> str:
        
        # Try to load the AGENTS.md file if it exists
        agent_md = self._load_agent_md(instance_id)
        if agent_md is not None:
            return agent_md
        
        # Otherwise, generate a new AGENTS.md file
        self.logger.warning(f"No existing AGENTS.md found for {instance_id}. Generating a new one.")
        storage_path = self._get_storage_path()
        traj_path = storage_path / instance_id / f"{instance_id}_traj.json"

        # Fetch the plan model
        plan_model = get_model(self.config.model_config)
        generator_config = self.config.generator_config
        generator = get_generator(generator_config=generator_config, model=plan_model, env=env)
        prompt = _PROMPT_TYPES.get(self.config.prompt_type, "")
        try:
            exit_status, result_diff = generator.run(task=prompt)

            # Clean the repo
            env.execute("git clean -fd", timeout=False)

            save_traj(
                generator=generator,
                path=traj_path,
                exit_status=exit_status,
                result=result_diff,
            )
        except Exception as e:
            self.logger.exception(f"Error generating AGENTS.md for instance {instance_id}: {e}")
            raise RuntimeError(f"Error generating AGENTS.md for instance {instance_id}: {e}") from e
        
        agents_md = extract_plan_from_patch(result_diff)
        if len(agents_md.strip()) == 0:
            raise RuntimeError(f"Extracted AGENTS.md is empty for instance {instance_id}")
        
        
        self._store_agent_md(instance_id, agents_md)
        return agents_md


    def _store_agent_md(self, instance_id: str, agent_md: str) -> None:

        with _PLAN_FILE_LOCK:
            
            storage_dir = self._get_storage_path()
            extracted_plans = storage_dir / "extracted_plans.json"

            if extracted_plans.exists():
                with open(extracted_plans, "r") as f:
                    plans = json.load(f)
            else:
                plans = {}

            plans[instance_id] = agent_md

            with open(extracted_plans, "w") as f:
                json.dump(plans, f, indent=2)

    def _load_agent_md(self, instance_id: str) -> str | None:
        
        storage_dir = self._get_storage_path()
        extracted_plans = storage_dir / "extracted_plans.json"

        if not extracted_plans.exists():
            return None

        with open(extracted_plans, "r") as f:
            plans = json.load(f)

        return plans.get(instance_id, None)
        

    def _get_storage_path(self) -> Path:
        
        storage_dir = Path(self.config.storage_dir)
        storage_dir = storage_dir / "init_planner" / self.config.prompt_type / self.config.plan_model # for keeping compatibility
        storage_dir.mkdir(parents=True, exist_ok=True)

        return storage_dir