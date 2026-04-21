import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Paperclip, Bookmark } from 'lucide-react';
import { api, type Message } from '../lib/api';

export function SavedMessagesPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [uploading, setUploading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      const m = await api.getSavedMessages();
      setMessages(m);
    } catch {}
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const send = async () => {
    const content = text.trim();
    if (!content) return;
    setText('');
    try {
      const msg = await api.saveText(content);
      setMessages((prev) => [...prev, msg]);
    } catch {}
  };

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const msg = await api.saveMedia(file);
      setMessages((prev) => [...prev, msg]);
    } catch {}
    setUploading(false);
    e.target.value = '';
  };

  return (
    <div className="h-screen flex flex-col bg-[var(--nexly-bg)]">
      {/* Header */}
      <div className="bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-2 shrink-0">
        <button onClick={() => navigate('/chats')} className="p-1">
          <ArrowLeft size={22} />
        </button>
        <div className="w-10 h-10 rounded-full bg-[var(--nexly-sent)]/10 flex items-center justify-center">
          <Bookmark size={20} className="text-[var(--nexly-sent)]" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-[var(--nexly-text)] text-sm truncate">Saved Messages</h2>
          <p className="text-xs text-[var(--nexly-text-secondary)]">Your private notes</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-2">
        {messages.length === 0 && (
          <div className="text-center text-sm text-[var(--nexly-text-secondary)] py-10">
            Save messages, links, files, or notes here. Only you can see them.
          </div>
        )}
        {messages.map((msg) => (
          <SavedBubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {uploading && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-4 py-2 flex items-center gap-2">
          <div className="animate-spin w-4 h-4 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" />
          <span className="text-sm text-[var(--nexly-text-secondary)]">Saving...</span>
        </div>
      )}

      {/* Input */}
      <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-2 shrink-0">
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-[var(--nexly-text-secondary)]"
        >
          <Paperclip size={22} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={upload}
          accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.zip,.rar,.txt"
        />
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Save a note..."
          className="flex-1 py-2.5 px-4 rounded-full bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]"
        />
        <button
          onClick={send}
          disabled={!text.trim()}
          className="p-2.5 rounded-full bg-[var(--nexly-sent)] text-white disabled:opacity-40"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}

function SavedBubble({ msg }: { msg: Message }) {
  const time = new Date(msg.created_at).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] rounded-2xl rounded-br-md px-4 py-2 bg-[var(--nexly-sent)] text-white">
        {msg.message_type === 'image' && msg.media_url && (
          <img src={msg.media_url} alt="" className="rounded-lg max-w-full max-h-64 object-cover mb-1" />
        )}
        {msg.message_type === 'video' && msg.media_url && (
          <video src={msg.media_url} controls className="rounded-lg max-w-full max-h-64 mb-1" />
        )}
        {msg.message_type === 'file' && msg.media_url && (
          <a
            href={msg.media_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 py-1 text-white"
          >
            📎 <span className="text-sm truncate">{msg.media_name || 'File'}</span>
          </a>
        )}
        {msg.message_type === 'text' && msg.content && (
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
        )}
        <div className="text-[11px] text-white/70 text-right mt-1">{time}</div>
      </div>
    </div>
  );
}
