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
        "curl -fsSL https://claude.ai/install.sh | bash",
    ],
    "post_install_commands": [],
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
}