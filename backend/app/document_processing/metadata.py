"""Metadata Extraction and Date Parsing Utilities.

Provides robust utilities for parsing heterogeneous date formats (PDF timestamps,
ISO 8601 strings, Word doc properties) and extracting YAML/frontmatter metadata.
"""

import re
from datetime import UTC, datetime
from typing import Any

# PDF date format regex: D:YYYYMMDDHHmmSSOHH'mm'
_PDF_DATE_REGEX = re.compile(
    r"^D:(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?:(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2}))?"
    r"(?:(?P<tz_sign>[+\-Zz])(?:(?P<tz_hour>\d{2})'?(?P<tz_min>\d{2})'?)?)?"
)


class MetadataParser:
    """Utilities for parsing and standardizing document metadata attributes."""

    @staticmethod
    def parse_pdf_date(date_str: str | None) -> datetime | None:
        """Parse standard PDF creation/modification timestamp strings (e.g., `D:20260805153000Z`).

        Args:
            date_str: Raw PDF date string.

        Returns:
            datetime | None: UTC timezone-aware datetime instance or None if invalid.
        """
        if not date_str or not isinstance(date_str, str):
            return None

        clean_str = date_str.strip()
        match = _PDF_DATE_REGEX.match(clean_str)
        if not match:
            # Fall back to generic ISO parser
            return MetadataParser.parse_iso_date(clean_str)

        try:
            parts = match.groupdict()
            year = int(parts["year"])
            month = int(parts["month"])
            day = int(parts["day"])
            hour = int(parts.get("hour") or 0)
            minute = int(parts.get("minute") or 0)
            second = int(parts.get("second") or 0)

            dt = datetime(year, month, day, hour, minute, second, tzinfo=UTC)
            return dt
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_iso_date(date_str: str | None) -> datetime | None:
        """Attempt to parse standard ISO-8601 datetime strings or timestamps."""
        if not date_str or not isinstance(date_str, str):
            return None

        clean_str = date_str.strip()
        # Handle trailing Z
        if clean_str.endswith("Z") or clean_str.endswith("z"):
            clean_str = clean_str[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        """Extract YAML-style frontmatter headers from markdown or plain text documents.

        Args:
            text: Raw document text string.

        Returns:
            tuple[dict[str, Any], str]: Extracted key-value dictionary and residual text without header.
        """
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text

        header_content = parts[1].strip()
        remaining_text = parts[2].strip()

        metadata: dict[str, Any] = {}
        for line in header_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                clean_key = key.strip().lower().replace(" ", "_")
                clean_val = val.strip().strip("\"'")
                metadata[clean_key] = clean_val

        return metadata, remaining_text
