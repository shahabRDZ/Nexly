import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Smile, Mic, MicOff, Paperclip, Phone, Video, X, Reply, Forward, Trash2, Pin } from 'lucide-react';
import { api, type User, type Message } from '../lib/api';
import { socket } from '../lib/ws';
import { useChat } from '../stores/chat';
import { Avatar } from '../components/Avatar';
import { MessageBubble } from '../components/MessageBubble';

export function ChatRoom() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { messages, loadMessages, addMessage, updateMessageStatus } = useChat();
  const [other, setOther] = useState<User | null>(null);
  const [text, setText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [recording, setRecording] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [contextMsg, setContextMsg] = useState<Message | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const myId = localStorage.getItem('userId')!;
  const chatMessages = messages.get(userId!) || [];

  useEffect(() => {
    if (!userId) return;
    api.getUser(userId).then(setOther);
    loadMessages(userId);

    const unsubs = [
      socket.on('new_message', (data: Message) => {
        if (data.sender_id === userId) {
          addMessage(data);
          api.markStatus([data.id], 'seen');
          socket.send('seen', { message_ids: [data.id], sender_id: data.sender_id });
        }
      }),
      socket.on('message_sent', (data: Message) => addMessage(data)),
      socket.on('typing', (data: { user_id: string; is_typing: boolean }) => {
        if (data.user_id === userId) setIsTyping(data.is_typing);
      }),
      socket.on('messages_seen', (data: { message_ids: string[] }) => {
        data.message_ids.forEach((id) => updateMessageStatus(id, 'seen'));
      }),
      socket.on('presence', (data: { user_id: string; is_online: boolean }) => {
        if (data.user_id === userId) setOther((prev) => prev ? { ...prev, is_online: data.is_online } : prev);
      }),
    ];

    return () => unsubs.forEach((fn) => fn());
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages.length]);

  const sendMessage = () => {
    const content = text.trim();
    if (!content) return;
    socket.send('message', {
      receiver_id: userId, content, message_type: 'text',
      reply_to_id: replyTo?.id || null,
    });
    setText('');
    setReplyTo(null);
    socket.send('typing', { receiver_id: userId, is_typing: false });
  };

  const handleTyping = (val: string) => {
    setText(val);
    socket.send('typing', { receiver_id: userId, is_typing: val.length > 0 });
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !userId) return;
    try { await api.sendMedia(userId, file); loadMessages(userId); } catch {}
    e.target.value = '';
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/ogg' });
        if (userId) { await api.sendVoice(userId, blob); loadMessages(userId); }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {}
  };

  const stopRecording = () => { mediaRecorderRef.current?.stop(); setRecording(false); };

  const handleDelete = async (msg: Message, forAll: boolean) => {
    await api.deleteMessage(msg.id, forAll);
    loadMessages(userId!);
    setContextMsg(null);
  };

  const handleForward = async (msg: Message) => {
    const target = prompt('Enter user ID to forward to:');
    if (target) { await api.forwardMessage(msg.id, target); }
    setContextMsg(null);
  };

  const handlePin = async (msg: Message) => {
    msg.is_pinned ? await api.unpinMessage(msg.id) : await api.pinMessage(msg.id);
    loadMessages(userId!);
    setContextMsg(null);
  };

  const initiateCall = async (type: 'voice' | 'video') => {
    if (!userId) return;
    await api.initiateCall(userId, type);
  };

  const emojis = ['😀', '😂', '❤️', '👍', '🔥', '😢', '😮', '🎉', '💯', '🙏', '😎', '🤔', '😊', '👋', '✨', '💪'];

  if (!other) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" /></div>;

  return (
    <div className="h-screen flex flex-col bg-[var(--nexly-bg)]">
      {/* Header */}
      <div className="bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => navigate('/chats')} className="p-1"><ArrowLeft size={22} className="text-[var(--nexly-text)]" /></button>
        <Avatar src={other.avatar_url} name={other.name} size={40} online={other.is_online} />
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-[var(--nexly-text)] text-sm truncate">{other.name}</h2>
          <p className="text-xs text-[var(--nexly-text-secondary)]">
            {isTyping ? 'typing...' : other.is_online ? 'online' : other.last_seen ? `last seen ${new Date(other.last_seen).toLocaleString()}` : 'offline'}
          </p>
        </div>
        <button onClick={() => initiateCall('voice')} className="p-2"><Phone size={20} className="text-[var(--nexly-sent)]" /></button>
        <button onClick={() => initiateCall('video')} className="p-2"><Video size={20} className="text-[var(--nexly-sent)]" /></button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {chatMessages.length === 0 && <div className="text-center text-sm text-[var(--nexly-text-secondary)] py-10">Start your conversation with {other.name}</div>}
        {chatMessages.map((msg) => (
          <div key={msg.id} onContextMenu={(e) => { e.preventDefault(); setContextMsg(msg); }}
            onClick={() => { if (contextMsg) setContextMsg(null); }}>
            {msg.reply_to_id && <ReplyPreview messages={chatMessages} replyToId={msg.reply_to_id} />}
            <MessageBubble message={msg} isMine={msg.sender_id === myId} />
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Context menu */}
      {contextMsg && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] p-2 flex gap-1 justify-center">
          <button onClick={() => { setReplyTo(contextMsg); setContextMsg(null); }} className="flex items-center gap-1 px-3 py-2 rounded-lg hover:bg-[var(--nexly-border)]/50 text-sm text-[var(--nexly-text)]"><Reply size={16} /> Reply</button>
          <button onClick={() => handleForward(contextMsg)} className="flex items-center gap-1 px-3 py-2 rounded-lg hover:bg-[var(--nexly-border)]/50 text-sm text-[var(--nexly-text)]"><Forward size={16} /> Forward</button>
          <button onClick={() => handlePin(contextMsg)} className="flex items-center gap-1 px-3 py-2 rounded-lg hover:bg-[var(--nexly-border)]/50 text-sm text-[var(--nexly-text)]"><Pin size={16} /> {contextMsg.is_pinned ? 'Unpin' : 'Pin'}</button>
          <button onClick={() => handleDelete(contextMsg, contextMsg.sender_id === myId)} className="flex items-center gap-1 px-3 py-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-sm text-red-500"><Trash2 size={16} /> Delete</button>
        </div>
      )}

      {/* Reply bar */}
      {replyTo && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-4 py-2 flex items-center gap-2">
          <div className="flex-1 border-l-2 border-[var(--nexly-sent)] pl-2">
            <p className="text-xs text-[var(--nexly-sent)] font-medium">Reply to</p>
            <p className="text-xs text-[var(--nexly-text-secondary)] truncate">{replyTo.content || 'Media'}</p>
          </div>
          <button onClick={() => setReplyTo(null)}><X size={18} className="text-[var(--nexly-text-secondary)]" /></button>
        </div>
      )}

      {/* Emoji picker */}
      {showEmoji && (
        <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] p-3 grid grid-cols-8 gap-2">
          {emojis.map((e) => (
            <button key={e} onClick={() => { setText((t) => t + e); setShowEmoji(false); }} className="text-2xl hover:scale-125 transition-transform">{e}</button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-2 shrink-0">
        <button onClick={() => setShowEmoji(!showEmoji)} className="p-2 text-[var(--nexly-text-secondary)]"><Smile size={22} /></button>
        <button onClick={() => fileInputRef.current?.click()} className="p-2 text-[var(--nexly-text-secondary)]"><Paperclip size={22} /></button>
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileUpload} accept="image/*,video/*,.pdf,.doc,.docx,.zip" />
        <input type="text" value={text} onChange={(e) => handleTyping(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Message..."
          className="flex-1 py-2.5 px-4 rounded-full bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]" />
        {text.trim() ? (
          <button onClick={sendMessage} className="p-2.5 rounded-full bg-[var(--nexly-sent)] text-white"><Send size={18} /></button>
        ) : (
          <button onMouseDown={startRecording} onMouseUp={stopRecording} onTouchStart={startRecording} onTouchEnd={stopRecording}
            className={`p-2.5 rounded-full ${recording ? 'bg-red-500 animate-pulse' : 'bg-[var(--nexly-sent)]'} text-white`}>
            {recording ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
        )}
      </div>
    </div>
  );
}

function ReplyPreview({ messages, replyToId }: { messages: Message[]; replyToId: string }) {
  const original = messages.find((m) => m.id === replyToId);
  if (!original) return null;
  return (
    <div className="ml-10 mb-0.5 border-l-2 border-[var(--nexly-sent)]/40 pl-2">
      <p className="text-xs text-[var(--nexly-text-secondary)] truncate">{original.content || 'Media'}</p>
    </div>
  );
}
