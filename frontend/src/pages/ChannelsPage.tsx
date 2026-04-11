import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Radio, Search, Hash } from 'lucide-react';
import { api, type Channel } from '../lib/api';
import { Avatar } from '../components/Avatar';

export function ChannelsPage() {
  const [myChannels, setMyChannels] = useState<Channel[]>([]);
  const [explore, setExplore] = useState<Channel[]>([]);
  const [tab, setTab] = useState<'mine' | 'explore'>('mine');
  const [searchQ, setSearchQ] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { api.getMyChannels().then(setMyChannels); }, []);

  useEffect(() => {
    if (tab === 'explore') api.exploreChannels(searchQ).then(setExplore);
  }, [tab, searchQ]);

  const channels = tab === 'mine' ? myChannels : explore;

  return (
    <div className="pb-20">
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] z-40">
        <div className="px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold text-[var(--nexly-text)]">Channels</h1>
          <button onClick={() => setShowCreate(true)} className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-[var(--nexly-border)]">
            <Plus size={22} className="text-[var(--nexly-sent)]" />
          </button>
        </div>
        <div className="flex border-b border-[var(--nexly-border)]">
          {(['mine', 'explore'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'text-[var(--nexly-sent)] border-b-2 border-[var(--nexly-sent)]' : 'text-[var(--nexly-text-secondary)]'}`}>
              {t === 'mine' ? 'My Channels' : 'Explore'}
            </button>
          ))}
        </div>
        {tab === 'explore' && (
          <div className="px-4 py-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--nexly-text-secondary)]" />
              <input type="text" value={searchQ} onChange={(e) => setSearchQ(e.target.value)} placeholder="Search channels..."
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]" />
            </div>
          </div>
        )}
      </div>

      {showCreate && <CreateChannelModal onClose={() => setShowCreate(false)} onCreated={(c) => { setMyChannels([c, ...myChannels]); setShowCreate(false); }} />}

      {channels.length === 0 ? (
        <div className="flex flex-col items-center py-20 text-center">
          <Radio size={48} className="text-[var(--nexly-text-secondary)] mb-3" />
          <h3 className="text-lg font-semibold text-[var(--nexly-text)]">{tab === 'mine' ? 'No channels yet' : 'No channels found'}</h3>
        </div>
      ) : (
        <div className="divide-y divide-[var(--nexly-border)]">
          {channels.map((ch) => (
            <button key={ch.id} onClick={() => navigate(`/channel/${ch.id}`)}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--nexly-border)]/30 transition-colors text-left">
              <Avatar src={ch.avatar_url} name={ch.name} size={52} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <p className="font-semibold text-[var(--nexly-text)] truncate">{ch.name}</p>
                  {ch.username && <span className="text-xs text-[var(--nexly-text-secondary)]">@{ch.username}</span>}
                </div>
                <p className="text-sm text-[var(--nexly-text-secondary)]">{ch.subscriber_count} subscribers</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateChannelModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: Channel) => void }) {
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [desc, setDesc] = useState('');
  const [isPublic, setIsPublic] = useState(true);
  const [loading, setLoading] = useState(false);

  const create = async () => {
    if (!name.trim()) return;
    setLoading(true);
    try {
      const ch = await api.createChannel(name, username || undefined as any, desc, isPublic);
      onCreated(ch);
    } catch {}
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--nexly-surface)] w-full max-w-md rounded-t-2xl sm:rounded-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-[var(--nexly-text)] mb-4">New Channel</h2>
        <input type="text" placeholder="Channel name" value={name} onChange={(e) => setName(e.target.value)}
          className="w-full py-2.5 px-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] mb-3 focus:outline-none focus:border-[var(--nexly-sent)]" />
        <div className="relative mb-3">
          <Hash size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--nexly-text-secondary)]" />
          <input type="text" placeholder="username (optional)" value={username} onChange={(e) => setUsername(e.target.value.replace(/\s/g, ''))}
            className="w-full py-2.5 pl-9 pr-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] focus:outline-none focus:border-[var(--nexly-sent)]" />
        </div>
        <textarea placeholder="Description" value={desc} onChange={(e) => setDesc(e.target.value)} rows={2}
          className="w-full py-2.5 px-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] mb-3 resize-none focus:outline-none focus:border-[var(--nexly-sent)]" />
        <label className="flex items-center gap-2 mb-4 cursor-pointer">
          <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} className="accent-[var(--nexly-sent)]" />
          <span className="text-sm text-[var(--nexly-text)]">Public channel</span>
        </label>
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-[var(--nexly-border)] text-[var(--nexly-text)]">Cancel</button>
          <button onClick={create} disabled={loading || !name.trim()}
            className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] text-white font-semibold disabled:opacity-50">
            {loading ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}
