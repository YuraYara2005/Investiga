
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders button with label', () => {
    render(<Button>Deploy Pipeline</Button>);
    expect(screen.getByRole('button', { name: /Deploy Pipeline/i })).toBeInTheDocument();
  });

  it('shows disabled state when isLoading is true', () => {
    render(<Button isLoading>Deploy Pipeline</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });
});
