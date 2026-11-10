import React, { useState, useRef, useEffect } from 'react';
import { Send, ShieldCheck, Zap, AlertCircle, RefreshCw, Sparkles, Database } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { MessageBubble } from '../components/chat/MessageBubble';
import { streamChatResponse } from '../services/api';
import type { ChatMessage, Citation } from '../types';

const SAMPLE_QUESTIONS = [
  { label: 'HR Leave Policy', q: 'What are the employee leave and attendance policies?' },
  { label: 'Finance Revenue (Restricted to Finance)', q: 'What is the quarterly revenue and gross margin?' },
  { label: 'HR Salaries (Managers Only)', q: 'What is my department salary information and pay bands?' },
  { label: 'Sales Pipeline', q: 'What is the active sales pipeline and enterprise win rate?' },
  { label: 'IT Server Runbook', q: 'Show me the server maintenance procedures and runbook.' },
  { label: 'IT Incidents (IT Admin Only)', q: 'What are the recent security incident reports and post-mortems?' },
];

export const ChatPage: React.FC = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [authDocCount, setAuthDocCount] = useState<number | null>(null);
  const [retrievedChunkCount, setRetrievedChunkCount] = useState<number | null>(null);
  const [authLatency, setAuthLatency] = useState<number | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSend = async (questionText?: string) => {
    const question = (questionText || input).trim();
    if (!question || isStreaming) return;

    setInput('');
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      citations: [],
    };
    setMessages((prev) => [...prev, assistantMsg]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulatedContent = '';
    const citations: Citation[] = [];

    try {
      const stream = streamChatResponse(question, conversationId || undefined, controller.signal);

      for await (const { event, data } of stream) {
        if (event === 'conversation.started') {
          if (data.conversation_id) setConversationId(data.conversation_id);
        } else if (event === 'authorization.completed') {
          setAuthDocCount(data.authorized_doc_count);
          if (data.authorization_latency_ms) setAuthLatency(data.authorization_latency_ms);
        } else if (event === 'retrieval.completed') {
          setRetrievedChunkCount(data.chunk_count);
        } else if (event === 'token') {
          accumulatedContent += data.content;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId ? { ...msg, content: accumulatedContent } : msg
            )
          );
        } else if (event === 'citation') {
          citations.push({
            document_id: data.document_id,
            title: data.title,
            chunk_index: data.chunk_index,
            similarity: data.similarity,
          });
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId ? { ...msg, citations: [...citations] } : msg
            )
          );
        } else if (event === 'error') {
          accumulatedContent += `\n[Security Notice: ${data.message}]`;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? { ...msg, content: accumulatedContent, isStreaming: false }
                : msg
            )
          );
        } else if (event === 'generation.completed') {
          // Done
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        accumulatedContent += `\n[Error: ${err.message || 'Streaming failed'}]`;
      }
    } finally {
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId ? { ...msg, isStreaming: false, citations } : msg
        )
      );
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setAuthDocCount(null);
    setRetrievedChunkCount(null);
    setConversationId(null);
  };

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Top Banner: Real-time Pre-Retrieval ACL Metrics */}
      <div className="bg-slate-950 border-b border-slate-800 px-6 py-2.5 flex items-center justify-between text-xs shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-teal-400 font-medium">
            <ShieldCheck size={16} />
            <span>Pre-Retrieval ACL Active</span>
          </div>

          <div className="h-4 w-px bg-slate-800" />

          <div className="flex items-center gap-3 text-slate-400">
            <span>
              Authorized Documents:{' '}
              <strong className="text-slate-200">{authDocCount !== null ? authDocCount : '—'}</strong>
            </span>
            <span>•</span>
            <span>
              Retrieved Chunks:{' '}
              <strong className="text-slate-200">{retrievedChunkCount !== null ? retrievedChunkCount : '—'}</strong>
            </span>
            {authLatency && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-teal-300 font-mono">
                  <Zap size={12} /> {authLatency.toFixed(1)}ms ACL
                </span>
              </>
            )}
          </div>
        </div>

        <button
          onClick={handleClear}
          className="text-slate-400 hover:text-slate-200 flex items-center gap-1 text-[11px] py-1 px-2 rounded hover:bg-slate-800 transition-colors"
        >
          <RefreshCw size={12} />
          <span>Clear Chat</span>
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <div className="max-w-2xl mx-auto text-center py-12">
            <div className="w-14 h-14 rounded-2xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400 mx-auto mb-4">
              <Sparkles size={28} />
            </div>
            <h2 className="text-lg font-bold text-slate-100 mb-1">Permission-Aware Enterprise RAG</h2>
            <p className="text-xs text-slate-400 mb-6 max-w-md mx-auto">
              Every query evaluates OpenFGA Zanzibar relationships to filter unauthorized documents in PostgreSQL <strong>before</strong> similarity retrieval.
            </p>

            <div className="text-left bg-slate-950/70 border border-slate-800 rounded-xl p-4">
              <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Database size={14} className="text-teal-400" />
                <span>Test Pre-Retrieval Scenarios for {user?.full_name}:</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {SAMPLE_QUESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(s.q)}
                    className="p-2.5 rounded-lg bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-teal-500/40 text-left transition-all group"
                  >
                    <p className="text-xs font-medium text-slate-200 group-hover:text-teal-300 mb-0.5 truncate">
                      {s.label}
                    </p>
                    <p className="text-[11px] text-slate-400 line-clamp-1">{s.q}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Box */}
      <div className="p-4 bg-slate-950 border-t border-slate-800 shrink-0">
        <div className="max-w-3xl mx-auto">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-xl p-2 focus-within:border-teal-500 transition-colors shadow-lg"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask as ${user?.full_name} (${user?.department_name || 'Admin'})...`}
              disabled={isStreaming}
              className="flex-1 bg-transparent border-none text-sm text-slate-100 placeholder-slate-500 focus:outline-none px-3"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={handleStop}
                className="bg-red-600/80 hover:bg-red-600 text-white text-xs px-3 py-2 rounded-lg font-medium transition-colors"
              >
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="bg-teal-600 hover:bg-teal-500 text-white p-2 rounded-lg disabled:opacity-40 disabled:hover:bg-teal-600 transition-colors shadow-sm"
              >
                <Send size={16} />
              </button>
            )}
          </form>

          <p className="text-[10px] text-slate-500 text-center mt-2">
            Context strictly bounded by Zanzibar ReBAC tuples • pgvector Cosine Distance Search
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;

