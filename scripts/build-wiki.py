#!/usr/bin/env python3
"""Build a flat GitHub Wiki from the hierarchical docs/ directory.

Transforms docs/ into wiki/ by:
1. Flattening the directory structure with section-prefixed filenames
2. Rewriting all internal markdown links to match the flat namespace
3. Generating _Sidebar.md with hierarchical navigation
4. Generating _Footer.md with a link to source docs

Usage:
    python3 scripts/build-wiki.py
"""

import os
import re
import shutil
from pathlib import Path

# Project root (parent of scripts/)
ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
WIKI_DIR = ROOT / "wiki"
REPO_URL = "https://github.com/jaredmixpanel/liteflow"

# Explicit mapping: docs-relative path -> wiki filename
# index.md files use the parent directory name as their wiki page name
PAGE_MAP = {
    "index.md": "Home.md",
    "getting-started/installation.md": "Getting-Started-Installation.md",
    "getting-started/first-workflow.md": "Getting-Started-First-Workflow.md",
    "getting-started/credentials.md": "Getting-Started-Credentials.md",
    "getting-started/scheduling.md": "Getting-Started-Scheduling.md",
    "getting-started/templates.md": "Getting-Started-Templates.md",
    "concepts/architecture.md": "Concepts-Architecture.md",
    "concepts/workflows-and-dags.md": "Concepts-Workflows-and-DAGs.md",
    "concepts/execution-engine.md": "Concepts-Execution-Engine.md",
    "concepts/context-and-data-flow.md": "Concepts-Context-and-Data-Flow.md",
    "reference/commands.md": "Reference-Commands.md",
    "reference/step-types/index.md": "Reference-Step-Types.md",
    "reference/step-types/script-shell-claude.md": "Reference-Script-Shell-Claude.md",
    "reference/step-types/query-http-transform.md": "Reference-Query-HTTP-Transform.md",
    "reference/step-types/gate-fanout-fanin.md": "Reference-Gate-FanOut-FanIn.md",
    "reference/modules/index.md": "Reference-Modules.md",
    "guides/debugging-workflows.md": "Guides-Debugging-Workflows.md",
    "guides/optimizing-workflows.md": "Guides-Optimizing-Workflows.md",
    "guides/creating-templates.md": "Guides-Creating-Templates.md",
    "guides/extending-liteflow.md": "Guides-Extending-liteflow.md",
}

SIDEBAR_CONTENT = """\
**[Home](Home)**

**Getting Started**
- [Installation](Getting-Started-Installation)
- [First Workflow](Getting-Started-First-Workflow)
- [Credentials](Getting-Started-Credentials)
- [Scheduling](Getting-Started-Scheduling)
- [Templates](Getting-Started-Templates)

**Concepts**
- [Architecture](Concepts-Architecture)
- [Workflows and DAGs](Concepts-Workflows-and-DAGs)
- [Execution Engine](Concepts-Execution-Engine)
- [Context and Data Flow](Concepts-Context-and-Data-Flow)

**Reference**
- [Commands](Reference-Commands)
- [Step Types](Reference-Step-Types)
  - [Script, Shell, Claude](Reference-Script-Shell-Claude)
  - [Query, HTTP, Transform](Reference-Query-HTTP-Transform)
  - [Gate, Fan-Out, Fan-In](Reference-Gate-FanOut-FanIn)
- [Modules](Reference-Modules)

**Guides**
- [Debugging](Guides-Debugging-Workflows)
- [Optimizing](Guides-Optimizing-Workflows)
- [Creating Templates](Guides-Creating-Templates)
- [Extending liteflow](Guides-Extending-liteflow)
"""

FOOTER_CONTENT = f"""\
---
[View source docs on GitHub]({REPO_URL}/tree/main/docs) | liteflow v0.1.0
"""


def rewrite_links(content: str, source_docs_rel: str) -> str:
    """Rewrite markdown links from relative doc paths to flat wiki page names.

    Args:
        content: Markdown content with relative links.
        source_docs_rel: Path of source file relative to docs/ (e.g. "getting-started/first-workflow.md").

    Returns:
        Content with links rewritten for the wiki's flat namespace.
    """
    source_dir = str(Path(source_docs_rel).parent)

    def replace_link(match: re.Match) -> str:
        full_match = match.group(0)
        text = match.group(1)
        href = match.group(2)

        # Skip external URLs and bare anchors
        if href.startswith(("http://", "https://", "#")):
            return full_match

        # Split href into path and optional anchor
        if "#" in href:
            path_part, anchor = href.split("#", 1)
            anchor = "#" + anchor
        else:
            path_part = href
            anchor = ""

        # Skip if no path (just an anchor)
        if not path_part:
            return full_match

        # Resolve relative path against source file's directory
        resolved = os.path.normpath(os.path.join(source_dir, path_part))

        # Look up in page map
        wiki_filename = PAGE_MAP.get(resolved)
        if wiki_filename is None:
            # Try without leading ./
            resolved_clean = resolved.lstrip("./")
            wiki_filename = PAGE_MAP.get(resolved_clean)

        if wiki_filename is None:
            print(f"  WARNING: unresolved link in {source_docs_rel}: [{text}]({href}) -> {resolved}")
            return full_match

        # Wiki page name is filename without .md
        wiki_page = wiki_filename.removesuffix(".md")
        return f"[{text}]({wiki_page}{anchor})"

    return re.sub(r"\[([^\]]*)\]\(([^)]+)\)", replace_link, content)


def build_wiki() -> None:
    """Build the wiki/ directory from docs/."""
    # Clean and recreate wiki/
    if WIKI_DIR.exists():
        shutil.rmtree(WIKI_DIR)
    WIKI_DIR.mkdir()

    rewritten_count = 0
    warning_count = 0

    for docs_rel, wiki_filename in PAGE_MAP.items():
        source = DOCS_DIR / docs_rel
        if not source.exists():
            print(f"ERROR: source file not found: {source}")
            continue

        content = source.read_text()

        # Count links before rewriting for stats
        original_links = re.findall(r"\[([^\]]*)\]\(([^)]+)\)", content)
        internal_links = [
            l for l in original_links
            if not l[1].startswith(("http://", "https://", "#"))
            and (l[1].split("#")[0])  # has a path component
        ]

        transformed = rewrite_links(content, docs_rel)

        dest = WIKI_DIR / wiki_filename
        dest.write_text(transformed)
        rewritten_count += len(internal_links)
        print(f"  {docs_rel} -> {wiki_filename} ({len(internal_links)} links)")

    # Generate _Sidebar.md
    (WIKI_DIR / "_Sidebar.md").write_text(SIDEBAR_CONTENT)
    print("  Generated _Sidebar.md")

    # Generate _Footer.md
    (WIKI_DIR / "_Footer.md").write_text(FOOTER_CONTENT)
    print("  Generated _Footer.md")

    # Summary
    total_files = len(list(WIKI_DIR.glob("*.md")))
    print(f"\nDone: {total_files} files in wiki/ ({rewritten_count} links rewritten)")


if __name__ == "__main__":
    print("Building wiki from docs/...\n")
    build_wiki()
