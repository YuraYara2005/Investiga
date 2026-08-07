
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  CategoryBadge,
  ProcessingStatusBadge,
  EmbeddingStatusBadge,
  HealthStatusBadge,
} from './StatusBadge';

describe('StatusBadge components', () => {
  it('renders CategoryBadge for RUNBOOK', () => {
    render(<CategoryBadge category="RUNBOOK" />);
    expect(screen.getByText('Runbook')).toBeInTheDocument();
  });

  it('renders ProcessingStatusBadge for READY', () => {
    render(<ProcessingStatusBadge status="READY" />);
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  it('renders EmbeddingStatusBadge for EMBEDDED', () => {
    render(<EmbeddingStatusBadge status="EMBEDDED" />);
    expect(screen.getByText('Indexed')).toBeInTheDocument();
  });

  it('renders HealthStatusBadge for healthy', () => {
    render(<HealthStatusBadge status="healthy" />);
    expect(screen.getByText('Operational')).toBeInTheDocument();
  });
});
