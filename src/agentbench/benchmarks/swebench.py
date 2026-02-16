# Forked from: https://github.com/SWE-agent/mini-swe-agent

import json
import random
import re
import tempfile
import threading
from pathlib import Path
from typing import Any
from dataclasses import dataclass
import logging

from datasets import load_dataset

from swebench import run_evaluation

from agentbench import Environment, Instance, Benchmark
from agentbench.environments import get_environment


DATASET_MAPPING = {
    "full": "princeton-nlp/SWE-Bench",
    "verified": "princeton-nlp/SWE-Bench_Verified",
    "lite": "princeton-nlp/SWE-Bench_Lite",
    "multimodal": "princeton-nlp/SWE-Bench_Multimodal",
    "multilingual": "swe-bench/SWE-Bench_Multilingual",
    "smith": "SWE-bench/SWE-smith",
    "_test": "klieret/swe-bench-dummy-test-dataset",
}


_OUTPUT_FILE_LOCK = threading.Lock()

logger = logging.getLogger("agentbench.swebench")

@dataclass
class SweBenchInstance(Instance):

    instance_id: str
    image_name: str
    docker_image_root: str
    repo: str
    task: str
    patch: str # The solution of the instance

    # Used for benchmark evaluation 
    dataset_name: str
    split: str

    def get_dir(self, base_dir: Path) -> Path:
        instance_id = self.instance_id
        instance_dir = base_dir / instance_id
        remove_from_preds_file(instance_dir / "preds.json", instance_id)
        instance_dir.mkdir(parents=True, exist_ok=True)
        return instance_dir

    def remove_agents_md_files(self, env: Environment) -> None:
        env.execute(
            r'find . -type f \( -name "AGENTS.md" -o -name "CLAUDE.md" \) -print -delete',
            timeout=False,
        )
        env.execute("rm -rf .github", timeout=False) # Copilot agents.md files

    def remove_docs(self, env: Environment) -> None:
        """Remove documentation files and folders from the repo, but keep AGENTS.md/CLAUDE.md."""

        logger.info(f"Removing documentation files for instance {self.instance_id}")

        # First we back up AGENTS.md and CLAUDE.md if they exist
        agent_md = env.read_file("AGENTS.md") 
        claude_md = env.read_file("CLAUDE.md")

        env.execute(
            r'''rm -f \
                mkdocs.yml mkdocs.yaml \
                readthedocs.yml .readthedocs.yml .readthedocs.yaml \
                docusaurus.config.js docusaurus.config.ts \
                sidebars.js sidebars.ts \
                docfx.json \
                conf.py sphinx.conf.py \
                antora.yml \
                .gitbook.yml book.json \
                _config.yml \
                docs.yml documentation.yml \
                */mkdocs.yml */mkdocs.yaml \
                */readthedocs.yml */.readthedocs.yml */.readthedocs.yaml \
                */docusaurus.config.js */docusaurus.config.ts \
                */docfx.json */antora.yml */.gitbook.yml */book.json
            ''',
            timeout=False,
        )

        env.execute(
            r'''rm -f \
                README README.* readme readme.* \
                CHANGELOG CHANGELOG.* changelog changelog.* \
                CONTRIBUTING CONTRIBUTING.* contributing contributing.* \
                CODE_OF_CONDUCT CODE_OF_CONDUCT.* code_of_conduct code_of_conduct.* \
                SECURITY SECURITY.* security security.* \
                SUPPORT SUPPORT.* support support.* \
                GOVERNANCE GOVERNANCE.* governance governance.* \
                AUTHORS AUTHORS.* authors authors.* \
                FAQ FAQ.* faq faq.* \
                ROADMAP ROADMAP.* roadmap roadmap.* \
                TROUBLESHOOTING TROUBLESHOOTING.* troubleshooting troubleshooting.* \
                INSTALL INSTALL.* install install.* \
                UPGRADE UPGRADE.* upgrade upgrade.* \
                MIGRATION MIGRATION.* migration migration.* \
                RELEASE RELEASE.* release release.*
            ''',
            timeout=False,
        )

        env.execute(
            r'''find . -type f \( \
                -iname "*.md" -o -iname "*.markdown" \
                -o -iname "*.rst" \
                -o -iname "*.adoc" -o -iname "*.asciidoc" \
                -o -iname "*.txt" \
                -o -iname "*.mdx" \
                -o -iname "*.ronn" \
                -o -iname "*.wiki" \
                -o -iname "*.tex" \
            \) -print -delete''',
            timeout=False,
        )

        env.execute(
            r'''rm -rf \
                docs doc documentation \
                site sites _site _docs _doc _documentation \
                .docs .doc .documentation \
                book books .gitbook \
                wiki wikis \
                guide guides manual manuals \
                api apidocs api-docs api_docs \
                reference references \
                tutorials tutorial \
                examples example \
                samples sample \
                guides guide \
                spec specs specification specifications \
                man manpages \
                help \
                docs-src docs_source docs-sources docs_sources \
                */docs */doc */documentation \
                */site */sites */_site */book */books */.gitbook
            ''',
            timeout=False,
        )

        env.execute(
            r'''rm -rf \
                _build .sphinx .doctrees \
                site-build site_build \
                public build dist out \
                .docusaurus \
                .vuepress/dist \
                .next \
                .gatsby \
                .cache \
                */_build */.sphinx */public */build */dist */out */.docusaurus */.cache
            ''',
            timeout=False,
        )

        env.execute(
            r'''find . -type f \( \
                -iname "*.svg" -o -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.gif" -o -iname "*.webp" \
                -o -iname "*.pdf" \
            \) \
            \( -path "*/docs/*" -o -path "*/doc/*" -o -path "*/documentation/*" -o -path "*/site/*" -o -path "*/book/*" \) \
            -print -delete''',
            timeout=False,
        )

        # Finally we restore AGENTS.md and CLAUDE.md
        if agent_md:
            env.write_file("AGENTS.md", agent_md)
        if claude_md:
            env.write_file("CLAUDE.md", claude_md)
    
    def setup(self, env_config: dict[str, Any], **kwargs) -> Environment:
        env = get_sb_environment(env_config, self)
        return env
    
    def solve(self, patch_diff: str, base_dir: Path, run_id: int) -> bool:
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".json") as prediction_file:

                prediction_file.write(json.dumps({self.instance_id: {"model_patch": patch_diff, "instance_id": self.instance_id, "model_name_or_path": "model"}}).encode())
                prediction_file.flush()
                print(prediction_file.name)

                namespace = "swebench"
                if "swa-bench" in self.dataset_name.lower():
                    namespace = "logicstarai"

                result_path = run_evaluation(
                    dataset_name=self.dataset_name,
                    split=self.split,
                    instance_ids=[self.instance_id],
                    predictions_path=prediction_file.name,
                    max_workers=1,
                    force_rebuild=False,
                    cache_level="env",
                    clean=False,
                    open_file_limit=4096,
                    run_id=str(run_id),
                    timeout=1800,
                    namespace=namespace,
                    rewrite_reports=False,
                    modal=False,
                    report_dir=base_dir.as_posix(),
                )

            with result_path.open() as f:
                result_data = json.load(f)
                solved = self.instance_id in result_data["resolved_ids"]

        except Exception as e:
            logger.error(f"Error during evaluation of instance {self.instance_id}: {e}", exc_info=True)
            solved = False

        return solved

