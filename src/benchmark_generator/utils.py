import shlex
from pathlib import PurePosixPath

def split_patch_by_test_files(patch_text: str) -> tuple[str, str, str]:
    """Split raw patch text into non-test, test, and unclassified sections."""

    def classify_path(raw_path: str) -> bool | None:
        if not raw_path:
            return None
        if raw_path.startswith(("\"", "'")) and raw_path.endswith(("\"", "'")):
            raw_path = raw_path[1:-1]
        if raw_path == "/dev/null":
            return None
        path = raw_path
        if raw_path.startswith(("a/", "b/")):
            path = raw_path[2:]
        normalized = PurePosixPath(path.lower())
        if not normalized.parts:
            return None
        return any("test" in part for part in normalized.parts)

    if not patch_text:
        return "", "", ""

    non_test_lines: list[str] = []
    test_lines: list[str] = []
    other_lines: list[str] = []

    current_section: list[str] = []
    current_is_test: bool | None = None

    def flush_section() -> None:
        nonlocal current_section, current_is_test
        if not current_section:
            return
        target = other_lines
        if current_is_test is True:
            target = test_lines
        elif current_is_test is False:
            target = non_test_lines
        target.extend(current_section)


    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            flush_section()
            tokens = shlex.split(line)
            candidate = tokens[3] if len(tokens) > 3 else ""
            if not candidate and len(tokens) > 2:
                candidate = tokens[2]
            current_is_test = classify_path(candidate)
            current_section = [line]
            continue

        if line.startswith(("+++", "---")):
            current_section.append(line)
            classification = classify_path(line[4:].strip())
            if classification is not None:
                current_is_test = classification
            continue

        if current_section:
            current_section.append(line)
        else:
            other_lines.append(line)

    flush_section()

    return (
        "\n".join(non_test_lines),
        "\n".join(test_lines),
        "\n".join(other_lines),
    )


def patch_change_python_files(patch_text: str) -> bool:
    """Check if the patch changes any Python files."""
    python_file_changed = False
    in_python_file = False

    try:
        patch_lines = patch_text.splitlines()
    except Exception:
        return False

    for line in patch_lines:
        if line.startswith("diff --git"):
            tokens = line.split()
            path_a = tokens[2] if len(tokens) > 2 else ""
            path_b = tokens[3] if len(tokens) > 3 else ""
            if path_a.startswith("a/"):
                path_a = path_a[2:]
            if path_b.startswith("b/"):
                path_b = path_b[2:]
            candidates = [path for path in (path_a, path_b) if path and path != "/dev/null"]
            in_python_file = any(path.endswith(".py") for path in candidates)
            continue

        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            in_python_file = path.endswith(".py")
            continue

        if line.startswith("--- "):
            path = line[4:].strip()
            if path.startswith("a/"):
                path = path[2:]
            in_python_file = path.endswith(".py")
            continue

        if (
            in_python_file
            and line
            and line[0] in {"+", "-"}
            and not line.startswith(("+++", "---"))
            and line[1:].strip()
        ):
            python_file_changed = True
            break

    return python_file_changed