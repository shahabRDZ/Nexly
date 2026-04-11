import { useEffect, useState } from 'react';
import { Phone, Video, PhoneIncoming, PhoneOutgoing, PhoneMissed } from 'lucide-react';
import { api, type CallRecord, type User } from '../lib/api';
import { Avatar } from '../components/Avatar';

export function CallsPage() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [users, setUsers] = useState<Map<string, User>>(new Map());
  const myId = localStorage.getItem('userId')!;

  useEffect(() => {
    api.getCallHistory().then(async (records) => {
      setCalls(records);
      const userMap = new Map<string, User>();
      const ids = new Set(records.flatMap((c) => [c.caller_id, c.callee_id]).filter((id) => id !== myId));
      for (const id of ids) {
        try { const u = await api.getUser(id); userMap.set(id, u); } catch {}
      }
      setUsers(userMap);
    });
  }, []);

  return (
    <div className="pb-20">
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-4 py-3 z-40">
        <h1 className="text-xl font-bold text-[var(--nexly-text)]">Calls</h1>
      </div>

      {calls.length === 0 ? (
        <div className="flex flex-col items-center py-20 text-center">
          <Phone size={48} className="text-[var(--nexly-text-secondary)] mb-3" />
          <h3 className="text-lg font-semibold text-[var(--nexly-text)]">No calls yet</h3>
          <p className="text-sm text-[var(--nexly-text-secondary)]">Your call history will appear here</p>
        </div>
      ) : (
        <div className="divide-y divide-[var(--nexly-border)]">
          {calls.map((call) => {
            const isOutgoing = call.caller_id === myId;
            const otherId = isOutgoing ? call.callee_id : call.caller_id;
            const other = users.get(otherId);
            const isMissed = call.status === 'missed' || call.status === 'declined';

            return (
              <div key={call.id} className="flex items-center gap-3 px-4 py-3">
                <Avatar src={other?.avatar_url || null} name={other?.name || 'Unknown'} size={48} />
                <div className="flex-1 min-w-0">
                  <p className={`font-semibold truncate ${isMissed ? 'text-red-500' : 'text-[var(--nexly-text)]'}`}>
                    {other?.name || otherId.slice(0, 8)}
                  </p>
                  <div className="flex items-center gap-1 text-sm text-[var(--nexly-text-secondary)]">
                    {isMissed ? <PhoneMissed size={14} className="text-red-500" /> : isOutgoing ? <PhoneOutgoing size={14} /> : <PhoneIncoming size={14} className="text-green-500" />}
                    <span>{isOutgoing ? 'Outgoing' : 'Incoming'} {call.call_type}</span>
                    <span>·</span>
                    <span>{new Date(call.started_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="text-right">
                  {call.duration_seconds ? (
                    <span className="text-sm text-[var(--nexly-text-secondary)]">{formatDuration(call.duration_seconds)}</span>
                  ) : (
                    <span className="text-sm text-red-400">{call.status}</span>
                  )}
                </div>
                <button className="p-2 text-[var(--nexly-sent)]">
                  {call.call_type === 'video' ? <Video size={20} /> : <Phone size={20} />}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}
