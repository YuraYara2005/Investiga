"""Enterprise ETL Subsystem for Investiga.

Provides modular multi-source data extraction, recursive filesystem loading,
resumable pipeline orchestration, and integration with the core document ingestion engine.
"""

from app.etl.exceptions import (
    ETLDiscoveryException,
    ETLException,
    ETLJobCancelledException,
    ETLJobExecutionException,
    ETLJobNotFoundException,
    ETLLoaderException,
    ETLLoadException,
    ETLPipelineException,
    ETLUnsupportedSourceException,
    ETLValidationException,
)
from app.etl.interfaces import (
    BaseLoaderInterface,
    ETLPipelineInterface,
    ETLRegistryInterface,
    ETLSchedulerInterface,
)
from app.etl.loaders import (
    APILoader,
    BaseLoader,
    ConfluenceLoader,
    FilesystemLoader,
    GDriveLoader,
    GitHubLoader,
    NotionLoader,
    SharePointLoader,
    WebsiteLoader,
)
from app.etl.models import (
    ETLConfiguration,
    ETLDiscoveredItem,
    ETLDocumentStreamItem,
    ETLJob,
    ETLJobStatus,
    ETLResult,
    ETLSource,
    ETLStatistics,
)
from app.etl.pipeline import ETLPipeline
from app.etl.registry import LoaderRegistry, get_loader_registry
from app.etl.scheduler import ETLScheduler, ScheduledETLEntry, ScheduleFrequency
from app.etl.service import ETLService

__all__ = [
    "APILoader",
    "BaseLoader",
    "BaseLoaderInterface",
    "ConfluenceLoader",
    "ETLConfiguration",
    "ETLDiscoveredItem",
    "ETLDiscoveryException",
    "ETLDocumentStreamItem",
    "ETLException",
    "ETLJob",
    "ETLJobCancelledException",
    "ETLJobExecutionException",
    "ETLJobNotFoundException",
    "ETLJobStatus",
    "ETLLoadException",
    "ETLLoaderException",
    "ETLPipeline",
    "ETLPipelineException",
    "ETLPipelineInterface",
    "ETLRegistryInterface",
    "ETLResult",
    "ETLScheduler",
    "ETLSchedulerInterface",
    "ETLService",
    "ETLSource",
    "ETLStatistics",
    "ETLUnsupportedSourceException",
    "ETLValidationException",
    "FilesystemLoader",
    "GDriveLoader",
    "GitHubLoader",
    "LoaderRegistry",
    "NotionLoader",
    "ScheduleFrequency",
    "ScheduledETLEntry",
    "SharePointLoader",
    "WebsiteLoader",
    "get_loader_registry",
]
