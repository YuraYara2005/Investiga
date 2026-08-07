import React, { useState } from 'react';
import { ShieldCheck, Check, X } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/Table';
import { Input } from '@/components/ui/Input';

interface SystemRole {
  name: string;
  displayName: string;
  description: string;
  permissions: string[];
}

const SYSTEM_ROLES: SystemRole[] = [
  {
    name: 'admin',
    displayName: 'Cluster Administrator',
    description: 'Full administrative access across all resources, cluster configuration, and user identities.',
    permissions: [
      'auth:create',
      'auth:read',
      'auth:update',
      'auth:delete',
      'knowledge:create',
      'knowledge:read',
      'knowledge:update',
      'knowledge:delete',
      'search:execute',
      'chat:execute',
      'eval:execute',
      'eval:read',
      'system:health',
      'system:manage',
    ],
  },
  {
    name: 'analyst',
    displayName: 'Incident Investigator / SRE',
    description: 'Authorized to execute incident queries, ingest runbooks, run RAG sessions, and inspect documents.',
    permissions: [
      'auth:read',
      'knowledge:create',
      'knowledge:read',
      'knowledge:update',
      'search:execute',
      'chat:execute',
      'eval:read',
      'system:health',
    ],
  },
  {
    name: 'viewer',
    displayName: 'Read-Only Auditor',
    description: 'Read-only access to published knowledge documents, runbooks, and cluster health telemetry.',
    permissions: [
      'auth:read',
      'knowledge:read',
      'system:health',
    ],
  },
];

const PERMISSIONS_CATALOG = [
  { code: 'knowledge:create', resource: 'Knowledge Base', action: 'Upload & Ingest Document' },
  { code: 'knowledge:read', resource: 'Knowledge Base', action: 'View & Search Documents' },
  { code: 'knowledge:update', resource: 'Knowledge Base', action: 'Update Metadata & Tags' },
  { code: 'knowledge:delete', resource: 'Knowledge Base', action: 'Soft Delete & Storage Purge' },
  { code: 'search:execute', resource: 'Investigation', action: 'Execute Hybrid Vector Search' },
  { code: 'chat:execute', resource: 'Investigation', action: 'Execute AI Reasoning (RAG)' },
  { code: 'eval:execute', resource: 'Evaluation', action: 'Trigger Benchmark Test Suite' },
  { code: 'eval:read', resource: 'Evaluation', action: 'View Benchmark Scores & Metrics' },
  { code: 'auth:create', resource: 'Identity & Access', action: 'Provision Operator Accounts' },
  { code: 'auth:read', resource: 'Identity & Access', action: 'Inspect User Claims & Profiles' },
  { code: 'auth:update', resource: 'Identity & Access', action: 'Modify Roles & Permissions' },
  { code: 'auth:delete', resource: 'Identity & Access', action: 'Deactivate / Revoke Operators' },
  { code: 'system:health', resource: 'Infrastructure', action: 'Inspect Diagnostic Telemetry' },
  { code: 'system:manage', resource: 'Infrastructure', action: 'Cluster Configuration Updates' },
];

export const RolesMatrixPage: React.FC = () => {
  const [filterQuery, setFilterQuery] = useState('');

  const filteredPermissions = PERMISSIONS_CATALOG.filter(
    (p) =>
      p.code.toLowerCase().includes(filterQuery.toLowerCase()) ||
      p.resource.toLowerCase().includes(filterQuery.toLowerCase()) ||
      p.action.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-rose-400" />
            RBAC Roles & Permission Entitlements Matrix
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Cryptographically enforced role definitions and authorization policies for the Investiga cluster.
          </p>
        </div>
      </div>

      {/* Role Cards Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {SYSTEM_ROLES.map((role) => (
          <Card key={role.name} className="p-5 flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold uppercase text-primary">
                  {role.name}
                </span>
                <Badge variant="cyan" className="font-mono text-[10px]">
                  {role.permissions.length} PERMISSIONS
                </Badge>
              </div>
              <h3 className="text-base font-bold text-foreground mt-2">{role.displayName}</h3>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                {role.description}
              </p>
            </div>

            <div className="pt-3 border-t border-border/40 text-[11px] text-muted-foreground">
              Built-in System Role
            </div>
          </Card>
        ))}
      </div>

      {/* Matrix Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3">
          <div>
            <CardTitle>Resource Authorization Matrix</CardTitle>
            <CardDescription>
              Mapping of granular permissions across defined system roles.
            </CardDescription>
          </div>

          <div className="w-full sm:w-64">
            <Input
              placeholder="Filter permissions..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
            />
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Resource Domain</TableHead>
                  <TableHead className="w-[220px]">Permission Code</TableHead>
                  <TableHead>Operation / Action</TableHead>
                  <TableHead className="text-center w-[120px]">Admin</TableHead>
                  <TableHead className="text-center w-[120px]">Analyst</TableHead>
                  <TableHead className="text-center w-[120px]">Viewer</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {filteredPermissions.map((perm) => (
                  <TableRow key={perm.code}>
                    <TableCell className="font-semibold text-xs text-foreground">
                      {perm.resource}
                    </TableCell>

                    <TableCell className="font-mono text-[11px] text-cyan-400">
                      {perm.code}
                    </TableCell>

                    <TableCell className="text-xs text-muted-foreground">
                      {perm.action}
                    </TableCell>

                    {SYSTEM_ROLES.map((role) => {
                      const hasPerm = role.permissions.includes(perm.code);
                      return (
                        <TableCell key={role.name} className="text-center">
                          {hasPerm ? (
                            <span className="inline-flex h-5 w-5 rounded-full bg-emerald-500/10 text-emerald-400 items-center justify-center">
                              <Check className="h-3.5 w-3.5" />
                            </span>
                          ) : (
                            <span className="inline-flex h-5 w-5 rounded-full bg-muted/40 text-muted-foreground/40 items-center justify-center">
                              <X className="h-3.5 w-3.5" />
                            </span>
                          )}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
