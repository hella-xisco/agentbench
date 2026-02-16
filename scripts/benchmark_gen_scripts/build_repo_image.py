import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "src/benchmark_generator/config.py"
DOCKERFILE_TEMPLATE = ROOT / "scripts/benchmark_gen_scripts/Dockerfile"


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)


def _parse_repo(repo_url: str) -> tuple[str, str, str]:
    """Return (repo_path, slug, clone_url) from a URL or owner/repo string."""
    cleaned = repo_url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    if cleaned.startswith("git@"):
        path = cleaned.split(":", 1)[1]
    elif "://" in cleaned:
        path = urlparse(cleaned).path
    else:
        path = cleaned

    path = path.strip("/ ")
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Could not extract owner/repo from '{repo_url}'.")

    owner, repo = parts[0], parts[1]
    repo_path = f"{owner}/{repo}"
    slug = f"{owner}_{repo}"

    if cleaned.startswith(("http://", "https://", "git@")):
        clone_url = repo_url
    else:
        clone_url = f"https://github.com/{repo_path}.git"

    return repo_path, slug, clone_url


def _prepare_dockerfile(
    template_path: Path, clone_url: str, workdir: Path
) -> Path:
    if not template_path.exists():
        raise FileNotFoundError(f"Dockerfile template not found: {template_path}")

    template = template_path.read_text()
    if "<REPO_URL>" not in template:
        raise ValueError("Template Dockerfile is missing the <REPO_URL> placeholder.")

    rendered = template.replace("<REPO_URL>", clone_url)
    dockerfile_path = workdir / "Dockerfile"
    dockerfile_path.write_text(rendered)
    return dockerfile_path


def _build_and_push_image(
    dockerfile_path: Path,
    image_tag: str,
    ref: str,
    push: bool,
) -> None:
    env = os.environ.copy()
    env.setdefault("DOCKER_BUILDKIT", "1")

    build_cmd = [
        "docker",
        "build",
        "--platform=linux/amd64",
        "--build-arg",
        f"REF={ref}",
        "-t",
        image_tag,
        "-f",
        str(dockerfile_path),
        str(dockerfile_path.parent),
    ]
    _run(build_cmd, env=env)

    if push:
        _run(["docker", "push", image_tag], env=env)


def _update_config(
    repo_path: str,
    image_tag: str,
    dataset_name: str,
    config_path: Path,
) -> bool:
    """Insert a new BenchmarkRepoConfig entry. Returns True if updated."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    content = config_path.read_text()
    if f'"{repo_path}"' in content:
        print(f"Config already contains an entry for {repo_path}, skipping.")
        return False

    marker = "\n}\n\n\ndef get_repo_config"
    if marker not in content:
        raise ValueError("Could not locate BENCHMARK_REPO_CONFIGS block in config.")

    entry = (
        f'    "{repo_path}": BenchmarkRepoConfig(\n'
        f'        repo="{repo_path}",\n'
        f'        docker_image="{image_tag}",\n'
        f'        dataset_name="{dataset_name}",\n'
        "    ),\n"
    )

    insert_at = content.index(marker)
    updated = content[:insert_at] + entry + content[insert_at:]
    config_path.write_text(updated)
    print(f"Added {repo_path} to {config_path}")
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build and push a docker image for a repo and register it in "
            "BENCHMARK_REPO_CONFIGS."
        )
    )
    parser.add_argument("repo_url", help="Repository URL (or owner/repo).")
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref (branch/tag/sha) to clone in the docker image. Default: %(default)s.",
    )
    parser.add_argument(
        "--no-push",
        dest="push",
        action="store_false",
        help="Build the image but skip pushing to the registry.",
    )
    parser.add_argument(
        "--skip-build",
        dest="build",
        action="store_false",
        help="Skip building/pushing the docker image; only update config.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DOCKERFILE_TEMPLATE,
        help=f"Path to the Dockerfile template (default: {DOCKERFILE_TEMPLATE}).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help=f"Path to benchmark config (default: {CONFIG_PATH}).",
    )
    parser.add_argument(
        "--image-tag",
        dest="image_tag",
        default=None,
        help="Override docker image tag (default: tgloaguen/agentbenchx86_<slug>:latest).",
    )
    parser.add_argument(
        "--dataset-name",
        dest="dataset_name",
        required=True,
        help=(
            "Dataset id to register in BENCHMARK_REPO_CONFIGS "
            '(for example: "org/dataset_name").'
        ),
    )

    args = parser.parse_args(argv)

    repo_path, slug, clone_url = _parse_repo(args.repo_url)
    image_tag = args.image_tag or f"tgloaguen/agentbenchx86_{slug}:latest"
    dataset_name = args.dataset_name

    print(f"Repo: {repo_path}")
    print(f"Slug: {slug}")
    print(f"Clone URL: {clone_url}")
    print(f"Docker image: {image_tag}")
    print(f"Dataset name: {dataset_name}")

    if args.build:
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            dockerfile_path = _prepare_dockerfile(args.template, clone_url, workdir)
            _build_and_push_image(
                dockerfile_path=dockerfile_path,
                image_tag=image_tag,
                ref=args.ref,
                push=args.push,
            )

    _update_config(
        repo_path=repo_path,
        image_tag=image_tag,
        dataset_name=dataset_name,
        config_path=args.config,
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
