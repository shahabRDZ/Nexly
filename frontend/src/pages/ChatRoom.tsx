import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Smile, Mic, Paperclip, Phone, Video, X, Reply, Forward, Trash2, Pin, Search, Edit3, MapPin, Sparkles, Bot } from 'lucide-react';
import { api, type User, type Message, type SearchResult, type ReactionGroup } from '../lib/api';
import { socket } from '../lib/ws';
import { useChat } from '../stores/chat';
import { Avatar } from '../components/Avatar';
import { MessageBubble } from '../components/MessageBubble';

const REACTION_EMOJIS = ['❤️', '👍', '😂', '😮', '😢', '🔥'];

export function ChatRoom() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { messages, loadMessages, addMessage, updateMessageStatus } = useChat();
  const [other, setOther] = useState<User | null>(null);
  const [text, setText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [editingMsg, setEditingMsg] = useState<Message | null>(null);
  const [contextMsg, setContextMsg] = useState<Message | null>(null);
  const [smartReplies, setSmartReplies] = useState<string[]>([]);
  const [searchMode, setSearchMode] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<ReturnType<typeof setInterval>>();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const myId = localStorage.getItem('userId') ?? '';
  const chatMessages = messages.get(userId!) || [];

  useEffect(() => {
    if (!userId) return;
    api.getUser(userId).then(setOther);
    loadMessages(userId);
    // Load smart replies
    api.getSmartReplies(userId).then((r) => setSmartReplies(r.replies)).catch(() => {});

    const unsubs = [
      socket.on('new_message', (data: Message) => {
        if (data.sender_id === userId) {
          addMessage(data);
          api.markStatus([data.id], 'seen');
          socket.send('seen', { message_ids: [data.id], sender_id: data.sender_id });
          // Refresh smart replies
          api.getSmartReplies(userId).then((r) => setSmartReplies(r.replies)).catch(() => {});
        }
      }),
      socket.on('message_sent', (data: Message) => addMessage(data)),
      socket.on('typing', (data: { user_id: string; is_typing: boolean }) => {
        if (data.user_id === userId) setIsTyping(data.is_typing);
      }),
      socket.on('messages_seen', (data: { message_ids: string[] }) => {
        data.message_ids.forEach((id) => updateMessageStatus(id, 'seen'));
      }),
      socket.on('message_edited', (data: { message_id: string; content: string }) => {
        loadMessages(userId);
      }),
      socket.on('reaction_update', () => loadMessages(userId)),
      socket.on('presence', (data: { user_id: string; is_online: boolean }) => {
        if (data.user_id === userId) setOther((prev) => prev ? { ...prev, is_online: data.is_online } : prev);
      }),
    ];
    return () => unsubs.forEach((fn) => fn());
  }, [userId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages.length]);

  // ── Send / Edit ──
  const sendMessage = () => {
    const content = text.trim();
    if (!content) return;

    if (editingMsg) {
      api.editMessage(editingMsg.id, content).then(() => { loadMessages(userId!); });
      setEditingMsg(null);
    } else {
      socket.send('message', { receiver_id: userId, content, message_type: 'text', reply_to_id: replyTo?.id || null });
      setReplyTo(null);
    }
    setText('');
    socket.send('typing', { receiver_id: userId, is_typing: false });
  };

  const handleTyping = (val: string) => {
    setText(val);
    socket.send('typing', { receiver_id: userId, is_typing: val.length > 0 });
  };

  // ── File Upload ──
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !userId) return;
    setUploading(true);
    setShowAttachMenu(false);
    try { await api.sendMedia(userId, file); await loadMessages(userId); } catch {}
    setUploading(false);
    e.target.value = '';
  };

  // ── Voice Recording ──
  const startRecording = async () => {
    if (recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(recordTimerRef.current);
        setRecordingTime(0);
        if (chunksRef.current.length === 0) return;
        const blob = new Blob(chunksRef.current, { type: mimeType });
        if (blob.size < 1000) return;
        setUploading(true);
        try { await api.sendVoice(userId!, blob, mimeType.includes('webm') ? 'webm' : 'mp4'); await loadMessages(userId!); } catch {}
        setUploading(false);
      };
      recorder.start(100);
      mediaRecorderRef.current = recorder;
      setRecording(true);
      recordTimerRef.current = setInterval(() => setRecordingTime((t) => t + 1), 1000);
    } catch {}
  };

  const stopRecording = () => { if (mediaRecorderRef.current) { mediaRecorderRef.current.stop(); mediaRecorderRef.current = null; } setRecording(false); };
  const cancelRecording = () => { if (mediaRecorderRef.current) { mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop()); mediaRecorderRef.current = null; } chunksRef.current = []; clearInterval(recordTimerRef.current); setRecording(false); setRecordingTime(0); };

  // ── Actions ──
  const handleReaction = async (msg: Message, emoji: string) => {
    try { await api.addReaction(msg.id, emoji); } catch { await api.removeReaction(msg.id, emoji).catch(() => {}); }
    setContextMsg(null);
  };

  const handleEdit = (msg: Message) => { setEditingMsg(msg); setText(msg.content || ''); setContextMsg(null); };
  const handleDelete = async (msg: Message) => { await api.deleteMessage(msg.id, msg.sender_id === myId); loadMessages(userId!); setContextMsg(null); };
  const handlePin = async (msg: Message) => { msg.is_pinned ? await api.unpinMessage(msg.id) : await api.pinMessage(msg.id); loadMessages(userId!); setContextMsg(null); };
  const handleForward = async (msg: Message) => { const t = prompt('User ID to forward:'); if (t) await api.forwardMessage(msg.id, t); setContextMsg(null); };

  // ── Location ──
  const sendLocation = () => {
    setShowAttachMenu(false);
    if (!navigator.geolocation || !userId) return;
    navigator.geolocation.getCurrentPosition(async (pos) => {
      await api.sendLocation(userId, pos.coords.latitude, pos.coords.longitude);
      loadMessages(userId);
    }, () => alert('Location access denied'));
  };

  // ── Search ──
  useEffect(() => {
    if (!searchQuery.trim() || !userId) { setSearchResults([]); return; }
    const timer = setTimeout(async () => {
      try { const r = await api.searchMessages(searchQuery, userId); setSearchResults(r); } catch {}
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const initiateCall = async (type: 'voice' | 'video') => {
    if (!userId || !other) return;
    try { const call = await api.initiateCall(userId, type); window.dispatchEvent(new CustomEvent('nexly:call_outgoing', { detail: { call_id: call.id, callee_id: userId, callee_name: other.name, callee_avatar: other.avatar_url, call_type: type } })); } catch {}
  };

  const emojis = ['😀', '😂', '❤️', '👍', '🔥', '😢', '😮', '🎉', '💯', '🙏', '😎', '🤔', '😊', '👋', '✨', '💪', '😍', '🥺', '😭', '🤣', '💀', '🫡', '🙌', '🤝'];
  const fmtTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  if (!other) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" /></div>;

  return (
    <div className="h-screen flex flex-col bg-[var(--nexly-bg)]">
      {/* Header */}
      <div className="bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-2 shrink-0">
        <button onClick={() => navigate('/chats')} className="p-1"><ArrowLeft size={22} /></button>
        <Avatar src={other.avatar_url} name={other.name} size={40} online={other.is_online} />
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-[var(--nexly-text)] text-sm truncate">{other.name}</h2>
          <p className="text-xs text-[var(--nexly-text-secondary)]">{isTyping ? 'typing...' : other.is_online ? 'online' : 'offline'}</p>
        </div>
        <button onClick={() => setSearchMode(!searchMode)} className="p-2"><Search size={18} className="text-[var(--nexly-text-secondary)]" /></button>
        <button onClick={() => initiateCall('voice')} className="p-2"><Phone size={18} className="text-[var(--nexly-sent)]" /></button>
        <button onClick={() => initiateCall('video')} className="p-2"><Video size={18} className="text-[var(--nexly-sent)]" /></button>
      </div>

      {/* Search bar */}
      {searchMode && (
        <div className="bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-3 py-2">
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search in conversation..." autoFocus
            className="w-full py-2 px-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-sm text-[var(--nexly-text)] focus:outline-none" />
          {searchResults.length > 0 && (
            <div className="mt-2 max-h-40 overflow-y-auto space-y-1">
              {searchResults.map((r) => (
                <div key={r.id} className="text-xs text-[var(--nexly-text-secondary)] p-2 rounded bg-[var(--nexly-bg)] truncate">
                  <span className="text-[10px]">{new Date(r.created_at).toLocaleDateString()}</span> — {r.content}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {chatMessages.length === 0 && <div className="text-center text-sm text-[var(--nexly-text-secondary)] py-10">Start your conversation with {other.name}</div>}
        {chatMessages.map((msg) => (
          <div key={msg.id} onContextMenu={(e) => { e.preventDefault(); setContextMsg(msg); }} onClick={() => contextMsg && setContextMsg(null)}>
            {msg.reply_to_id && <ReplyPreview messages={chatMessages} replyToId={msg.reply_to_id} />}
            <MessageBubble message={msg} isMine={msg.sender_id === myId} />
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {uploading && <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-4 py-2 flex items-center gap-2"><div className="animate-spin w-4 h-4 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" /><span className="text-sm text-[var(--nexly-text-secondary)]">Sending...</span></div>}

      {/* Context menu with reactions */}
      {contextMsg && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] p-2 space-y-2">
          {/* Reaction bar */}
          <div className="flex justify-center gap-2">
            {REACTION_EMOJIS.map((e) => (
              <button key={e} onClick={() => handleReaction(contextMsg, e)} className="text-xl hover:scale-125 transition-transform p-1">{e}</button>
            ))}
          </div>
          <div className="flex gap-1 justify-center flex-wrap">
            <button onClick={() => { setReplyTo(contextMsg); setContextMsg(null); }} className="flex items-center gap-1 px-3 py-1.5 rounded-lg hover:bg-[var(--nexly-border)]/50 text-xs text-[var(--nexly-text)]"><Reply size={14} /> Reply</button>
            {contextMsg.sender_id === myId && contextMsg.message_type === 'text' && (
              <button onClick={() => handleEdit(contextMsg)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg hover:bg-[var(--nexly-border)]/50 text-xs text-[var(--nexly-text)]"><Edit3 size={14} /> Edit</button>
            )}
            <button onClick={() => handleForward(contextMsg)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg hover:bg-[var(--nexly-border)]/50 text-xs text-[var(--nexly-text)]"><Forward size={14} /> Forward</button>
            <button onClick={() => handlePin(contextMsg)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg hover:bg-[var(--nexly-border)]/50 text-xs text-[var(--nexly-text)]"><Pin size={14} /> {contextMsg.is_pinned ? 'Unpin' : 'Pin'}</button>
            <button onClick={() => handleDelete(contextMsg)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-xs text-red-500"><Trash2 size={14} /> Delete</button>
          </div>
        </div>
      )}

      {/* Reply / Edit bar */}
      {(replyTo || editingMsg) && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-4 py-2 flex items-center gap-2">
          <div className="flex-1 border-l-2 border-[var(--nexly-sent)] pl-2">
            <p className="text-xs text-[var(--nexly-sent)] font-medium">{editingMsg ? 'Editing' : 'Reply to'}</p>
            <p className="text-xs text-[var(--nexly-text-secondary)] truncate">{(editingMsg || replyTo)?.content || 'Media'}</p>
          </div>
          <button onClick={() => { setReplyTo(null); setEditingMsg(null); setText(''); }}><X size={18} className="text-[var(--nexly-text-secondary)]" /></button>
        </div>
      )}

      {/* Smart Replies */}
      {smartReplies.length > 0 && !text && !recording && !editingMsg && chatMessages.length > 0 && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-3 py-2 flex gap-2 overflow-x-auto">
          <Sparkles size={14} className="text-[var(--nexly-sent)] shrink-0 mt-1.5" />
          {smartReplies.map((r, i) => (
            <button key={i} onClick={() => { setText(r); }} className="shrink-0 px-3 py-1.5 rounded-full border border-[var(--nexly-sent)]/30 text-xs text-[var(--nexly-sent)] hover:bg-[var(--nexly-sent)]/10 transition-colors">{r}</button>
          ))}
        </div>
      )}

      {/* Emoji picker */}
      {showEmoji && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] p-3 grid grid-cols-8 gap-2">
          {emojis.map((e) => (<button key={e} onClick={() => { setText((t) => t + e); setShowEmoji(false); }} className="text-2xl hover:scale-125 transition-transform">{e}</button>))}
        </div>
      )}

      {/* Attach menu */}
      {showAttachMenu && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] p-3 grid grid-cols-3 gap-3">
          <button onClick={() => { fileInputRef.current?.click(); }} className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-[var(--nexly-border)]/50">
            <Paperclip size={22} className="text-blue-500" /><span className="text-[11px] text-[var(--nexly-text-secondary)]">File</span>
          </button>
          <button onClick={sendLocation} className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-[var(--nexly-border)]/50">
            <MapPin size={22} className="text-green-500" /><span className="text-[11px] text-[var(--nexly-text-secondary)]">Location</span>
          </button>
          <button onClick={() => { navigate(`/ai-chat`); setShowAttachMenu(false); }} className="flex flex-col items-center gap-1 p-3 rounded-xl hover:bg-[var(--nexly-border)]/50">
            <Bot size={22} className="text-purple-500" /><span className="text-[11px] text-[var(--nexly-text-secondary)]">AI Bot</span>
          </button>
        </div>
      )}

      {/* Input */}
      <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-2 shrink-0">
        {recording ? (
          <div className="flex-1 flex items-center gap-3">
            <button onClick={cancelRecording} className="p-2 text-red-500"><X size={22} /></button>
            <div className="flex-1 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm text-red-500 font-mono">{fmtTime(recordingTime)}</span>
              <span className="text-sm text-[var(--nexly-text-secondary)]">Recording...</span>
            </div>
            <button onClick={stopRecording} className="p-2.5 rounded-full bg-[var(--nexly-sent)] text-white"><Send size={18} /></button>
          </div>
        ) : (
          <>
            <button onClick={() => setShowEmoji(!showEmoji)} className="p-2 text-[var(--nexly-text-secondary)]"><Smile size={22} /></button>
            <button onClick={() => setShowAttachMenu(!showAttachMenu)} className="p-2 text-[var(--nexly-text-secondary)]"><Paperclip size={22} /></button>
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileUpload} accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.zip,.rar,.txt" />
            <input type="text" value={text} onChange={(e) => handleTyping(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendMessage()} placeholder={editingMsg ? 'Edit message...' : 'Message...'}
              className="flex-1 py-2.5 px-4 rounded-full bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]" />
            {text.trim() ? (
              <button onClick={sendMessage} className="p-2.5 rounded-full bg-[var(--nexly-sent)] text-white"><Send size={18} /></button>
            ) : (
              <button onClick={startRecording} className="p-2.5 rounded-full bg-[var(--nexly-sent)] text-white"><Mic size={18} /></button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ReplyPreview({ messages, replyToId }: { messages: Message[]; replyToId: string }) {
  const original = messages.find((m) => m.id === replyToId);
  if (!original) return null;
  return <div className="ml-10 mb-0.5 border-l-2 border-[var(--nexly-sent)]/40 pl-2"><p className="text-xs text-[var(--nexly-text-secondary)] truncate">{original.content || 'Media'}</p></div>;
}
