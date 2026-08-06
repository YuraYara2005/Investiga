"""ETL Loaders Subpackage for Investiga.

Provides BaseLoader contract, local filesystem implementation, and enterprise
cloud/source loader placeholders.
"""

from app.etl.loaders.api_loader import APILoader
from app.etl.loaders.base_loader import BaseLoader
from app.etl.loaders.confluence_loader import ConfluenceLoader
from app.etl.loaders.filesystem_loader import FilesystemLoader
from app.etl.loaders.gdrive_loader import GDriveLoader
from app.etl.loaders.github_loader import GitHubLoader
from app.etl.loaders.notion_loader import NotionLoader
from app.etl.loaders.sharepoint_loader import SharePointLoader
from app.etl.loaders.website_loader import WebsiteLoader

__all__ = [
    "APILoader",
    "BaseLoader",
    "ConfluenceLoader",
    "FilesystemLoader",
    "GDriveLoader",
    "GitHubLoader",
    "NotionLoader",
    "SharePointLoader",
    "WebsiteLoader",
]
