import React from 'react';
import { Bot, User as UserIcon, FileText, CheckCircle2 } from 'lucide-react';
import type { ChatMessage } from '../../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center text-white shrink-0 mt-1 shadow-md">
          <Bot size={18} />
        </div>
      )}

      <div className={`max-w-[80%] rounded-xl p-4 shadow-sm ${
        isUser
          ? 'bg-teal-600 text-white rounded-tr-none'
          : 'bg-slate-800 border border-slate-700 text-slate-100 rounded-tl-none'
      }`}>
        <div className="text-xs text-slate-400 mb-1 flex items-center gap-1">
          <span>{isUser ? 'You' : 'Governance Assistant'}</span>
          <span>•</span>
          <span>{message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>

        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
          {message.isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-teal-400 animate-pulse" />
          )}
        </div>

        {/* Citations section */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700/60">
            <div className="text-xs font-semibold text-teal-400 mb-2 flex items-center gap-1.5">
              <CheckCircle2 size={13} />
              <span>Verified Authorized Sources ({message.citations.length}):</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {message.citations.map((c, i) => (
                <div
                  key={i}
                  className="bg-slate-900/60 border border-slate-700/80 rounded p-2 text-xs flex items-start gap-2"
                >
                  <FileText size={14} className="text-teal-400 mt-0.5 shrink-0" />
                  <div className="overflow-hidden">
                    <p className="font-medium text-slate-200 truncate">{c.title}</p>
                    <p className="text-[10px] text-slate-400">
                      Match: {(c.similarity * 100).toFixed(0)}% • Chunk #{c.chunk_index}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1 shadow-md">
          <UserIcon size={18} />
        </div>
      )}
    </div>
  );
};

