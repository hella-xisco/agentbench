"""Register numbered thesis floats and their exact source/asset checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def braced(text: str, start: int) -> tuple[str, int]:
    if text[start] != "{":
        raise ValueError("Expected a TeX group")
    depth = 1
    for index in range(start + 1, len(text)):
        if text[index] in "{}" and (index == 0 or text[index - 1] != "\\"):
            depth += 1 if text[index] == "{" else -1
            if not depth:
                return text[start + 1:index], index + 1
    raise ValueError("Unbalanced TeX group")


def register(root: Path) -> dict:
    pdf = root / "thesis.pdf"
    pages = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True).split("\f")
    main = (root / "thesis.tex").read_text()
    included = re.findall(r"\\include\{(chapters/[^}]+)\}", main)
    assets = []
    seen = set()
    previous = {}
    for chapter in included:
        source = root / (chapter + ".tex")
        raw = source.read_text()
        clean = re.sub(r"(?<!\\)%[^\n]*", "", raw)
        aux = source.with_suffix(".aux").read_text()
        for match in re.finditer(r"\\begin\{(figure|table|sidewaystable)\}[\s\S]*?\\end\{\1\}", clean):
            block = match.group()
            kind = "figure" if match[1] == "figure" else "table"
            labels = re.findall(r"\\label\{([^}]+)\}", block)
            if len(labels) != 1 or labels[0] in seen:
                raise ValueError(f"Missing/duplicate float label in {chapter}")
            label = labels[0]
            seen.add(label)
            compiled = re.search(r"\\newlabel\{" + re.escape(label) + r"\}\{\{([^}]+)\}\{([^}]+)\}", aux)
            if not compiled:
                raise ValueError(f"Unresolved float: {label}")
            number, printed_page = compiled.groups()
            chapter_number, ordinal = number.rsplit(".", 1)
            key = kind, chapter_number
            if int(ordinal) != previous.get(key, 0) + 1:
                raise ValueError(f"Nonsequential {kind} number: {number}")
            previous[key] = int(ordinal)
            caption = re.search(r"\\caption(?:\[([^\]]*)\])?\s*\{", block)
            if not caption:
                raise ValueError(f"Missing caption: {label}")
            caption_text, _ = braced(block, caption.end() - 1)
            positions = [(i + 1, m.start()) for i, page in enumerate(pages)
                         for m in re.finditer(r"(?m)^\s*" + kind.title() + r"\s+" + re.escape(number) + r":", page)]
            if len(positions) != 1:
                raise ValueError(f"Caption absent or repeated in PDF: {label}: {positions}")
            files = []
            inputs = []
            for input_name in re.findall(r"\\input\{([^}]+)\}", block):
                file = root / input_name
                if not file.suffix:
                    file = file.with_suffix(".tex")
                files.append(file)
                inputs.extend(re.findall(r"(?m)^% Source: (.+)$", file.read_text()))
            for graphic in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", block):
                stem = root / "figures" / graphic
                for suffix in (".svg", ".pdf", ".drawio"):
                    file = stem.with_suffix(suffix)
                    if file.exists():
                        files.append(file)
                svg = stem.with_suffix(".svg")
                if svg.exists():
                    metadata = re.search(r"<metadata>([\s\S]*?)</metadata>", svg.read_text())
                    if metadata:
                        inputs.append(metadata[1])
            if any(not file.exists() for file in files):
                raise ValueError(f"Missing asset: {label}")
            assets.append({
                "kind": kind, "number": number, "label": label,
                "printed_page": printed_page, "pdf_page": positions[0][0],
                "caption_position": positions[0][1],
                "short_caption_tex": caption[1] or caption_text,
                "caption_tex": caption_text, "source_tex": str(source.relative_to(root)),
                "source_excerpt_tex": block,
                "files": {str(file.relative_to(root)): digest(file) for file in files},
                "analysis_sources": inputs,
            })
    for kind, extension in (("figure", "lof"), ("table", "lot")):
        listed = re.findall(r"\\contentsline \{" + kind + r"\}\{\\numberline \{([^}]+)\}", (root / f"thesis.{extension}").read_text())
        actual = [asset["number"] for asset in assets if asset["kind"] == kind]
        positions = [(asset["pdf_page"], asset["caption_position"]) for asset in assets if asset["kind"] == kind]
        if listed != actual or positions != sorted(positions):
            raise ValueError(f"{kind} source order, PDF order and list differ")
    return {"pdf_sha256": digest(pdf), "numbering": "separate chapterwise figure and table counters in appearance order",
            "assets": assets}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = register(args.thesis_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Registered {len(result['assets'])} floats; numbering, labels, PDF and lists agree")


if __name__ == "__main__":
    main()
