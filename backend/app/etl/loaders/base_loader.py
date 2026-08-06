"""Base ETL Loader Abstract Base Class.

Provides shared filtering, pattern matching, validation, and template methods
for all specialized and enterprise data loader implementations.
"""

from __future__ import annotations

import fnmatch
from abc import ABC
from pathlib import PurePath
from typing import ClassVar

from app.core.logging import get_logger
from app.etl.exceptions import ETLValidationException
from app.etl.interfaces import BaseLoaderInterface
from app.etl.models import ETLConfiguration, ETLSource

logger = get_logger(__name__)


class BaseLoader(BaseLoaderInterface, ABC):
    """Abstract base class for all ETL loader implementations."""

    SOURCE_TYPE: ClassVar[ETLSource]

    def supports(self, source_type: ETLSource | str) -> bool:
        """Evaluate whether this loader handles the given source type."""
        target = (
            source_type.value
            if isinstance(source_type, ETLSource)
            else str(source_type).lower()
        )
        return target == self.SOURCE_TYPE.value

    def _matches_filters(
        self,
        rel_path: str,
        filename: str,
        extension: str,
        config: ETLConfiguration,
    ) -> bool:
        """Evaluate inclusion/exclusion glob patterns, hidden files, and extension constraints."""
        # 1. Hidden file/folder filtering
        if config.ignore_hidden:
            parts = PurePath(rel_path).parts
            if any(p.startswith(".") and p != "." and p != ".." for p in parts):
                return False
            if filename.startswith(".") and filename not in {".dockerfile"}:
                return False

        # 2. Extension filtering
        if config.allowed_extensions is not None:
            norm_exts = {
                e.lower() if e.startswith(".") else f".{e.lower()}"
                for e in config.allowed_extensions
            }
            if extension.lower() not in norm_exts:
                return False

        # 3. Exclude patterns (e.g. *.tmp, node_modules/*, .git/*)
        if config.exclude_patterns:
            for pattern in config.exclude_patterns:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                    filename, pattern
                ):
                    return False

        # 4. Include patterns (default: ['*'])
        if config.include_patterns:
            matched_include = False
            for pattern in config.include_patterns:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                    filename, pattern
                ):
                    matched_include = True
                    break
            if not matched_include:
                return False

        return True

    def validate(self, config: ETLConfiguration) -> bool:
        """Validate generic configuration parameters."""
        if not config.source_path_or_uri or not config.source_path_or_uri.strip():
            raise ETLValidationException(
                message="Source path or URI cannot be empty.",
                source=self.SOURCE_TYPE.value,
            )
        if config.batch_size <= 0:
            raise ETLValidationException(
                message="Batch size must be a positive integer.",
                source=self.SOURCE_TYPE.value,
            )
        return True
