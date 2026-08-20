import os

# Claude Code wird pro Container frisch installiert. Ohne Versionsargument liefert der
# Bootstrap-Installer den jeweils aktuellen Stand aus -- der Harness waere dann zwischen
# Laeufen (und bei langen Laeufen sogar innerhalb eines Laufs) nicht derselbe. In einem
# Design, das den Harness als Untersuchungsgegenstand behandelt, ist das die unabhaengige
# Variable, die davonlaeuft. Upstream pinnt qwen-code (@0.0.14) und codex (@0.55.0), aber
# weder claude_code noch gemini-cli (@latest) -- wir ziehen das nach.
# Der Installer akzeptiert `stable|latest|X.Y.Z`: `... | bash -s 2.1.223`.
CLAUDE_CODE_VERSION = os.getenv("AGENTBENCH_CLAUDE_CODE_VERSION", "2.1.223")

QWEN_GENERATOR_CONFIG = {
    "launch_command": "OPENAI_API_KEY={api_key} OPENAI_BASE_URL={base_url} OPENAI_MODEL={model} qwen --yolo -p {prompt}",
    "install_commands": [
        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash",
        '. "$HOME/.nvm/nvm.sh"',
        "nvm install 24",
        "npm install -g @qwen-code/qwen-code@0.0.14",
    ],
    "post_install_commands": [
        "mkdir -p .qwen",
        """cat > .qwen/settings.json << 'JSON'
{
  "sessionTokenLimit": 262144,
  "contextFileName": "AGENTS.md",
  "chatCompression": {
    "contextPercentageThreshold": 0.6
  },
  "summarizeToolOutput": {
    "run_shell_command": {
      "tokenBudget": 2000
    }
  }
}
JSON""",
        "cat .qwen/settings.json",
    ],
    "post_exec_commands": [
        "rm -rf .qwen",
    ],
    "cli_name": "qwen_code",
}

CODEX_GENERATOR_CONFIG = {
    "launch_command": "RUST_LOG=debug LITELLM_API_KEY={api_key} codex exec -c model_provider=litellm -c model_providers.litellm.name=litellm -c model_providers.litellm.base_url={base_url} -c model={model} -c model_providers.litellm.env_key=LITELLM_API_KEY -c model_providers.litellm.wire_api=responses --yolo --skip-git-repo-check {prompt}",
    "install_commands": [
        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash",
        '. "$HOME/.nvm/nvm.sh"',
        "nvm install 24",
        "npm install -g @openai/codex@0.55.0",
    ],
    "post_install_commands": [],
    "post_exec_commands": [],
    "cli_name": "codex",
}

CLAUDE_CODE_GENERATOR_CONFIG = {
    "launch_command": "IS_SANDBOX=1 ANTHROPIC_BASE_URL={base_url} ANTHROPIC_AUTH_TOKEN={api_key} ~/.local/bin/claude --dangerously-skip-permissions --model {model} -p {prompt}",
    "install_commands": [
        f"curl -fsSL https://claude.ai/install.sh | bash -s {CLAUDE_CODE_VERSION}",
    ],
    "post_install_commands": [
        # Zur Kontrolle in der Container-Ausgabe: was ist tatsaechlich installiert?
        "~/.local/bin/claude --version",
    ],
    "post_exec_commands": [],
    "cli_name": "claude_code",
}

GEMINI_CLI_GENERATOR_CONFIG = {
    "launch_command": "GEMINI_API_KEY={api_key} GOOGLE_GEMINI_BASE_URL={base_url} GEMINI_MODEL={model} /root/.nvm/versions/node/v24.13.0/bin/gemini --yolo -p {prompt}",
    "install_commands": [
        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash",
        '. "$HOME/.nvm/nvm.sh"',
        "nvm install 24",
        "npm install -g @google/gemini-cli@latest",
    ],
    "post_install_commands": [
        "mv AGENTS.md GEMINI.md",
    ],
    "post_exec_commands": [
        "mv",
    ],
    "cli_name": "gemini_cli",
}



# Pi (badlogic/earendil) — neutraler Studien-Harness (Pivot §12). Anbindung wie alle
# CLIs ueber den harness-eigenen LiteLLM-Proxy ({base_url}/{api_key}/{model} aus
# get_openai_args), damit Traces/Tokens in der .traj.json landen und temp 0 aus dem
# Registry-Eintrag (glm-4.5-air-t0) request-seitig erzwungen wird. Pi kennt keinen
# Base-URL-Flag -> models.json wird im launch_command mit den Laufzeitwerten
# geschrieben (doppelte Klammern = Literale fuers .format()). --session-dir liegt
# bewusst AUSSERHALB von /testbed, sonst landen Session-Dateien im finalen git diff.
# -p = print mode, -a = Trust fuer projektlokale Dateien (AGENTS.md/Skills-Delivery!).
# Version gepinnt (0.84.2 = Stand Skill-Gate 16.08.); Node via nvm wie qwen/codex.
PI_GENERATOR_CONFIG = {
    "launch_command": (
        "mkdir -p ~/.pi/agent /tmp/pi-sessions && "
        "printf '%s' '{{\"providers\":{{\"litellm\":{{\"baseUrl\":\"{base_url}\","
        "\"api\":\"openai-completions\",\"apiKey\":\"{api_key}\",\"models\":"
        "[{{\"id\":\"{model}\",\"name\":\"study-model\",\"contextWindow\":131072,"
        "\"maxTokens\":8192}}]}}}}}}' > ~/.pi/agent/models.json && "
        "pi -p -a --provider litellm --model {model} --session-dir /tmp/pi-sessions "
        "--append-system-prompt \"You operate non-interactively. Never end your turn with "
        "only a plan or announcement - always proceed by calling tools until the task is "
        "complete, then finish with a summary of your changes.\" {prompt}"
    ),
    "install_commands": [
        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash",
        '. "$HOME/.nvm/nvm.sh"',
        "nvm install 24",
        "npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.84.2",
    ],
    "post_install_commands": [
        "pi --version",
    ],
    "post_exec_commands": [],
    "cli_name": "pi",
}


MINI_SWE_AGENTS_CONFIG = {\
    "step_limit": 200,
}

def add_generator_class(config: dict, generator_class: str) -> dict:
    if "generator_class" not in config:
        config["generator_class"] = generator_class
    return config


ALL_GENERATOR_CONFIGS = {
    "qwen_code": add_generator_class(QWEN_GENERATOR_CONFIG, "cli_agent"),
    "codex": add_generator_class(CODEX_GENERATOR_CONFIG, "cli_agent"),
    "miniswe_agents": add_generator_class(MINI_SWE_AGENTS_CONFIG, "miniswe_agents"),
    "claude_code": add_generator_class(CLAUDE_CODE_GENERATOR_CONFIG, "cli_agent"),
    "gemini_cli": add_generator_class(GEMINI_CLI_GENERATOR_CONFIG, "cli_agent"),
    "pi": add_generator_class(PI_GENERATOR_CONFIG, "cli_agent"),
}