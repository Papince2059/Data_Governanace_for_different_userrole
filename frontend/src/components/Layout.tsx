import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  Files,
  ShieldAlert,
  LogOut,
  Users,
  Shield,
  Building2,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const DEMO_USERS = [
  { name: 'Alice Smith', email: 'alice@acme.com', role: 'HR Analyst', dept: 'HR' },
  { name: 'Helen Vance', email: 'helen@acme.com', role: 'HR Manager', dept: 'HR' },
  { name: 'Bob Miller', email: 'bob@acme.com', role: 'Finance Analyst', dept: 'Finance' },
  { name: 'Frank Castle', email: 'frank@acme.com', role: 'Finance Manager', dept: 'Finance' },
  { name: 'Charlie Davis', email: 'charlie@acme.com', role: 'Sales Executive', dept: 'Sales' },
  { name: 'Sara Connor', email: 'sara@acme.com', role: 'Sales Manager', dept: 'Sales' },
  { name: 'David Bowman', email: 'david@acme.com', role: 'IT Engineer', dept: 'IT' },
  { name: 'Irene Adler', email: 'irene@acme.com', role: 'IT Administrator', dept: 'IT' },
  { name: 'Administrator', email: 'admin@acme.com', role: 'System Admin', dept: 'Admin' },
];

export const Layout: React.FC = () => {
  const { user, logout, switchUserQuick } = useAuth();
  const navigate = useNavigate();

  const handleQuickSwitch = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedEmail = e.target.value;
    if (selectedEmail) {
      await switchUserQuick(selectedEmail);
    }
  };

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col justify-between shrink-0">
        <div>
          {/* Header */}
          <div className="p-4 border-b border-slate-800 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400">
              <Shield size={22} />
            </div>
            <div>
              <h1 className="font-semibold text-sm text-slate-100 leading-tight">Data Governance</h1>
              <p className="text-[11px] text-teal-400 font-mono">OpenFGA + pgvector</p>
            </div>
          </div>

          {/* Quick User Switcher Demo Dropdown */}
          <div className="p-3 bg-slate-900/80 border-b border-slate-800">
            <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Switch Persona (Demo)
            </label>
            <select
              value={user?.email || ''}
              onChange={handleQuickSwitch}
              className="w-full bg-slate-800 border border-slate-700 text-xs rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-teal-500"
            >
              {DEMO_USERS.map((u) => (
                <option key={u.email} value={u.email}>
                  {u.name} ({u.dept})
                </option>
              ))}
            </select>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <NavLink
              to="/chat"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-teal-600/20 text-teal-300 border border-teal-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`
              }
            >
              <MessageSquare size={18} />
              <span>Secure Chat (RAG)</span>
            </NavLink>

            <NavLink
              to="/documents"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-teal-600/20 text-teal-300 border border-teal-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`
              }
            >
              <Files size={18} />
              <span>Documents</span>
            </NavLink>

            {user?.is_admin && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-teal-600/20 text-teal-300 border border-teal-500/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                  }`
                }
              >
                <ShieldAlert size={18} />
                <span>Admin ReBAC</span>
              </NavLink>
            )}
          </nav>
        </div>

        {/* User Card & Logout */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-xs text-teal-400 shrink-0">
                {user?.full_name ? user.full_name[0] : 'U'}
              </div>
              <div className="overflow-hidden">
                <p className="text-xs font-medium text-slate-200 truncate">{user?.full_name}</p>
                <p className="text-[11px] text-slate-400 truncate flex items-center gap-1">
                  <Building2 size={10} />
                  <span>{user?.department_name || 'Organization Admin'}</span>
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition-colors"
            >
              <LogOut size={16} />
            </button>
          </div>
          <div className="text-[10px] text-slate-500 font-mono text-center pt-1 border-t border-slate-900">
            Tenant: {user?.tenant_id ? user.tenant_id.slice(0, 8) : 'Acme'}...
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;

