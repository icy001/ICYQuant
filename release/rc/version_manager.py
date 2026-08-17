"""
Version management for semantic versioning and release tag generation.

Handles Major.Minor.Patch versioning with pre-release tags (alpha, beta, rc)
and build metadata. Supports version comparison, bumping, and constraint checking.

Usage::

    vm = VersionManager()
    info = vm.parse("1.2.3")
    bumped = vm.bump("1.2.3", part="minor")
    tag = vm.generate_tag("1.2.3", pre_release="rc", pre_release_num=2)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class PreReleaseTag(str, Enum):
    """Pre-release tag types for version strings."""

    ALPHA = "alpha"
    BETA = "beta"
    RC = "rc"


# Semantic version pattern: [v]major.minor.patch[-pre[.num]][+build]
# Supports: v1.2.3, v1.2.3-alpha1, v1.2.3-alpha.1, v1.2.3-rc.1,
#           v1.2.3-alpha1-rc1, v1.2.3+build.42
_VERSION_RE = re.compile(
    r"^[vV]?"
    r"(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[a-zA-Z]+)\.?(?P<pre_num>[0-9]+)?(?P<sub_tag>-[a-zA-Z]+[0-9]+)*)?"
    r"(?:\+(?P<build>[a-zA-Z0-9.-]+))?$"
)


@dataclass
class VersionInfo:
    """Parsed version components and comparison results.

    Attributes:
        major: Major version number (backward-incompatible changes).
        minor: Minor version number (backward-compatible additions).
        patch: Patch version number (backward-compatible fixes).
        pre_release: Pre-release tag type, if any.
        pre_release_num: Pre-release number (e.g., rc.2 → 2).
        sub_tag: Sub-tag after pre-release (e.g., -rc1 in alpha1-rc1).
        build_metadata: Build metadata suffix, if any.
        raw: The raw version string.
    """

    major: int = 0
    minor: int = 0
    patch: int = 0
    pre_release: Optional[PreReleaseTag] = None
    pre_release_num: Optional[int] = None
    sub_tag: Optional[str] = None
    build_metadata: Optional[str] = None
    raw: str = ""

    def to_string(self) -> str:
        """Reconstruct the canonical version string.

        Returns:
            Formatted semantic version string.
        """
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release is not None:
            base += f"-{self.pre_release.value}"
            if self.pre_release_num is not None:
                base += f".{self.pre_release_num}"
            if self.sub_tag:
                base += f"-{self.sub_tag.lstrip('-')}"
        if self.build_metadata:
            base += f"+{self.build_metadata}"
        return base

    def _cmp_tuple(self) -> Tuple:
        """Return a tuple suitable for version comparison.

        Pre-release versions sort lower than the release.
        Release versions have pre_release=inf.
        Sub-tag is used as a tiebreaker when pre-release tags match.

        Returns:
            Comparison tuple: (major, minor, patch, pre_sort, pre_num, sub_tag_sort).
        """
        pre_sort = float("inf") if self.pre_release is None else self._pre_order()
        pre_num = self.pre_release_num if self.pre_release_num is not None else 0
        sub_tag_sort = self.sub_tag or ""
        return (self.major, self.minor, self.patch, pre_sort, pre_num, sub_tag_sort)

    def _pre_order(self) -> int:
        """Return the sort order index for a pre-release tag.

        alpha < beta < rc < release

        Returns:
            Ordinal position of the pre-release tag.
        """
        order = {PreReleaseTag.ALPHA: 0, PreReleaseTag.BETA: 1, PreReleaseTag.RC: 2}
        return order.get(self.pre_release, -1)  # type: ignore[arg-type]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionInfo):
            return NotImplemented
        return self._cmp_tuple() == other._cmp_tuple()

    def __lt__(self, other: VersionInfo) -> bool:
        return self._cmp_tuple() < other._cmp_tuple()

    def __le__(self, other: VersionInfo) -> bool:
        return self._cmp_tuple() <= other._cmp_tuple()

    def __gt__(self, other: VersionInfo) -> bool:
        return self._cmp_tuple() > other._cmp_tuple()

    def __ge__(self, other: VersionInfo) -> bool:
        return self._cmp_tuple() >= other._cmp_tuple()

    def __hash__(self) -> int:
        return hash(self._cmp_tuple())

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"VersionInfo({self.to_string()!r})"


class VersionManager:
    """Semantic versioning manager.

    Parses, compares, bumps, and generates semantic versions.

    Usage::

        vm = VersionManager()
        info = vm.parse("2.1.0-rc.3+build.456")
        bumped = vm.bump("2.1.0", part="minor")
        tag = vm.generate_release_tag("2.1.0", pre_release="beta", pre_release_num=1)
    """

    def parse(self, version: str) -> VersionInfo:
        """Parse a semantic version string into VersionInfo.

        Args:
            version: A semantic version string (e.g., "1.2.3-rc.1+build.42").

        Returns:
            Parsed VersionInfo with all components.

        Raises:
            ValueError: If the version string is not valid semver.
        """
        m = _VERSION_RE.match(version.strip())
        if not m:
            raise ValueError(f"Invalid semantic version: {version!r}")

        pre_tag = None
        pre_num = None
        sub_tag = None
        if m.group("pre"):
            try:
                pre_tag = PreReleaseTag(m.group("pre").lower())
            except ValueError:
                raise ValueError(
                    f"Unknown pre-release tag: {m.group('pre')!r} in version {version!r}"
                )
            pre_num = int(m.group("pre_num")) if m.group("pre_num") else None
            sub_tag = m.group("sub_tag")  # e.g., "-rc1"

        return VersionInfo(
            major=int(m.group("major")),
            minor=int(m.group("minor")),
            patch=int(m.group("patch")),
            pre_release=pre_tag,
            pre_release_num=pre_num,
            sub_tag=sub_tag,
            build_metadata=m.group("build"),
            raw=version.strip(),
        )

    def compare(self, v1: str, v2: str) -> int:
        """Compare two version strings.

        Args:
            v1: First version string.
            v2: Second version string.

        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2.
        """
        info1 = self.parse(v1)
        info2 = self.parse(v2)
        if info1 < info2:
            return -1
        if info1 > info2:
            return 1
        return 0

    def bump(
        self,
        version: str,
        part: str = "patch",
        pre_release: Optional[PreReleaseTag] = None,
        pre_release_num: Optional[int] = None,
        build_metadata: Optional[str] = None,
    ) -> VersionInfo:
        """Bump a version by the specified part.

        Args:
            version: Current version string.
            part: Component to bump ("major", "minor", "patch").
            pre_release: Optional pre-release tag to attach.
            pre_release_num: Optional pre-release number.
            build_metadata: Optional build metadata suffix.

        Returns:
            New VersionInfo after bumping.

        Raises:
            ValueError: If part is not one of major/minor/patch.
        """
        info = self.parse(version)
        part = part.lower()

        if part == "major":
            info.major += 1
            info.minor = 0
            info.patch = 0
        elif part == "minor":
            info.minor += 1
            info.patch = 0
        elif part == "patch":
            info.patch += 1
        else:
            raise ValueError(f"Invalid bump part: {part!r}. Use 'major', 'minor', or 'patch'.")

        info.pre_release = pre_release
        info.pre_release_num = pre_release_num
        info.build_metadata = build_metadata
        info.raw = ""

        if not info.raw:
            info.raw = info.to_string()

        return info

    def bump_prerelease(
        self,
        version: str,
        pre_release: PreReleaseTag,
        pre_release_num: int = 1,
    ) -> VersionInfo:
        """Bump the pre-release number for a given tag.

        If the current version has the same pre-release tag, the number is
        incremented. Otherwise the base patch version is kept and the new
        pre-release tag/number is applied.

        Args:
            version: Current version string.
            pre_release: Pre-release tag type.
            pre_release_num: Starting pre-release number.

        Returns:
            New VersionInfo with bumped pre-release.
        """
        info = self.parse(version)

        if info.pre_release == pre_release and info.pre_release_num is not None:
            info.pre_release_num += 1
        else:
            info.pre_release = pre_release
            info.pre_release_num = pre_release_num

        info.raw = info.to_string()
        return info

    def generate_tag(
        self,
        version: str,
        pre_release: Optional[PreReleaseTag] = None,
        pre_release_num: Optional[int] = None,
        build_metadata: Optional[str] = None,
        prefix: str = "",
    ) -> str:
        """Generate a version string and release tag.

        Args:
            version: Base version string (e.g., "1.2.3").
            pre_release: Pre-release tag to attach.
            pre_release_num: Pre-release number.
            build_metadata: Build metadata suffix.
            prefix: Optional tag prefix (e.g., "v" → "v1.2.3").

        Returns:
            Formatted tag string.
        """
        info = self.parse(version)
        if pre_release is not None:
            info.pre_release = pre_release
            info.pre_release_num = pre_release_num
        if build_metadata is not None:
            info.build_metadata = build_metadata
        return f"{prefix}{info.to_string()}"

    def generate_release_tag(
        self,
        version: str,
        pre_release: Optional[PreReleaseTag] = None,
        pre_release_num: Optional[int] = None,
        prefix: str = "v",
    ) -> str:
        """Generate a release tag string.

        Convenience wrapper around generate_tag with a default "v" prefix.

        Args:
            version: Base version (e.g., "1.2.3").
            pre_release: Optional pre-release tag.
            pre_release_num: Optional pre-release number.
            prefix: Tag prefix (default "v").

        Returns:
            Release tag (e.g., "v1.2.3-rc.1").
        """
        return self.generate_tag(
            version,
            pre_release=pre_release,
            pre_release_num=pre_release_num,
            prefix=prefix,
        )

    def check_constraint(
        self,
        version: str,
        constraint: str,
    ) -> bool:
        """Check if a version satisfies a constraint.

        Supported constraint formats:
        - "1.2.3"     exact match
        - ">=1.0.0"   greater than or equal
        - ">1.0.0"    greater than
        - "<=2.0.0"   less than or equal
        - "<2.0.0"    less than
        - "~1.2.0"    compatible with (~1.2.0 → >=1.2.0, <1.3.0)
        - "^1.2.3"    caret (^1.2.3 → >=1.2.3, <2.0.0)

        Args:
            version: Version to check.
            constraint: Constraint expression.

        Returns:
            True if the version satisfies the constraint.

        Raises:
            ValueError: If the constraint format is not recognized.
        """
        ver = self.parse(version)
        constraint = constraint.strip()

        if constraint.startswith(">="):
            target = self.parse(constraint[2:])
            return ver >= target
        if constraint.startswith(">"):
            target = self.parse(constraint[1:])
            return ver > target
        if constraint.startswith("<="):
            target = self.parse(constraint[2:])
            return ver <= target
        if constraint.startswith("<"):
            target = self.parse(constraint[1:])
            return ver < target
        if constraint.startswith("~"):
            target = self.parse(constraint[1:])
            upper = VersionInfo(major=target.major, minor=target.minor + 1, patch=0)
            return ver >= target and ver < upper
        if constraint.startswith("^"):
            target = self.parse(constraint[1:])
            upper = VersionInfo(major=target.major + 1, minor=0, patch=0)
            return ver >= target and ver < upper

        target = self.parse(constraint)
        return ver == target

    def list_prereleases(
        self,
        base_version: str,
        pre_release: PreReleaseTag,
        start: int = 1,
        end: int = 10,
    ) -> List[str]:
        """Generate a list of pre-release version strings.

        Args:
            base_version: Base version (e.g., "1.2.3").
            pre_release: Pre-release tag type.
            start: Starting pre-release number.
            end: Ending pre-release number (inclusive).

        Returns:
            List of version strings (e.g., ["1.2.3-alpha.1", "1.2.3-alpha.2"]).
        """
        results: List[str] = []
        for n in range(start, end + 1):
            results.append(self.generate_tag(
                base_version,
                pre_release=pre_release,
                pre_release_num=n,
            ))
        return results