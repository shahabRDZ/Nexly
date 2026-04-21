import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Archive } from 'lucide-react';
import { api, type Conversation } from '../lib/api';
import { Avatar } from '../components/Avatar';

export function ArchivedChatsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Conversation[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await api.getArchivedConversations();
      setItems(data);
    } catch {}
  };

  useEffect(() => {
    load();
  }, []);

  const unarchive = async (userId: string) => {
    setBusy(userId);
    try {
      await api.unarchiveChat(userId);
      setItems((prev) => prev.filter((c) => c.user.id !== userId));
    } catch {}
    setBusy(null);
  };

  return (
    <div className="pb-20">
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-4 py-3 flex items-center gap-3 z-40">
        <button onClick={() => navigate('/chats')} className="p-1">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-xl font-bold text-[var(--nexly-text)]">Archived</h1>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
          <div className="w-20 h-20 rounded-full bg-[var(--nexly-border)] flex items-center justify-center mb-4">
            <Archive size={36} className="text-[var(--nexly-text-secondary)]" />
          </div>
          <h3 className="text-lg font-semibold text-[var(--nexly-text)] mb-1">No archived chats</h3>
          <p className="text-sm text-[var(--nexly-text-secondary)]">
            Archive chats to hide them from the main list
          </p>
        </div>
      ) : (
        <div className="divide-y divide-[var(--nexly-border)]">
          {items.map((convo) => {
            const preview =
              convo.last_message?.message_type === 'voice'
                ? 'Voice message'
                : convo.last_message?.content?.slice(0, 50) || '';
            return (
              <div key={convo.user.id} className="flex items-center gap-3 px-4 py-3">
                <button
                  onClick={() => navigate(`/chat/${convo.user.id}`)}
                  className="flex-1 flex items-center gap-3 text-left"
                >
                  <Avatar src={convo.user.avatar_url} name={convo.user.name} size={48} />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-[var(--nexly-text)] truncate">
                      {convo.user.name}
                    </div>
                    <div className="text-sm text-[var(--nexly-text-secondary)] truncate">
                      {preview}
                    </div>
                  </div>
                </button>
                <button
                  onClick={() => unarchive(convo.user.id)}
                  disabled={busy === convo.user.id}
                  className="text-xs px-3 py-1.5 rounded-lg bg-[var(--nexly-border)] text-[var(--nexly-text)] disabled:opacity-50"
                >
                  Unarchive
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
