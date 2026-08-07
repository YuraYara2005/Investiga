import React from 'react';
import { Badge } from './Badge';
import type {
  DocumentCategory,
  EmbeddingStatus,
  ProcessingStatus,
} from '@/types/knowledge';
import type { ComponentStatus } from '@/types/health';

interface CategoryBadgeProps {
  category: DocumentCategory;
}

export const CategoryBadge: React.FC<CategoryBadgeProps> = ({ category }) => {
  switch (category) {
    case 'RUNBOOK':
      return <Badge variant="cyan">Runbook</Badge>;
    case 'INCIDENT_REPORT':
      return <Badge variant="destructive">Incident Report</Badge>;
    case 'MANUAL':
      return <Badge variant="default">Manual</Badge>;
    case 'CONFIGURATION':
      return <Badge variant="warning">Configuration</Badge>;
    case 'POLICY':
      return <Badge variant="secondary">Policy</Badge>;
    default:
      return <Badge variant="outline">Other</Badge>;
  }
};

interface ProcessingStatusBadgeProps {
  status: ProcessingStatus;
}

export const ProcessingStatusBadge: React.FC<ProcessingStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'READY':
      return (
        <Badge variant="success" dot>
          Ready
        </Badge>
      );
    case 'PROCESSING':
    case 'VALIDATING':
      return (
        <Badge variant="warning" dot pulse>
          {status === 'VALIDATING' ? 'Validating' : 'Processing'}
        </Badge>
      );
    case 'UPLOADED':
      return (
        <Badge variant="secondary" dot>
          Uploaded
        </Badge>
      );
    case 'FAILED':
      return (
        <Badge variant="destructive" dot>
          Failed
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
};

interface EmbeddingStatusBadgeProps {
  status: EmbeddingStatus;
}

export const EmbeddingStatusBadge: React.FC<EmbeddingStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'EMBEDDED':
      return (
        <Badge variant="success" dot>
          Indexed
        </Badge>
      );
    case 'QUEUED':
      return (
        <Badge variant="cyan" dot pulse>
          Queued
        </Badge>
      );
    case 'FAILED':
      return (
        <Badge variant="destructive" dot>
          Failed
        </Badge>
      );
    case 'NOT_STARTED':
    default:
      return (
        <Badge variant="secondary" dot>
          Pending
        </Badge>
      );
  }
};

interface HealthStatusBadgeProps {
  status: ComponentStatus;
}

export const HealthStatusBadge: React.FC<HealthStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'healthy':
      return (
        <Badge variant="success" dot>
          Operational
        </Badge>
      );
    case 'degraded':
      return (
        <Badge variant="warning" dot pulse>
          Degraded
        </Badge>
      );
    case 'unhealthy':
      return (
        <Badge variant="destructive" dot pulse>
          Unhealthy
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
};
