"""Feature Catalog — organize features into logical categories.

Provides category management and hierarchical feature browsing,
enabling users to discover features by domain.

Usage::

    from services.feature_store import FeatureCatalog, FeatureCategory

    catalog = FeatureCatalog()
    catalog.create_category("price", "Price-based features")
    catalog.assign("ema20", "price")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class FeatureCategory:
    """A logical grouping of related features.

    Attributes:
        name: Unique category identifier (e.g. "price", "fundamental").
        description: Human-readable description.
        parent: Parent category name for hierarchy, or None.
        created_at: Unix timestamp of creation.
    """

    name: str
    description: str = ""
    parent: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class FeatureCatalog:
    """Manages feature categories and assignments.

    Supports hierarchical categories and search by category.
    """

    # ---- 分组：初始化 ----

    def __init__(self) -> None:
        self._categories: Dict[str, FeatureCategory] = {}
        self._assignments: Dict[str, str] = {}  # feature_name -> category_name

    # ---- 分组：分类管理 ----

    def create_category(
        self,
        name: str,
        description: str = "",
        parent: Optional[str] = None,
    ) -> FeatureCategory:
        """Create a new feature category.

        Args:
            name: Unique category name.
            description: Human-readable description.
            parent: Optional parent category for hierarchy.

        Returns:
            The created FeatureCategory.

        Raises:
            ValueError: If category already exists.
        """
        if name in self._categories:
            raise ValueError(f"Category '{name}' already exists.")
        if parent is not None and parent not in self._categories:
            raise ValueError(f"Parent category '{parent}' not found.")

        cat = FeatureCategory(name=name, description=description, parent=parent)
        self._categories[name] = cat
        return cat

    def get_category(self, name: str) -> FeatureCategory:
        """Get a category by name.

        Args:
            name: Category name.

        Returns:
            The FeatureCategory.

        Raises:
            KeyError: If category not found.
        """
        if name not in self._categories:
            raise KeyError(f"Category '{name}' not found.")
        return self._categories[name]

    def list_categories(self) -> List[FeatureCategory]:
        """List all categories sorted by name.

        Returns:
            List of FeatureCategory.
        """
        cats = list(self._categories.values())
        cats.sort(key=lambda c: c.name)
        return cats

    def get_children(self, parent_name: str) -> List[FeatureCategory]:
        """Get direct child categories.

        Args:
            parent_name: Parent category name.

        Returns:
            List of child FeatureCategory.

        Raises:
            KeyError: If parent category not found.
        """
        if parent_name not in self._categories:
            raise KeyError(f"Parent category '{parent_name}' not found.")
        children = [c for c in self._categories.values() if c.parent == parent_name]
        children.sort(key=lambda c: c.name)
        return children

    def get_tree(self) -> Dict[str, object]:
        """Build a hierarchical tree representation.

        Returns:
            Dict with category names as keys, each containing info and children.
        """

        def _build_node(name: str) -> Dict[str, object]:
            cat = self._categories[name]
            children = {}
            for child in self.get_children(name):
                children[child.name] = _build_node(child.name)
            return {
                "description": cat.description,
                "children": children,
            }

        # Find roots (categories with no parent)
        roots = [c for c in self._categories.values() if c.parent is None]
        tree: Dict[str, object] = {}
        for root in roots:
            tree[root.name] = _build_node(root.name)
        return tree

    # ---- 分组：特征分配 ----

    def assign(self, feature_name: str, category_name: str) -> None:
        """Assign a feature to a category.

        Args:
            feature_name: Feature name.
            category_name: Category to assign to.

        Raises:
            KeyError: If category not found.
        """
        if category_name not in self._categories:
            raise KeyError(f"Category '{category_name}' not found.")
        self._assignments[feature_name] = category_name

    def unassign(self, feature_name: str) -> None:
        """Remove a feature from its category.

        Args:
            feature_name: Feature name.
        """
        self._assignments.pop(feature_name, None)

    def get_feature_category(self, feature_name: str) -> Optional[str]:
        """Get the category assigned to a feature.

        Args:
            feature_name: Feature name.

        Returns:
            Category name or None if not assigned.
        """
        return self._assignments.get(feature_name)

    def list_by_category(self, category_name: str) -> List[str]:
        """List all feature names in a category.

        Args:
            category_name: Category name.

        Returns:
            Sorted list of feature names.

        Raises:
            KeyError: If category not found.
        """
        if category_name not in self._categories:
            raise KeyError(f"Category '{category_name}' not found.")
        features = [
            name for name, cat in self._assignments.items() if cat == category_name
        ]
        features.sort()
        return features

    def get_assignment_map(self) -> Dict[str, str]:
        """Get the full feature -> category assignment map.

        Returns:
            Dict of feature_name -> category_name.
        """
        return dict(self._assignments)