@dataclass
class SweBenchConfig:
    dataset_name: str = "nmuendler/SWE-bench_Verified_shuffle"
    filter_spec: str = ""
    slice_spec: str = ""
    split: str = "test"
    shuffle: bool = False

class SweBench(Benchmark):
    """SWE-bench benchmark."""

    def __init__(self, **kwargs: Any) -> None:
        self.config = SweBenchConfig(**kwargs)
        if self.config.dataset_name in DATASET_MAPPING:
            self.config.dataset_name = DATASET_MAPPING[self.config.dataset_name]

        self.instances = self.get_instances()
        self.instance_map = {inst.instance_id: inst for inst in self.instances}

    def get_single_instance(self, instance_id: str) -> SweBenchInstance:
        return self.instance_map[instance_id]

    def get_instances(self) -> list[SweBenchInstance]:
        instances = list(load_dataset(self.config.dataset_name, split=self.config.split))
        instances = filter_instances(
            instances, filter_spec=self.config.filter_spec, slice_spec=self.config.slice_spec, shuffle=self.config.shuffle
        )
        return [self._get_instance_from_row(row) for row in instances]

    def _sanitize_patch_diff(self, patch_diff: str) -> str:
        # Check that the patch ends with a newline
        if not patch_diff.endswith("\n"):
            patch_diff += "\n"
        return patch_diff
    
    def solve(self, patch_diffs: dict[str,str], base_dir: Path, run_id: int, workers: int = 8) -> dict[str, bool]:
        
        # We call run_evaluation for all instances at once
        try:
            with tempfile.NamedTemporaryFile(suffix=".json") as prediction_file:

                # Write the prediction file
                preds = {}
                for instance_id, patch_dict in patch_diffs.items():
                    preds[instance_id] = {"model_patch": self._sanitize_patch_diff(patch_dict["model_patch"]), "instance_id": instance_id, "model_name_or_path": "model"}
                prediction_file.write(json.dumps(preds).encode())
                prediction_file.flush()

                # Get the instance ids from the instance attributes intersected with the prediction keys
                instance_ids = list(self.instance_map.keys())
                instance_ids = [id for id in instance_ids if id in preds]
                logger.info(f"Evaluating {len(instance_ids)} instances with SWE-bench")
                

                namespace = "swebench"
                if "swa-bench" in self.config.dataset_name.lower():
                    namespace = "logicstarai"
                    logger.info("Using logicstarai namespace for SWA-bench dataset")

                result_path = run_evaluation(
                    dataset_name=self.config.dataset_name,
                    split=self.config.split,
                    instance_ids=instance_ids,
                    predictions_path=prediction_file.name,
                    max_workers=workers,
                    force_rebuild=False,
                    cache_level="env",
                    clean=True,
                    open_file_limit=4096,
                    run_id=str(run_id),
                    timeout=1800,
                    namespace=namespace,
                    rewrite_reports=False,
                    modal=False,
                    report_dir=base_dir.as_posix(),
                )

            solved = {}
            for instance_id in instance_ids:
                with result_path.open() as f:
                    result_data = json.load(f)
                    solved[instance_id] = instance_id in result_data["resolved_ids"]

        except Exception as e:
            logger.error(f"Error during evaluation of Swebench: {e}", exc_info=True)
            return {}

        return solved
        
       
    def _get_instance_from_row(self, row: dict[str, Any]) -> SweBenchInstance:
        instance = SweBenchInstance(
            instance_id=row["instance_id"],
            image_name=row.get("image_name", None),
            docker_image_root=row.get("docker_image_root", None),
            repo=row["repo"],
            task=row["problem_statement"],
            patch=row["patch"],
            dataset_name=self.config.dataset_name,
            split=self.config.split,
        )
        return instance


