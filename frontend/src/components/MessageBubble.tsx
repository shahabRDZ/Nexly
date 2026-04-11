import { useState } from 'react';
import { Check, CheckCheck, FileText, Globe, Eye } from 'lucide-react';
import type { Message } from '../lib/api';

interface Props {
  message: Message;
  isMine: boolean;
}

export function MessageBubble({ message, isMine }: Props) {
  const [showOriginal, setShowOriginal] = useState(false);

  if (message.deleted_for_all) {
    return (
      <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} mb-1`}>
        <div className="px-4 py-2 rounded-2xl bg-[var(--nexly-border)]/50 italic text-sm text-[var(--nexly-text-secondary)]">
          This message was deleted
        </div>
      </div>
    );
  }

  const time = new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const isTranslated = message.translated && message.original_content;
  const displayContent = showOriginal ? message.original_content : message.content;

  return (
    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} mb-1`}>
      <div className={`max-w-[75%] rounded-2xl px-4 py-2 ${
        isMine
          ? 'bg-[var(--nexly-sent)] text-white rounded-br-md'
          : 'bg-[var(--nexly-received)] border border-[var(--nexly-border)] rounded-bl-md'
      }`}>
        {message.is_forwarded && (
          <p className={`text-xs mb-1 ${isMine ? 'text-white/60' : 'text-[var(--nexly-text-secondary)]'}`}>Forwarded</p>
        )}

        <MessageContent message={{ ...message, content: displayContent ?? message.content }} isMine={isMine} />

        {/* Translation indicator + Show Original toggle */}
        {isTranslated && (
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className={`flex items-center gap-1 mt-1 text-[10px] transition-colors ${
              isMine ? 'text-white/50 hover:text-white/80' : 'text-[var(--nexly-text-secondary)] hover:text-[var(--nexly-text)]'
            }`}
          >
            <Globe size={10} />
            <span>{showOriginal ? 'Show translation' : `Translated from ${message.source_language?.toUpperCase()}`}</span>
            <Eye size={10} />
          </button>
        )}

        <div className={`flex items-center gap-1 justify-end mt-1 ${isMine ? 'text-white/70' : 'text-[var(--nexly-text-secondary)]'}`}>
          {message.is_pinned && <span className="text-[10px]">pinned</span>}
          <span className="text-[11px]">{time}</span>
          {message.edited_at && <span className="text-[10px]">edited</span>}
          {isMine && <StatusIcon status={message.status} />}
        </div>
      </div>
    </div>
  );
}

function MessageContent({ message, isMine }: { message: Message; isMine: boolean }) {
  switch (message.message_type) {
    case 'voice':
      return (
        <audio controls className="h-8 max-w-full" style={{ filter: isMine ? 'invert(1) brightness(2) hue-rotate(180deg)' : 'none' }}>
          <source src={message.media_url!} />
        </audio>
      );
    case 'image':
      return (
        <div className="mb-1">
          <img src={message.media_url!} alt="" className="rounded-lg max-w-full max-h-64 object-cover cursor-pointer"
            onClick={() => window.open(message.media_url!, '_blank')} />
          {message.content && message.content !== message.media_name && (
            <p className="text-[15px] leading-relaxed mt-1">{message.content}</p>
          )}
        </div>
      );
    case 'video':
      return <video src={message.media_url!} controls className="rounded-lg max-w-full max-h-64 mb-1" />;
    case 'file':
      return (
        <a href={message.media_url!} target="_blank" rel="noopener noreferrer"
          className={`flex items-center gap-2 py-1 ${isMine ? 'text-white' : 'text-[var(--nexly-sent)]'}`}>
          <FileText size={20} />
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{message.media_name || 'File'}</p>
            {message.media_size && <p className="text-xs opacity-70">{formatSize(message.media_size)}</p>}
          </div>
        </a>
      );
    default:
      return <p className="text-[15px] leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>;
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'seen': return <CheckCheck size={14} className="text-blue-400" />;
    case 'delivered': return <CheckCheck size={14} className="text-white/70" />;
    default: return <Check size={14} className="text-white/70" />;
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
