from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import fire
from githubkit import GitHub

from benchmark_generator.config import (
    DEFAULT_OUTPUT_DIR,
    PR_CACHE_DIR_NAME,
    maybe_get_repo_config,
)
from benchmark_generator.pull_request import PullRequestInstance
from agentbench.utils.log import logger

ISSUE_URL_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/issues/(?P<number>\d+)",
    re.IGNORECASE,
)
REPO_ISSUE_PATTERN = re.compile(
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<number>\d+)",
    re.IGNORECASE,
)
LOCAL_ISSUE_PATTERN = re.compile(r"#(?P<number>\d+)")

MAX_PR_CACHE_SIZE = 2000


def _issue_slug(base_repo: str, owner: str | None = None, repo: str | None = None) -> str:
    if owner and repo:
        return f"{owner}/{repo}"
    return base_repo


def _split_repo_slug(repo_slug: str) -> tuple[str, str]:
    if "/" not in repo_slug:
        raise ValueError(f"Repository slug must be in the form owner/repo, got: {repo_slug}")
    return tuple(repo_slug.split("/", 1))  # type: ignore[return-value]


def extract_issue_references(body: str, base_repo: str) -> list[tuple[str, int]]:
    if not body:
        return []

    references: set[tuple[str, int]] = set()

    for match in ISSUE_URL_PATTERN.finditer(body):
        owner = match.group("owner")
        repo = match.group("repo")
        number = int(match.group("number"))
        references.add((_issue_slug(base_repo, owner, repo), number))

    for match in REPO_ISSUE_PATTERN.finditer(body):
        owner = match.group("owner")
        repo = match.group("repo")
        number = int(match.group("number"))
        references.add((_issue_slug(base_repo, owner, repo), number))

    for match in LOCAL_ISSUE_PATTERN.finditer(body):
        number = int(match.group("number"))
        references.add((_issue_slug(base_repo), number))

    # Preserve deterministic ordering for reproducibility
    return sorted(references)


def ensure_cache_paths(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)


def load_pr_cache(pr_cache_path: Path) -> PullRequestInstance | None:
    patch_cache_path = pr_cache_path.with_suffix(".patch")
    if not pr_cache_path.exists():
        return None
    try:
        data = json.loads(pr_cache_path.read_text())
        if "patch" not in data and patch_cache_path.exists():
            data["patch"] = patch_cache_path.read_text()
        return PullRequestInstance.from_dict(data)
    except json.JSONDecodeError:
        logger.warning(f"Unable to parse cached PR data at {pr_cache_path}, refetching.")
    except ValueError:
        logger.warning(f"Cached PR data at {pr_cache_path} is missing required fields, refetching.")
    return None


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2))


def format_body_with_comments(body: str, comments: list[str]) -> str:
    comments_block = "\n".join(comments).strip()
    formatted_body = f"# Main body\n\n{body}"
    if comments_block:
        return f"{formatted_body}\n\n# Comments\n\n{comments_block}"
    return formatted_body


