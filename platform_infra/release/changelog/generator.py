"""Automated Release Changelog Generator (L17 Release - Feature 17.10).

Synthesizes structured release notes from conventional git commits and database
schema diffs into categorized Markdown sections.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


_CONVENTIONAL_RE = re.compile(
    r"^(?P<kind>feat|fix|perf|refactor|docs|chore|security)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<desc>.+)$"
)


@dataclass
class CommitEntry:
    """Parsed git commit record."""

    sha: str
    message: str
    author: str = "unknown"
    kind: str = "other"
    scope: Optional[str] = None
    description: str = ""
    breaking: bool = False

    @classmethod
    def from_raw(cls, sha: str, message: str, author: str = "unknown") -> "CommitEntry":
        first_line = message.strip().splitlines()[0] if message.strip() else ""
        match = _CONVENTIONAL_RE.match(first_line)
        breaking = "BREAKING CHANGE" in message
        if match:
            return cls(
                sha=sha[:8],
                message=message,
                author=author,
                kind=match.group("kind"),
                scope=match.group("scope"),
                description=match.group("desc").strip(),
                breaking=breaking or bool(match.group("breaking")),
            )
        return cls(
            sha=sha[:8],
            message=message,
            author=author,
            kind="other",
            description=first_line,
            breaking=breaking,
        )


@dataclass
class SchemaDiffEntry:
    """Database schema change detected between releases."""

    table: str
    change_type: str  # e.g., "ADD_COLUMN", "CREATE_TABLE", "DROP_COLUMN"
    detail: str
    breaking: bool = False


@dataclass
class ChangelogRelease:
    """Rendered release changelog artifact."""

    version: str
    release_date: str
    sections: Dict[str, List[str]] = field(default_factory=dict)
    markdown: str = ""


class ChangelogGenerator:
    """Generates Markdown changelogs from commit history and schema diffs."""

    _SECTION_TITLES: Dict[str, str] = {
        "breaking": "Breaking Changes",
        "feat": "Features",
        "fix": "Bug Fixes",
        "security": "Security",
        "perf": "Performance",
        "schema": "Schema Changes",
        "other": "Maintenance & Docs",
    }

    def generate(
        self,
        version: str,
        commits: List[CommitEntry],
        schema_diffs: Optional[List[SchemaDiffEntry]] = None,
        release_date: Optional[str] = None,
    ) -> ChangelogRelease:
        """Build categorized sections and Markdown document for a release."""
        date_str = release_date or datetime.date.today().isoformat()
        sections: Dict[str, List[str]] = {k: [] for k in self._SECTION_TITLES}

        for commit in commits:
            prefix = f"**{commit.scope}**: " if commit.scope else ""
            bullet = f"- {prefix}{commit.description} (`{commit.sha}`)"
            if commit.breaking:
                sections["breaking"].append(bullet)
            elif commit.kind in sections:
                sections[commit.kind].append(bullet)
            else:
                sections["other"].append(bullet)

        for diff in schema_diffs or []:
            tag = " [BREAKING]" if diff.breaking else ""
            bullet = f"- `{diff.table}` ({diff.change_type}){tag}: {diff.detail}"
            target_sec = "breaking" if diff.breaking else "schema"
            sections[target_sec].append(bullet)

        lines = [f"## [{version}] - {date_str}", ""]
        for key, title in self._SECTION_TITLES.items():
            items = sections[key]
            if not items:
                continue
            lines.append(f"### {title}")
            lines.extend(items)
            lines.append("")

        non_empty = {k: v for k, v in sections.items() if v}
        return ChangelogRelease(
            version=version,
            release_date=date_str,
            sections=non_empty,
            markdown="\n".join(lines).strip() + "\n",
        )

