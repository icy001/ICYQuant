"""
Release notes generator for ICYQuant.

Generates Markdown format release notes with sections for new features,
bug fixes, breaking changes, API changes, migration guide, and known
issues. Supports Conventional Commits parsing and auto-generation
from changelog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CommitEntry:
    hash: str
    message: str
    author: str
    type: str = ""
    scope: str = ""
    description: str = ""
    is_breaking: bool = False
    body: str = ""
    footer: str = ""


@dataclass
class ReleaseSection:
    title: str
    entries: list[str] = field(default_factory=list)


@dataclass
class ReleaseNotesResult:
    success: bool
    title: str
    version: str
    generated_at: str
    markdown_content: str
    sections: list[ReleaseSection] = field(default_factory=list)
    total_entries: int = 0
    features_count: int = 0
    fixes_count: int = 0
    breaking_changes_count: int = 0
    authors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ReleaseNotesGenerator:
    """
    Generates structured release notes in Markdown format.

    Parses Conventional Commits and organizes them into release note
    sections including new features, bug fixes, breaking changes,
    API changes, migration guides, and known issues.
    """

    FEATURE_TYPES = {"feat", "feature", "add"}
    FIX_TYPES = {"fix", "bugfix", "bug"}
    BREAKING_TYPES = {"breaking", "break"}
    API_TYPES = {"api", "change"}
    DOC_TYPES = {"docs", "doc", "documentation"}
    PERF_TYPES = {"perf", "performance"}
    REFACTOR_TYPES = {"refactor", "ref"}
    TEST_TYPES = {"test", "tests"}
    BUILD_TYPES = {"build", "ci", "chore"}

    SECTION_ORDER = [
        "breaking",
        "features",
        "fixes",
        "api",
        "performance",
        "refactored",
        "documentation",
    ]

    def __init__(
        self,
        version: str,
        *,
        title: str = "",
        date: Optional[str] = None,
    ) -> None:
        self.version = version
        self.title = title or f"ICYQuant v{version}"
        self.date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._commits: list[CommitEntry] = []
        self._known_issues: list[str] = []
        self._migration_notes: list[str] = []
        self._additional_sections: dict[str, list[str]] = {}

    def add_commit(
        self,
        commit_hash: str,
        message: str,
        *,
        author: str = "",
        body: str = "",
        footer: str = "",
    ) -> None:
        entry = self._parse_commit(
            commit_hash, message, author, body, footer
        )
        self._commits.append(entry)

    def add_commit_entry(self, entry: CommitEntry) -> None:
        self._commits.append(entry)

    def add_known_issue(self, description: str) -> None:
        self._known_issues.append(description)

    def add_migration_note(self, description: str) -> None:
        self._migration_notes.append(description)

    def add_section(self, title: str, entries: list[str]) -> None:
        self._additional_sections[title] = entries

    def parse_commits(
        self,
        commit_messages: list[dict[str, str]],
    ) -> None:
        for msg in commit_messages:
            commit_hash = msg.get("hash", "")
            message = msg.get("message", "")
            author = msg.get("author", "")
            body = msg.get("body", "")
            footer = msg.get("footer", "")
            self.add_commit(
                commit_hash, message, author=author, body=body, footer=footer
            )

    def generate(self) -> ReleaseNotesResult:
        errors: list[str] = []

        sections = self._build_sections()
        markdown = self._build_markdown(sections)

        authors = sorted({c.author for c in self._commits if c.author})
        features_count = sum(
            1 for c in self._commits if c.type in self.FEATURE_TYPES
        )
        fixes_count = sum(
            1 for c in self._commits if c.type in self.FIX_TYPES
        )
        breaking_count = sum(
            1 for c in self._commits if c.is_breaking
        )

        total_entries = sum(
            len(s.entries) for s in sections
        )

        success = len(errors) == 0
        return ReleaseNotesResult(
            success=success,
            title=self.title,
            version=self.version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            markdown_content=markdown,
            sections=sections,
            total_entries=total_entries,
            features_count=features_count,
            fixes_count=fixes_count,
            breaking_changes_count=breaking_count,
            authors=authors,
            errors=errors,
        )

    def _parse_commit(
        self,
        commit_hash: str,
        message: str,
        author: str,
        body: str,
        footer: str,
    ) -> CommitEntry:
        conventional_pattern = (
            r"^(?P<type>[a-zA-Z]+)"
            r"(?:\((?P<scope>[^)]+)\))?"
            r"(?P<breaking>[!])?"
            r":\s*(?P<description>.+)$"
        )

        is_breaking = "BREAKING CHANGE" in (body or "") or "!" in (message or "")

        match = re.match(conventional_pattern, message or "")
        if match:
            commit_type = match.group("type").lower()
            scope = match.group("scope") or ""
            description = match.group("description") or message or ""
            if match.group("breaking"):
                is_breaking = True
        else:
            commit_type = "other"
            scope = ""
            description = message or ""

        return CommitEntry(
            hash=commit_hash,
            message=message or "",
            author=author,
            type=commit_type,
            scope=scope,
            description=description,
            is_breaking=is_breaking,
            body=body or "",
            footer=footer or "",
        )

    def _build_sections(self) -> list[ReleaseSection]:
        grouped: dict[str, list[str]] = {
            "breaking": [],
            "features": [],
            "fixes": [],
            "api": [],
            "performance": [],
            "refactored": [],
            "documentation": [],
        }

        for commit in self._commits:
            entry = self._format_entry(commit)
            if commit.is_breaking:
                grouped["breaking"].append(entry)
            elif commit.type in self.FEATURE_TYPES:
                grouped["features"].append(entry)
            elif commit.type in self.FIX_TYPES:
                grouped["fixes"].append(entry)
            elif commit.type in self.API_TYPES:
                grouped["api"].append(entry)
            elif commit.type in self.PERF_TYPES:
                grouped["performance"].append(entry)
            elif commit.type in self.REFACTOR_TYPES:
                grouped["refactored"].append(entry)
            elif commit.type in self.DOC_TYPES:
                grouped["documentation"].append(entry)

        sections: list[ReleaseSection] = []
        section_titles = {
            "breaking": "Breaking Changes",
            "features": "New Features",
            "fixes": "Bug Fixes",
            "api": "API Changes",
            "performance": "Performance Improvements",
            "refactored": "Refactored",
            "documentation": "Documentation",
        }

        for key in self.SECTION_ORDER:
            entries = grouped.get(key, [])
            if entries:
                sections.append(ReleaseSection(
                    title=section_titles[key],
                    entries=entries,
                ))

        for title, entries in self._additional_sections.items():
            if entries:
                sections.append(ReleaseSection(
                    title=title,
                    entries=entries,
                ))

        if self._migration_notes:
            sections.append(ReleaseSection(
                title="Migration Guide",
                entries=list(self._migration_notes),
            ))

        if self._known_issues:
            sections.append(ReleaseSection(
                title="Known Issues",
                entries=list(self._known_issues),
            ))

        return sections

    def _format_entry(self, commit: CommitEntry) -> str:
        short_hash = commit.hash[:7] if len(commit.hash) >= 7 else commit.hash
        prefix = f"**{commit.scope}** " if commit.scope else ""
        description = commit.description.strip()
        entry = f"- {prefix}{description} ({short_hash})"
        if commit.author:
            entry += f" - @{commit.author}"
        return entry

    def _build_markdown(self, sections: list[ReleaseSection]) -> str:
        lines: list[str] = []

        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"**Version:** `{self.version}`  ")
        lines.append(f"**Date:** {self.date}  ")
        lines.append("")

        if self._commits:
            authors = sorted({c.author for c in self._commits if c.author})
            if authors:
                author_list = ", ".join(f"@{a}" for a in authors)
                lines.append(f"**Contributors:** {author_list}")
                lines.append("")

        lines.append("---")
        lines.append("")

        features_count = sum(
            1 for c in self._commits if c.type in self.FEATURE_TYPES
        )
        fixes_count = sum(
            1 for c in self._commits if c.type in self.FIX_TYPES
        )
        breaking_count = sum(
            1 for c in self._commits if c.is_breaking
        )

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- ✨ **New Features:** {features_count}")
        lines.append(f"- 🐛 **Bug Fixes:** {fixes_count}")
        if breaking_count > 0:
            lines.append(f"- ⚠️  **Breaking Changes:** {breaking_count}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for section in sections:
            emoji = self._section_emoji(section.title)
            lines.append(f"## {emoji} {section.title}")
            lines.append("")
            for entry in section.entries:
                lines.append(entry)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(
            f"*Generated by ICYQuant ReleaseNotesGenerator on "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        )

        return "\n".join(lines)

    @staticmethod
    def _section_emoji(title: str) -> str:
        emoji_map = {
            "Breaking Changes": "⚠️",
            "New Features": "✨",
            "Bug Fixes": "🐛",
            "API Changes": "🔌",
            "Performance Improvements": "⚡",
            "Refactored": "♻️",
            "Documentation": "📝",
            "Migration Guide": "📦",
            "Known Issues": "❗",
        }
        return emoji_map.get(title, "📌")

    @staticmethod
    def from_changelog(
        version: str,
        changelog_path: str,
    ) -> ReleaseNotesResult:
        generator = ReleaseNotesGenerator(version)

        try:
            with open(changelog_path, "r", encoding="utf-8") as f:
                content = f.read()

            sections = re.split(r"\n## ", content)
            for section in sections:
                if not section.strip():
                    continue

                title_match = re.match(r"^(.+)$", section, re.MULTILINE)
                if not title_match:
                    continue

                lines = section.split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("- ") or line.startswith("* "):
                        message = line[2:].strip()
                        generator.add_commit(
                            "",
                            message,
                            author="changelog",
                        )
        except (OSError, IOError):
            pass

        return generator.generate()