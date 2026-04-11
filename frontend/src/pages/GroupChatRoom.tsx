import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Users, Smile } from 'lucide-react';
import { api, type Group, type GroupMember, type Message } from '../lib/api';
import { socket } from '../lib/ws';
import { Avatar } from '../components/Avatar';
import { MessageBubble } from '../components/MessageBubble';

export function GroupChatRoom() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const [group, setGroup] = useState<Group | null>(null);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [typingUsers, setTypingUsers] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const myId = localStorage.getItem('userId')!;

  useEffect(() => {
    if (!groupId) return;
    api.getGroup(groupId).then(setGroup);
    api.getGroupMembers(groupId).then(setMembers);
    api.getGroupMessages(groupId).then(setMessages);

    const unsubs = [
      socket.on('group_message', (data: Message) => {
        if (data.group_id === groupId) {
          setMessages((prev) => [...prev, data]);
        }
      }),
      socket.on('message_sent', (data: Message) => {
        if (data.group_id === groupId) {
          setMessages((prev) => {
            if (prev.find((m) => m.id === data.id)) return prev;
            return [...prev, data];
          });
        }
      }),
      socket.on('group_typing', (data: { group_id: string; user_id: string; is_typing: boolean }) => {
        if (data.group_id === groupId) {
          setTypingUsers((prev) => {
            const next = new Set(prev);
            data.is_typing ? next.add(data.user_id) : next.delete(data.user_id);
            return next;
          });
        }
      }),
    ];
    return () => unsubs.forEach((fn) => fn());
  }, [groupId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const sendMessage = () => {
    const content = text.trim();
    if (!content || !groupId) return;
    socket.send('group_message', { group_id: groupId, content, message_type: 'text' });
    setText('');
  };

  const handleTyping = (val: string) => {
    setText(val);
    if (groupId) socket.send('group_typing', { group_id: groupId, is_typing: val.length > 0 });
  };

  const getMemberName = (userId: string) => members.find((m) => m.user_id === userId)?.name || 'Unknown';

  const typingText = typingUsers.size > 0
    ? [...typingUsers].map((uid) => getMemberName(uid)).join(', ') + ' typing...'
    : `${members.length} members`;

  if (!group) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" /></div>;

  return (
    <div className="h-screen flex flex-col bg-[var(--nexly-bg)]">
      <div className="bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={() => navigate('/groups')} className="p-1"><ArrowLeft size={22} className="text-[var(--nexly-text)]" /></button>
        <Avatar src={group.avatar_url} name={group.name} size={40} />
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-[var(--nexly-text)] text-sm truncate">{group.name}</h2>
          <p className="text-xs text-[var(--nexly-text-secondary)]">{typingText}</p>
        </div>
        <button onClick={() => {}} className="p-2"><Users size={20} className="text-[var(--nexly-text-secondary)]" /></button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {messages.map((msg) => (
          <div key={msg.id}>
            {msg.sender_id !== myId && (
              <p className="text-xs text-[var(--nexly-sent)] font-medium ml-1 mb-0.5">{getMemberName(msg.sender_id)}</p>
            )}
            <MessageBubble message={msg} isMine={msg.sender_id === myId} />
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] px-3 py-2.5 flex items-center gap-2 shrink-0">
        <input type="text" value={text} onChange={(e) => handleTyping(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Message..."
          className="flex-1 py-2.5 px-4 rounded-full bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]" />
        <button onClick={sendMessage} className="p-2.5 rounded-full bg-[var(--nexly-sent)] text-white"><Send size={18} /></button>
      </div>
    </div>
  );
}
