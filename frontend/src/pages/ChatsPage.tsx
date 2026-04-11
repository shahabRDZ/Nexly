import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquarePlus } from 'lucide-react';
import { Avatar } from '../components/Avatar';
import { useChat } from '../stores/chat';
import type { Conversation } from '../lib/api';

export function ChatsPage() {
  const { conversations, loadConversations } = useChat();
  const navigate = useNavigate();

  useEffect(() => {
    loadConversations();
  }, []);

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-4 py-3 flex items-center justify-between z-40">
        <h1 className="text-xl font-bold text-[var(--nexly-text)]">Chats</h1>
        <button
          onClick={() => navigate('/contacts')}
          className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-[var(--nexly-border)] transition-colors"
        >
          <MessageSquarePlus size={22} className="text-[var(--nexly-sent)]" />
        </button>
      </div>

      {conversations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
          <div className="w-20 h-20 rounded-full bg-[var(--nexly-border)] flex items-center justify-center mb-4">
            <MessageSquarePlus size={36} className="text-[var(--nexly-text-secondary)]" />
          </div>
          <h3 className="text-lg font-semibold text-[var(--nexly-text)] mb-1">No conversations yet</h3>
          <p className="text-sm text-[var(--nexly-text-secondary)]">
            Start chatting by searching for contacts
          </p>
        </div>
      ) : (
        <div className="divide-y divide-[var(--nexly-border)]">
          {conversations.map((convo) => (
            <ConversationRow key={convo.user.id} convo={convo} />
          ))}
        </div>
      )}
    </div>
  );
}

function ConversationRow({ convo }: { convo: Conversation }) {
  const navigate = useNavigate();
  const { user, last_message, unread_count } = convo;

  const time = last_message
    ? new Date(last_message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  const preview =
    last_message?.message_type === 'voice'
      ? 'Voice message'
      : last_message?.content?.slice(0, 50) || '';

  return (
    <button
      onClick={() => navigate(`/chat/${user.id}`)}
      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--nexly-border)]/30 transition-colors text-left"
    >
      <Avatar src={user.avatar_url} name={user.name} size={52} online={user.is_online} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-[var(--nexly-text)] truncate">{user.name}</span>
          <span className="text-xs text-[var(--nexly-text-secondary)] shrink-0 ml-2">{time}</span>
        </div>
        <div className="flex items-center justify-between mt-0.5">
          <span className="text-sm text-[var(--nexly-text-secondary)] truncate">{preview}</span>
          {unread_count > 0 && (
            <span className="ml-2 shrink-0 min-w-[20px] h-5 rounded-full bg-[var(--nexly-sent)] text-white text-xs flex items-center justify-center px-1.5 font-medium">
              {unread_count}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
