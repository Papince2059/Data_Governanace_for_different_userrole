import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Lock, Mail, ArrowRight, UserCheck } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const QUICK_USERS = [
  { name: 'Alice Smith', email: 'alice@acme.com', role: 'HR Analyst', dept: 'HR', desc: 'Standard HR docs only' },
  { name: 'Helen Vance', email: 'helen@acme.com', role: 'HR Manager', dept: 'HR', desc: 'All HR docs + Confidential Salaries' },
  { name: 'Bob Miller', email: 'bob@acme.com', role: 'Finance Analyst', dept: 'Finance', desc: 'Standard Finance reports' },
  { name: 'Frank Castle', email: 'frank@acme.com', role: 'Finance Manager', dept: 'Finance', desc: 'All Finance + Forecasts & Payroll' },
  { name: 'Charlie Davis', email: 'charlie@acme.com', role: 'Sales Executive', dept: 'Sales', desc: 'Standard Customer & Pipeline' },
  { name: 'Sara Connor', email: 'sara@acme.com', role: 'Sales Manager', dept: 'Sales', desc: 'All Sales + Pricing Strategy' },
  { name: 'David Bowman', email: 'david@acme.com', role: 'IT Engineer', dept: 'IT', desc: 'Standard IT Runbooks & Architecture' },
  { name: 'Irene Adler', email: 'irene@acme.com', role: 'IT Administrator', dept: 'IT', desc: 'All IT + Incident Reports' },
  { name: 'System Admin', email: 'admin@acme.com', role: 'Administrator', dept: 'Admin', desc: 'ReBAC Management & Audit' },
];

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('alice@acme.com');
  const [password, setPassword] = useState('password123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate('/chat');
    } catch (err: any) {
      setError(err.response?.data?.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectQuickUser = async (userEmail: string) => {
    setEmail(userEmail);
    setPassword('password123');
    setLoading(true);
    try {
      await login(userEmail, 'password123');
      navigate('/chat');
    } catch (err: any) {
      setError(err.response?.data?.message || 'Quick login failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden grid grid-cols-1 md:grid-cols-2">
        {/* Left Side: Credentials Form */}
        <div className="p-8 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400">
                <Shield size={26} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Acme Governance</h2>
                <p className="text-xs text-slate-400">Pre-Retrieval ACL + Zanzibar ReBAC</p>
              </div>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-950/60 border border-red-800 text-red-200 text-xs rounded-lg">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Email Address</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-3 text-slate-500" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
                    placeholder="user@acme.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-3 text-slate-500" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-teal-600 hover:bg-teal-500 text-white font-medium py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 mt-2 shadow-lg shadow-teal-900/30 disabled:opacity-50"
              >
                {loading ? 'Authenticating...' : 'Sign In'}
                <ArrowRight size={16} />
              </button>
            </form>
          </div>

          <div className="text-[11px] text-slate-500 mt-6 text-center">
            Zero-Trust Pre-Retrieval ACL Filtering • OpenFGA Engine
          </div>
        </div>

        {/* Right Side: Quick Persona Selector for Testing */}
        <div className="bg-slate-950/60 p-6 border-t md:border-t-0 md:border-l border-slate-800 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <UserCheck size={14} className="text-teal-400" />
              <span>Select Demo Persona to Test Access</span>
            </h3>
            <p className="text-[11px] text-slate-400 mb-3">
              Click any user to test how their OpenFGA relationships restrict RAG context and document browsing.
            </p>

            <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
              {QUICK_USERS.map((u) => (
                <button
                  key={u.email}
                  type="button"
                  onClick={() => handleSelectQuickUser(u.email)}
                  className="w-full text-left p-2.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-teal-500/50 transition-all flex items-center justify-between group"
                >
                  <div className="overflow-hidden">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-slate-200 group-hover:text-teal-300">
                        {u.name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-teal-400 font-mono">
                        {u.dept}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 truncate">{u.desc}</p>
                  </div>
                  <span className="text-[10px] text-slate-500 group-hover:text-teal-400 font-medium shrink-0">
                    Login →
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="text-[10px] text-slate-500 text-center mt-3 pt-2 border-t border-slate-900">
            All demo passwords: <span className="font-mono text-slate-400">password123</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;

