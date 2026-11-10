import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Plus,
  MinusCircle,
  Users,
  Building,
  KeyRound,
  Loader2,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import type { Department, Group, User } from '../types';

export const AdminPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);

  // Permission Checker State
  const [checkUser, setCheckUser] = useState('alice');
  const [checkRelation, setCheckRelation] = useState('can_read');
  const [checkResource, setCheckResource] = useState('document:doc_salary_records');
  const [checkResult, setCheckResult] = useState<{ allowed: boolean } | null>(null);
  const [checking, setChecking] = useState(false);

  // Grant / Revoke Form State
  const [actionSubject, setActionSubject] = useState('user:alice');
  const [actionRelation, setActionRelation] = useState('viewer');
  const [actionResource, setActionResource] = useState('document:doc_salary_records');
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [u, d, g] = await Promise.all([
          api.getUsers(),
          api.getDepartments(),
          api.getGroups(),
        ]);
        setUsers(u);
        setDepartments(d);
        setGroups(g);
      } catch (err) {
        console.error('Failed to load admin metadata', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleRunCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    setChecking(true);
    setCheckResult(null);
    try {
      const res = await api.checkPermission(
        checkUser,
        checkRelation,
        'document',
        checkResource
      );
      setCheckResult({ allowed: res.allowed });
    } catch (err: any) {
      alert(err.response?.data?.message || 'Check failed');
    } finally {
      setChecking(false);
    }
  };

  const handleGrant = async () => {
    setActionStatus(null);
    try {
      await api.grantPermission(actionSubject, actionRelation, 'document', actionResource);
      setActionStatus(`✓ Successfully granted '${actionRelation}' on '${actionResource}' to '${actionSubject}'`);
    } catch (err: any) {
      setActionStatus(`✗ Error granting permission: ${err.response?.data?.message || err.message}`);
    }
  };

  const handleRevoke = async () => {
    setActionStatus(null);
    try {
      await api.revokePermission(actionSubject, actionRelation, 'document', actionResource);
      setActionStatus(`✓ Successfully revoked '${actionRelation}' on '${actionResource}' from '${actionSubject}'`);
    } catch (err: any) {
      setActionStatus(`✗ Error revoking permission: ${err.response?.data?.message || err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-xs">
        <Loader2 className="animate-spin mr-2" size={18} />
        Loading administrative console...
      </div>
    );
  }

  return (
    <div className="p-6 bg-slate-900 overflow-y-auto space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <ShieldAlert className="text-teal-400" />
          <span>OpenFGA Zanzibar ReBAC Administration</span>
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Live inspection and manipulation of OpenFGA relationship tuples, users, and departments.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Live Permission Evaluator */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-xl">
          <h2 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <KeyRound size={16} className="text-teal-400" />
            <span>Interactive Permission Evaluator</span>
          </h2>
          <p className="text-xs text-slate-400 mb-4">
            Runs an explicit <code className="text-teal-300">OpenFGA Check</code> against the live authorization graph.
          </p>

          <form onSubmit={handleRunCheck} className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-300 mb-1">User Identifier</label>
              <input
                type="text"
                value={checkUser}
                onChange={(e) => setCheckUser(e.target.value)}
                placeholder="e.g. alice, helen, bob, david"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-300 mb-1">Relation</label>
              <select
                value={checkRelation}
                onChange={(e) => setCheckRelation(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
              >
                <option value="can_read">can_read (Computed: Viewer or Editor or Owner)</option>
                <option value="can_write">can_write (Computed: Editor or Owner)</option>
                <option value="viewer">viewer (Direct Viewer)</option>
                <option value="owner">owner (Owner)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-300 mb-1">Resource Object</label>
              <input
                type="text"
                value={checkResource}
                onChange={(e) => setCheckResource(e.target.value)}
                placeholder="e.g. document:doc_salary_records"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
              />
            </div>

            <button
              type="submit"
              disabled={checking}
              className="w-full bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5"
            >
              {checking ? 'Evaluating...' : 'Evaluate Permission in OpenFGA'}
            </button>
          </form>

          {/* Result Banner */}
          {checkResult !== null && (
            <div
              className={`mt-4 p-3 rounded-lg border flex items-center gap-3 ${
                checkResult.allowed
                  ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200'
                  : 'bg-rose-950/60 border-rose-800 text-rose-200'
              }`}
            >
              {checkResult.allowed ? (
                <CheckCircle2 size={20} className="text-emerald-400 shrink-0" />
              ) : (
                <XCircle size={20} className="text-rose-400 shrink-0" />
              )}
              <div className="text-xs">
                <span className="font-bold text-sm block">
                  {checkResult.allowed ? 'ACCESS GRANTED' : 'ACCESS DENIED'}
                </span>
                <span className="text-[11px] opacity-80 font-mono">
                  user:{checkUser} {checkRelation} {checkResource}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 2. Grant / Revoke Permissions */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-xl">
          <h2 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <Layers size={16} className="text-teal-400" />
            <span>Manage Relationship Tuples</span>
          </h2>
          <p className="text-xs text-slate-400 mb-4">
            Directly commit or revoke Zanzibar relationship tuples in OpenFGA in real-time.
          </p>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-300 mb-1">Subject (User or Group#Member)</label>
              <input
                type="text"
                value={actionSubject}
                onChange={(e) => setActionSubject(e.target.value)}
                placeholder="e.g. user:alice or group:hr#member"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-300 mb-1">Relation</label>
              <select
                value={actionRelation}
                onChange={(e) => setActionRelation(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
              >
                <option value="viewer">viewer</option>
                <option value="editor">editor</option>
                <option value="owner">owner</option>
                <option value="member">member</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-300 mb-1">Object</label>
              <input
                type="text"
                value={actionResource}
                onChange={(e) => setActionResource(e.target.value)}
                placeholder="e.g. document:doc_salary_records"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
              />
            </div>

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={handleGrant}
                className="flex-1 bg-emerald-700 hover:bg-emerald-600 text-white font-semibold text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5"
              >
                <Plus size={14} /> Grant Permission
              </button>
              <button
                type="button"
                onClick={handleRevoke}
                className="flex-1 bg-rose-700 hover:bg-rose-600 text-white font-semibold text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5"
              >
                <MinusCircle size={14} /> Revoke Permission
              </button>
            </div>

            {actionStatus && (
              <div className="mt-3 p-2.5 bg-slate-900 border border-slate-700 rounded text-xs font-mono text-teal-300 break-words">
                {actionStatus}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. System Entities Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Users */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Users size={14} className="text-teal-400" />
            <span>Users ({users.length})</span>
          </h3>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {users.map((u) => (
              <div key={u.id} className="p-2 bg-slate-900/60 rounded border border-slate-800/80 text-xs">
                <span className="font-medium text-slate-200 block">{u.full_name}</span>
                <span className="text-[10px] text-slate-400 font-mono">{u.email}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Departments */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Building size={14} className="text-teal-400" />
            <span>Departments ({departments.length})</span>
          </h3>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {departments.map((d) => (
              <div key={d.id} className="p-2 bg-slate-900/60 rounded border border-slate-800/80 text-xs">
                <span className="font-medium text-slate-200 block">{d.name}</span>
                <span className="text-[10px] text-slate-400">{d.description}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Groups */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Layers size={14} className="text-teal-400" />
            <span>Groups ({groups.length})</span>
          </h3>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {groups.map((g) => (
              <div key={g.id} className="p-2 bg-slate-900/60 rounded border border-slate-800/80 text-xs">
                <span className="font-medium text-slate-200 block font-mono text-teal-400">{g.name}</span>
                <span className="text-[10px] text-slate-400">{g.description}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminPage;