def filter_instances(
    instances: list[dict],
    *,
    filter_spec: str,
    slice_spec: str = "",
    shuffle: bool = False,
) -> list[dict]:
    """Filter and slice a list of SWEBench instances."""
    if shuffle:
        instances = sorted(instances.copy(), key=lambda x: x["instance_id"])
        random.seed(42)
        random.shuffle(instances)
    before_filter = len(instances)
    instances = [
        instance
        for instance in instances
        if re.match(filter_spec, instance["instance_id"])
    ]
    if (after_filter := len(instances)) != before_filter:
        logger.info(f"Instance filter: {before_filter} -> {after_filter} instances")
    if slice_spec:
        values = [int(x) if x else None for x in slice_spec.split(":")]
        instances = instances[slice(*values)]
        if (after_slice := len(instances)) != before_filter:
            logger.info(f"Instance slice: {before_filter} -> {after_slice} instances")
    return instances
    

def get_swebench_docker_image_name(instance: SweBenchInstance) -> str:
    """Get the image name for a SWEBench instance."""
    
    image_name = instance.image_name
    docker_image_root = instance.docker_image_root or "sweb.eval"

    owner_name = "swebench"

    if "swa-bench" in docker_image_root.lower():
        owner_name = "logicstarai"

    if image_name is None:
        # Docker doesn't allow double underscore, so we replace them with a magic token
        iid = instance.instance_id
        if owner_name == "logicstarai":
            id_docker_compatible = iid
            suffix = ""
        elif owner_name == "swebench":
            id_docker_compatible = iid.replace("__", "_1776_")
            suffix = ":latest"

            if "matplotlib" in id_docker_compatible: # Fix for rootless docker
                owner_name = "tgloaguen"

        else:
            id_docker_compatible = iid.replace("__", "-1776-")
            suffix = ":latest"

        

        image_name = f"{owner_name}/{docker_image_root}.x86_64.{id_docker_compatible}{suffix}".lower()
    return image_name


def get_sb_environment(env_config: dict, instance: SweBenchInstance) -> Environment:
    image_name = get_swebench_docker_image_name(instance)
    if env_config.get("environment_class") == "singularity":
        image_name = "docker://" + image_name
    env_config["image"] = image_name
    return get_environment(env_config, default_type="docker")

def remove_from_preds_file(output_path: Path, instance_id: str):
    """Remove an instance from the predictions file."""
    if not output_path.exists():
        return
    with _OUTPUT_FILE_LOCK:
        output_data = json.loads(output_path.read_text())
        if instance_id in output_data:
            del output_data[instance_id]
            output_path.write_text(json.dumps(output_data, indent=2))

