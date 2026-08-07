import React from 'react';
import { cn } from '@/lib/utils';

export interface FormFieldProps {
  label?: string;
  error?: string;
  helperText?: string;
  required?: boolean;
  htmlFor?: string;
  className?: string;
  children: React.ReactNode;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  error,
  helperText,
  required = false,
  htmlFor,
  className,
  children,
}) => {
  return (
    <div className={cn('space-y-1.5 w-full', className)}>
      {label && (
        <label
          htmlFor={htmlFor}
          className="block text-xs font-medium text-foreground tracking-tight"
        >
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </label>
      )}
      <div>{children}</div>
      {error ? (
        <p className="text-[11px] font-medium text-destructive leading-tight">{error}</p>
      ) : helperText ? (
        <p className="text-[11px] text-muted-foreground leading-tight">{helperText}</p>
      ) : null}
    </div>
  );
};
