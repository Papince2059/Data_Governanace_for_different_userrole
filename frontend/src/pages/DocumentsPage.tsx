import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  Trash2,
  Search,
  Filter,
  CheckCircle,
  AlertTriangle,
  Clock,
  Loader2,
  X,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';
import type { Department, Document, IngestionJob } from '../types';

export const DocumentsPage: React.FC = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedDept, setSelectedDept] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDesc, setUploadDesc] = useState('');
  const [uploadDeptId, setUploadDeptId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadJobId, setUploadJobId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStatusMsg, setUploadStatusMsg] = useState<string>('');

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const deptId = selectedDept === 'all' ? undefined : selectedDept;
      const [docsData, deptsData] = await Promise.all([
        api.getDocuments(deptId),
        api.getDepartments(),
      ]);
      setDocuments(docsData);
      setDepartments(deptsData);
    } catch (err) {
      console.error('Failed to load documents', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, [selectedDept, user?.email]);

  const handleDelete = async (docId: string, title: string) => {
    if (!window.confirm(`Are you sure you want to delete '${title}'?`)) return;
    try {
      await api.deleteDocument(docId);
      await fetchDocs();
    } catch (err: any) {
      alert(err.response?.data?.message || 'Delete failed.');
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle.trim()) return;

    setUploading(true);
    setUploadProgress(5);
    setUploadStatusMsg('Initiating ingestion pipeline...');

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('title', uploadTitle);
    if (uploadDesc) formData.append('description', uploadDesc);
    if (uploadDeptId) formData.append('department_id', uploadDeptId);

    try {
      const res = await api.uploadDocument(formData);
      setUploadJobId(res.job_id);

      // Listen to SSE progress stream
      const token = localStorage.getItem('access_token');
      const eventSource = new EventSource(
        `/api/v1/ingestion/jobs/${res.job_id}/events`
      );

      eventSource.onmessage = (event) => {
        // Fallback generic
      };

      const eventTypes = [
        'ingestion.started',
        'document.validated',
        'document.extracted',
        'document.chunked',
        'embeddings.generated',
        'permissions.created',
        'document.indexed',
        'ingestion.completed',
        'ingestion.failed',
      ];

      eventTypes.forEach((type) => {
        eventSource.addEventListener(type, (e: any) => {
          try {
            const payload = JSON.parse(e.data);
            setUploadStatusMsg(payload.message || type);

            if (type === 'ingestion.started') setUploadProgress(10);
            else if (type === 'document.validated') setUploadProgress(25);
            else if (type === 'document.extracted') setUploadProgress(40);
            else if (type === 'document.chunked') setUploadProgress(60);
            else if (type === 'embeddings.generated') setUploadProgress(80);
            else if (type === 'permissions.created') setUploadProgress(90);
            else if (type === 'ingestion.completed') {
              setUploadProgress(100);
              eventSource.close();
              setTimeout(() => {
                setIsUploadOpen(false);
                setUploading(false);
                setUploadFile(null);
                setUploadTitle('');
                setUploadDesc('');
                fetchDocs();
              }, 1200);
            } else if (type === 'ingestion.failed') {
              setUploadProgress(100);
              eventSource.close();
              setUploading(false);
              alert('Ingestion failed: ' + payload.message);
            }
          } catch {}
        });
      });

      eventSource.onerror = () => {
        eventSource.close();
      };
    } catch (err: any) {
      setUploading(false);
      alert(err.response?.data?.message || 'Failed to submit document.');
    }
  };

  const filteredDocs = documents.filter((d) =>
    d.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full bg-slate-900 p-6 overflow-y-auto">
      {/* Page Title & Upload Trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <FileText className="text-teal-400" />
            <span>Authorized Enterprise Documents</span>
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Documents visible exclusively to {user?.full_name} via OpenFGA ReBAC relationship evaluation.
          </p>
        </div>

        <button
          onClick={() => setIsUploadOpen(true)}
          className="bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold px-4 py-2.5 rounded-lg flex items-center gap-2 shadow-lg shadow-teal-900/30 transition-colors self-start sm:self-auto"
        >
          <Upload size={16} />
          <span>Upload Document</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 mb-6 flex flex-col md:flex-row items-center gap-3 justify-between">
        {/* Department Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          <button
            onClick={() => setSelectedDept('all')}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors shrink-0 ${
              selectedDept === 'all'
                ? 'bg-teal-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            All Accessible ({documents.length})
          </button>
          {departments.map((dept) => (
            <button
              key={dept.id}
              onClick={() => setSelectedDept(dept.id)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors shrink-0 ${
                selectedDept === dept.id
                  ? 'bg-teal-600 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              {dept.name}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full md:w-64">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500"
          />
        </div>
      </div>

      {/* Documents Table */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400 text-xs">
          <Loader2 className="animate-spin mr-2" size={18} />
          Evaluating OpenFGA graph permissions...
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-12 text-center max-w-lg mx-auto">
          <AlertTriangle className="text-amber-400 mx-auto mb-3" size={28} />
          <h3 className="text-sm font-semibold text-slate-200 mb-1">No Accessible Documents</h3>
          <p className="text-xs text-slate-400 mb-4">
            Under your current persona ({user?.email}), OpenFGA relationship tuples do not grant read permissions to documents in this category.
          </p>
        </div>
      ) : (
        <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-400 font-semibold uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="px-4 py-3">Document Title</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {filteredDocs.map((doc) => {
                const dept = departments.find((d) => d.id === doc.department_id);
                return (
                  <tr key={doc.id} className="hover:bg-slate-900/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <FileText size={16} className="text-teal-400 shrink-0" />
                        <div>
                          <span className="font-medium text-slate-100">{doc.title}</span>
                          {doc.description && (
                            <p className="text-[11px] text-slate-400 truncate max-w-xs">{doc.description}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-400 uppercase">
                      {doc.file_type}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 px-2 py-0.5 rounded-full">
                        <CheckCircle size={10} /> active
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {dept ? dept.name : 'Cross-Department'}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {(user?.is_admin || doc.owner_id === user?.id) && (
                        <button
                          onClick={() => handleDelete(doc.id, doc.title)}
                          title="Delete Document"
                          className="p-1 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Upload Modal with Live Ingestion Progress */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <button
              onClick={() => !uploading && setIsUploadOpen(false)}
              disabled={uploading}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-200 disabled:opacity-30"
            >
              <X size={18} />
            </button>

            <h3 className="text-base font-bold text-white mb-1 flex items-center gap-2">
              <Upload size={18} className="text-teal-400" />
              <span>Upload Document for Ingestion</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Files are parsed, chunked, embedded via MiniLM, and bound to Zanzibar ReBAC permissions.
            </p>

            {uploading ? (
              <div className="py-6 text-center space-y-4">
                <div className="w-12 h-12 rounded-full border-2 border-teal-500 border-t-transparent animate-spin mx-auto" />
                <div>
                  <p className="text-sm font-semibold text-slate-200 mb-1">{uploadStatusMsg}</p>
                  <p className="text-xs text-slate-400 font-mono">Progress: {uploadProgress}%</p>
                </div>
                <div className="w-full bg-slate-850 rounded-full h-2 overflow-hidden border border-slate-700">
                  <div
                    className="bg-teal-500 h-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            ) : (
              <form onSubmit={handleUploadSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Select File (.txt, .pdf, .docx)</label>
                  <input
                    type="file"
                    accept=".txt,.pdf,.docx"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        setUploadFile(f);
                        if (!uploadTitle) setUploadTitle(f.name.replace(/\.[^/.]+$/, ''));
                      }
                    }}
                    required
                    className="w-full text-xs text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-teal-600 file:text-white hover:file:bg-teal-500 file:cursor-pointer bg-slate-800 border border-slate-700 rounded-lg p-1"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Document Title</label>
                  <input
                    type="text"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    required
                    placeholder="e.g. Q4 Infrastructure Architecture"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Department</label>
                  <select
                    value={uploadDeptId}
                    onChange={(e) => setUploadDeptId(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  >
                    <option value="">Company-Wide / Cross-Department</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Description (Optional)</label>
                  <textarea
                    value={uploadDesc}
                    onChange={(e) => setUploadDesc(e.target.value)}
                    rows={2}
                    placeholder="Brief description of contents..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-teal-500"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setIsUploadOpen(false)}
                    className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs px-4 py-2 rounded-lg transition-colors"
                  >
                    Start Ingestion
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;

