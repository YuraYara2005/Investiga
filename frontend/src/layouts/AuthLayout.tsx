import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Shield, Lock, Terminal, Cpu } from 'lucide-react';
import { ToastContainer } from '@/components/ui/Toast';

export const AuthLayout: React.FC = () => {
  return (
    <div className="min-h-screen w-screen flex bg-background text-foreground overflow-hidden">
      {/* Left Branding / Cybersecurity Matrix Visual Hero */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-slate-950 flex-col justify-between p-12 overflow-hidden border-r border-border/60">
        {/* Background Grid Pattern & Glows */}
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-30 pointer-events-none" />
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-indigo-600/20 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 rounded-full bg-cyan-500/20 blur-3xl pointer-events-none" />

        {/* Top Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 p-0.5 shadow-lg shadow-cyan-500/20">
            <div className="h-full w-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Shield className="h-5 w-5 text-cyan-400" />
            </div>
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              INVESTIGA
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                Enterprise Core
              </span>
            </h1>
            <p className="text-xs text-slate-400">Incident Intelligence & Knowledge System</p>
          </div>
        </div>

        {/* Center Feature Highlights */}
        <div className="relative z-10 max-w-md space-y-6">
          <div>
            <h2 className="text-2xl font-extrabold text-white tracking-tight leading-snug">
              Rapid incident diagnosis powered by hybrid vector search & domain reasoning.
            </h2>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Equip SREs and security operators with automated runbook ingestion, sub-millisecond semantic retrieval, and real-time diagnostic telemetry.
            </p>
          </div>

          <div className="space-y-3 pt-4 border-t border-slate-800">
            <div className="flex items-start gap-3">
              <div className="h-7 w-7 rounded-md bg-indigo-950/80 border border-indigo-500/30 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Lock className="h-3.5 w-3.5" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-200">Argon2id & Strict RBAC Security</h3>
                <p className="text-[11px] text-slate-400">Hardware-grade password hashing with fine-grained role entitlements.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="h-7 w-7 rounded-md bg-cyan-950/80 border border-cyan-500/30 text-cyan-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Terminal className="h-3.5 w-3.5" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-200">Multi-Format Knowledge Pipeline</h3>
                <p className="text-[11px] text-slate-400">Deterministic SHA-256 deduplication and hybrid vector-keyword retrieval.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="h-7 w-7 rounded-md bg-indigo-950/80 border border-indigo-500/30 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Cpu className="h-3.5 w-3.5" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-slate-200">Observability & Health Probes</h3>
                <p className="text-[11px] text-slate-400">Native Kubernetes liveness/readiness probes with sub-millisecond telemetry.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Metadata */}
        <div className="relative z-10 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>INVESTIGA CLUSTER // SECURE REGION</span>
          <span>BUILD v1.0.0</span>
        </div>
      </div>

      {/* Right Content View (Form card) */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center items-center p-6 sm:p-12">
        <div className="w-full max-w-md space-y-6">
          <div className="lg:hidden flex items-center gap-3 mb-6">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-indigo-600 to-cyan-500 p-0.5 shadow-md">
              <div className="h-full w-full bg-slate-950 rounded-[7px] flex items-center justify-center">
                <Shield className="h-4 w-4 text-cyan-400" />
              </div>
            </div>
            <div>
              <span className="font-bold text-sm text-foreground">INVESTIGA</span>
              <p className="text-[10px] text-muted-foreground">Incident Intelligence Platform</p>
            </div>
          </div>

          <Outlet />

          <div className="text-center text-xs text-muted-foreground pt-4 border-t border-border/40">
            <span>Need system access or credential recovery? </span>
            <Link to="/login" className="text-primary hover:underline font-medium">
              Contact Cluster Admin
            </Link>
          </div>
        </div>
      </div>

      <ToastContainer />
    </div>
  );
};