def fetch_pull_requests(
    client: GitHub,
    owner: str,
    repo: str,
    *,
    state: str,
    limit: int,
    only_merged: bool = True,
) -> list[dict[str, Any]]:
    prs: list[dict[str, Any]] = []
    page = 1
    per_page = 50
    max_count = min(limit if limit != -1 else 10_000_000, MAX_PR_CACHE_SIZE)

    while len(prs) < max_count:
        resp = client.rest.pulls.list(
            owner,
            repo,
            state=state,
            page=page,
            per_page=per_page,
            sort="updated",
            direction="desc",
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for pr in batch:
            if only_merged and not pr.get("merged_at"):
                continue
            prs.append(pr)
            if len(prs) >= max_count:
                break
        if len(batch) < per_page:
            break
        page += 1
    return prs


def fetch_pull_request(client: GitHub, owner: str, repo: str, number: int) -> dict[str, Any]:
    resp = client.rest.pulls.get(owner, repo, number)
    resp.raise_for_status()

    # Prefer typed payload to avoid accidentally getting None on unexpected responses.
    pr_data = resp.json()

    if pr_data is None:
        logger.warning(f"Pull request #{number} data is None.")

    return pr_data or {}


def fetch_patch(client: GitHub, patch_url: str) -> str:
    resp = client.request(
        "GET",
        patch_url,
        headers={"Accept": "application/vnd.github.v3.diff"},
    )
    resp.raise_for_status()
    return resp.text


def _paginate_comments(
    fetcher,
    *,
    per_page: int = 100,
    start_page: int = 1,
) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    page = start_page
    while True:
        resp = fetcher(page=page, per_page=per_page)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        comments.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return comments


def fetch_issue_comments(client: GitHub, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    return _paginate_comments(
        lambda **kwargs: client.rest.issues.list_comments(
            owner,
            repo,
            issue_number=number,
            **kwargs,
        )
    )


def fetch_review_comments(client: GitHub, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    return _paginate_comments(
        lambda **kwargs: client.rest.pulls.list_review_comments(
            owner,
            repo,
            pull_number=number,
            **kwargs,
        )
    )


def fetch_pr_comments(client: GitHub, owner: str, repo: str, pr_number: int) -> list[str]:
    """Fetch both issue and review comments for the pull request."""
    comments: list[tuple[str, str]] = []
    for comment_type, fetcher in (
        ("issue", fetch_issue_comments),
        ("review", fetch_review_comments),
    ):
        try:
            fetched_comments = fetcher(client, owner, repo, pr_number)
        except Exception as exc:
            logger.warning(
                f"Failed to fetch {comment_type} comments for PR #{pr_number}: {exc}",
                exc_info=True,
            )
            continue

        for comment in fetched_comments:
            body = comment.get("body")
            if not body:
                continue
            created_at = comment.get("created_at") or ""
            comments.append((created_at, body))

    comments.sort(key=lambda item: item[0])
    return [body for _, body in comments]


def fetch_referenced_issues(
    client: GitHub, references: list[tuple[str, int]]
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for slug, number in references:
        try:
            owner, repo = _split_repo_slug(slug)
            issue_resp = client.rest.issues.get(owner, repo, issue_number=number)
            issue_resp.raise_for_status()
            issue = issue_resp.json()
        except Exception as exc:
            logger.warning(
                f"Failed to fetch issue {slug}#{number}: {exc}",
                exc_info=True,
            )
            continue

        issues.append(
            {
                "title": issue.get("title") or "",
                "body": issue.get("body") or "",
            }
        )
    return issues


def cache_pull_request(
    *,
    client: GitHub,
    owner: str,
    repo: str,
    pr_number: int,
    cache_dir: Path,
    pr_summary: dict[str, Any] | None = None,
    force: bool = False,
) -> PullRequestInstance:
    pr_cache_path = cache_dir / f"{pr_number}.json"

    cached = load_pr_cache(pr_cache_path)
    summary_updated = (
        cached is not None
        and pr_summary is not None
        and pr_summary.get("updated_at") != cached.updated_at
    )

    if cached and not force and not summary_updated:
        # Fully cached entry; no refresh required.
        return cached

    logger.info(f"Fetching PR #{pr_number} from GitHub.")
    pr_data = fetch_pull_request(client, owner, repo, pr_number)

    patch_url = pr_data.get("diff_url")
    if not patch_url:
        raise ValueError(f"Patch URL missing in GitHub response for PR #{pr_number}.")

    patch_text = fetch_patch(client, patch_url)
    comments = fetch_pr_comments(client, owner, repo, pr_number)

    original_body = pr_data.get("body") or ""
    body_with_comments = format_body_with_comments(original_body, comments)

    base_repo_full_name = (
        pr_data.get("base", {}).get("repo", {}).get("full_name") or f"{owner}/{repo}"
    )
    references = extract_issue_references(body_with_comments, base_repo_full_name)
    referenced_issues = fetch_referenced_issues(client, references)

    url = pr_data.get("html_url") or ""

    try:
        head_repo = pr_data.get("head", {}).get("repo", {}).get("full_name")
    except AttributeError:
        head_repo = ""

    pr_instance = PullRequestInstance(
        number=int(pr_data.get("number") or pr_number),
        url=url,
        title=str(pr_data.get("title") or ""),
        body=body_with_comments,
        author=(pr_data.get("user") or {}).get("login") or "",
        base_repo=base_repo_full_name,
        head_repo=head_repo,
        base_sha=pr_data.get("base", {}).get("sha") or "",
        merged_at=pr_data.get("merged_at"),
        created_at=pr_data.get("created_at"),
        updated_at=pr_data.get("updated_at"),
        patch=patch_text,
        referenced_issues=referenced_issues,
        cache_updated_at=datetime.utcnow().isoformat() + "Z",
    )

    write_json(pr_cache_path, pr_instance.to_dict())

    return pr_instance


def build_cache(
    repo: str | None = None,
    output: str = DEFAULT_OUTPUT_DIR,
    limit: int = 20,
    force: bool = True,
    only_merged: bool = True,
    refetch: bool = True,
    repo_config: str | None = None,
) -> None:
    config = maybe_get_repo_config(repo_config or repo)
    if config:
        repo = repo or config.repo
        if output == DEFAULT_OUTPUT_DIR or not output:
            output = config.output_dir

    if not repo:
        raise ValueError("You must provide a repository slug via --repo or --repo-config.")

    owner, repository = _split_repo_slug(repo)

    output_path = Path(output) / repo.replace("/", "_")
    cache_dir = output_path / PR_CACHE_DIR_NAME
    ensure_cache_paths(cache_dir)

    effective_limit = MAX_PR_CACHE_SIZE if limit == -1 else min(limit, MAX_PR_CACHE_SIZE)
    if effective_limit != limit:
        logger.info(
            f"Capping requested limit {limit} to {effective_limit} "
            f"(maximum {MAX_PR_CACHE_SIZE})."
        )

    token = os.environ.get("GITHUB_TOKEN")
    if token is None:
        logger.warning(
            "GITHUB_TOKEN environment variable not set. "
            "You may encounter rate limiting when fetching from GitHub."
        )
    else:
        logger.info("Using GITHUB_TOKEN for authenticated requests to GitHub.")

    logger.info(
        f"Fetching pull requests for {repo} "
        f"(limit={effective_limit if effective_limit != -1 else 'all'}, only_merged={only_merged})."
    )

    processed_numbers: set[int] = set()

    with GitHub(token) as client:
        if refetch:
            prs = fetch_pull_requests(
                client,
                owner,
                repository,
                state="closed",
                limit=effective_limit,
                only_merged=only_merged,
            )

            for pr in prs:
                number = int(pr["number"])
                cache_pull_request(
                    client=client,
                    owner=owner,
                    repo=repository,
                    pr_number=number,
                    cache_dir=cache_dir,
                    pr_summary=pr,
                    force=force,
                )
                processed_numbers.add(number)

    logger.info(
        f"Cached {len(processed_numbers)} pull requests for {repo} at {cache_dir}."
    )


def main(**kwargs: Any) -> None:
    build_cache(**kwargs)


if __name__ == "__main__":
    fire.Fire(main)
