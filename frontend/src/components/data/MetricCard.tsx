import React from 'react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/Card';

export interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
    label?: string;
  };
  badge?: React.ReactNode;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  badge,
  className,
}) => {
  return (
    <Card className={cn('p-5 flex flex-col justify-between relative overflow-hidden', className)}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {title}
          </p>
          <div className="text-2xl font-bold font-mono tracking-tight text-foreground">
            {value}
          </div>
        </div>
        {icon && (
          <div className="h-10 w-10 rounded-lg bg-muted/60 text-foreground flex items-center justify-center border border-border/40 flex-shrink-0">
            {icon}
          </div>
        )}
      </div>

      {(subtitle || trend || badge) && (
        <div className="mt-4 flex items-center justify-between text-xs pt-3 border-t border-border/40">
          <div className="flex items-center gap-2">
            {trend && (
              <span
                className={cn(
                  'font-medium font-mono',
                  trend.isPositive ? 'text-emerald-500' : 'text-rose-500'
                )}
              >
                {trend.isPositive ? '+' : ''}
                {trend.value}
              </span>
            )}
            {subtitle && <span className="text-muted-foreground truncate">{subtitle}</span>}
          </div>
          {badge && <div>{badge}</div>}
        </div>
      )}
    </Card>
  );
};
