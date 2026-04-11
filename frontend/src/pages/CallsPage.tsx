import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Phone, Video, PhoneIncoming, PhoneOutgoing, PhoneMissed, ArrowLeft, Clock } from 'lucide-react';
import { api, type CallRecord, type User } from '../lib/api';
import { Avatar } from '../components/Avatar';

type Tab = 'all' | 'missed' | 'incoming' | 'outgoing';

export function CallsPage() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [users, setUsers] = useState<Map<string, User>>(new Map());
  const [tab, setTab] = useState<Tab>('all');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const myId = localStorage.getItem('userId')!;

  useEffect(() => {
    loadCalls();
  }, []);

  const loadCalls = async () => {
    setLoading(true);
    try {
      const records = await api.getCallHistory();
      setCalls(records);

      // Batch fetch users
      const ids = new Set(records.flatMap((c) => [c.caller_id, c.callee_id]).filter((id) => id !== myId));
      const userMap = new Map<string, User>();
      await Promise.all(
        [...ids].map(async (id) => {
          try { const u = await api.getUser(id); userMap.set(id, u); } catch {}
        })
      );
      setUsers(userMap);
    } catch {}
    setLoading(false);
  };

  const filtered = calls.filter((c) => {
    const isOutgoing = c.caller_id === myId;
    const isMissed = c.status === 'missed' || c.status === 'declined';
    switch (tab) {
      case 'missed': return isMissed;
      case 'incoming': return !isOutgoing;
      case 'outgoing': return isOutgoing;
      default: return true;
    }
  });

  const initiateCall = (userId: string, type: 'voice' | 'video') => {
    const other = users.get(userId);
    if (!other) return;
    api.initiateCall(userId, type).then((call) => {
      window.dispatchEvent(new CustomEvent('nexly:call_outgoing', {
        detail: { call_id: call.id, callee_id: userId, callee_name: other.name, callee_avatar: other.avatar_url, call_type: type },
      }));
    }).catch(() => {});
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'missed', label: 'Missed' },
    { key: 'incoming', label: 'Incoming' },
    { key: 'outgoing', label: 'Outgoing' },
  ];

  const missedCount = calls.filter((c) => c.status === 'missed' || c.status === 'declined').length;

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] z-40">
        <div className="px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate('/chats')} className="p-1">
            <ArrowLeft size={22} className="text-[var(--nexly-text)]" />
          </button>
          <h1 className="text-xl font-bold text-[var(--nexly-text)] flex-1">Calls</h1>
          {missedCount > 0 && (
            <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full font-medium">
              {missedCount} missed
            </span>
          )}
        </div>

        {/* Tabs */}
        <div className="flex px-2 gap-1">
          {tabs.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex-1 py-2 text-xs font-medium rounded-t-lg transition-colors ${
                tab === t.key
                  ? 'text-[var(--nexly-sent)] border-b-2 border-[var(--nexly-sent)] bg-[var(--nexly-sent)]/5'
                  : 'text-[var(--nexly-text-secondary)]'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" />
        </div>
      )}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="flex flex-col items-center py-20 text-center px-6">
          <div className="w-20 h-20 rounded-full bg-[var(--nexly-border)] flex items-center justify-center mb-4">
            {tab === 'missed' ? <PhoneMissed size={36} className="text-red-400" /> : <Phone size={36} className="text-[var(--nexly-text-secondary)]" />}
          </div>
          <h3 className="text-lg font-semibold text-[var(--nexly-text)]">
            {tab === 'all' ? 'No calls yet' : `No ${tab} calls`}
          </h3>
          <p className="text-sm text-[var(--nexly-text-secondary)] mt-1">
            {tab === 'all' ? 'Start a call from any chat' : `Your ${tab} calls will appear here`}
          </p>
        </div>
      )}

      {/* Call list */}
      {!loading && filtered.length > 0 && (
        <div>
          {groupByDate(filtered).map(({ label, items }) => (
            <div key={label}>
              {/* Date header */}
              <div className="sticky top-[105px] bg-[var(--nexly-bg)] px-4 py-1.5 z-10">
                <span className="text-xs font-medium text-[var(--nexly-text-secondary)] uppercase tracking-wide">{label}</span>
              </div>

              <div className="divide-y divide-[var(--nexly-border)]">
                {items.map((call) => {
                  const isOutgoing = call.caller_id === myId;
                  const otherId = isOutgoing ? call.callee_id : call.caller_id;
                  const other = users.get(otherId);
                  const isMissed = call.status === 'missed' || call.status === 'declined';
                  const isVideo = call.call_type === 'video';

                  return (
                    <div key={call.id} className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--nexly-border)]/20 transition-colors">
                      {/* Avatar */}
                      <div className="relative">
                        <Avatar src={other?.avatar_url || null} name={other?.name || 'Unknown'} size={48} />
                        <div className={`absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full flex items-center justify-center ${isMissed ? 'bg-red-500' : isOutgoing ? 'bg-blue-500' : 'bg-green-500'}`}>
                          {isMissed ? <PhoneMissed size={10} className="text-white" /> : isOutgoing ? <PhoneOutgoing size={10} className="text-white" /> : <PhoneIncoming size={10} className="text-white" />}
                        </div>
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0" onClick={() => other && navigate(`/chat/${otherId}`)} role="button">
                        <p className={`font-semibold text-sm truncate ${isMissed ? 'text-red-500' : 'text-[var(--nexly-text)]'}`}>
                          {other?.name || 'Unknown'}
                        </p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {isVideo ? <Video size={12} className="text-[var(--nexly-text-secondary)]" /> : <Phone size={12} className="text-[var(--nexly-text-secondary)]" />}
                          <span className="text-xs text-[var(--nexly-text-secondary)]">
                            {isOutgoing ? 'Outgoing' : 'Incoming'} {call.call_type}
                          </span>
                        </div>
                      </div>

                      {/* Time + Duration */}
                      <div className="text-right shrink-0">
                        <p className="text-xs text-[var(--nexly-text-secondary)]">
                          {new Date(call.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                        {call.duration_seconds ? (
                          <div className="flex items-center gap-1 justify-end mt-0.5">
                            <Clock size={10} className="text-[var(--nexly-text-secondary)]" />
                            <span className="text-xs text-[var(--nexly-text-secondary)]">{formatDuration(call.duration_seconds)}</span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-red-400 font-medium">{call.status}</span>
                        )}
                      </div>

                      {/* Re-call button */}
                      <button
                        onClick={() => other && initiateCall(otherId, call.call_type as 'voice' | 'video')}
                        className="p-2.5 rounded-full hover:bg-[var(--nexly-sent)]/10 transition-colors"
                      >
                        {isVideo ? <Video size={20} className="text-[var(--nexly-sent)]" /> : <Phone size={20} className="text-[var(--nexly-sent)]" />}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `0:${seconds.toString().padStart(2, '0')}`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}:${(m % 60).toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function groupByDate(calls: CallRecord[]): { label: string; items: CallRecord[] }[] {
  const groups = new Map<string, CallRecord[]>();
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  for (const call of calls) {
    const date = new Date(call.started_at).toDateString();
    let label: string;
    if (date === today) label = 'Today';
    else if (date === yesterday) label = 'Yesterday';
    else label = new Date(call.started_at).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });

    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(call);
  }

  return [...groups.entries()].map(([label, items]) => ({ label, items }));
}
