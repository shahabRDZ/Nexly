import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Users } from 'lucide-react';
import { api, type Group, type User } from '../lib/api';
import { Avatar } from '../components/Avatar';

export function GroupsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { api.getMyGroups().then(setGroups); }, []);

  return (
    <div className="pb-20">
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-4 py-3 flex items-center justify-between z-40">
        <h1 className="text-xl font-bold text-[var(--nexly-text)]">Groups</h1>
        <button onClick={() => setShowCreate(true)} className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-[var(--nexly-border)] transition-colors">
          <Plus size={22} className="text-[var(--nexly-sent)]" />
        </button>
      </div>

      {showCreate && <CreateGroupModal onClose={() => setShowCreate(false)} onCreated={(g) => { setGroups([g, ...groups]); setShowCreate(false); }} />}

      {groups.length === 0 ? (
        <div className="flex flex-col items-center py-20 text-center px-6">
          <Users size={48} className="text-[var(--nexly-text-secondary)] mb-3" />
          <h3 className="text-lg font-semibold text-[var(--nexly-text)]">No groups yet</h3>
          <p className="text-sm text-[var(--nexly-text-secondary)]">Create a group to start chatting</p>
        </div>
      ) : (
        <div className="divide-y divide-[var(--nexly-border)]">
          {groups.map((g) => (
            <button key={g.id} onClick={() => navigate(`/group/${g.id}`)}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--nexly-border)]/30 transition-colors text-left">
              <Avatar src={g.avatar_url} name={g.name} size={52} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-[var(--nexly-text)] truncate">{g.name}</p>
                <p className="text-sm text-[var(--nexly-text-secondary)]">{g.member_count} members</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateGroupModal({ onClose, onCreated }: { onClose: () => void; onCreated: (g: Group) => void }) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [contacts, setContacts] = useState<User[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.getContacts().then(setContacts); }, []);

  const toggle = (id: string) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  };

  const create = async () => {
    if (!name.trim()) return;
    setLoading(true);
    try {
      const group = await api.createGroup(name, desc, Array.from(selected));
      onCreated(group);
    } catch {}
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--nexly-surface)] w-full max-w-md rounded-t-2xl sm:rounded-2xl p-5 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-[var(--nexly-text)] mb-4">New Group</h2>
        <input type="text" placeholder="Group name" value={name} onChange={(e) => setName(e.target.value)}
          className="w-full py-2.5 px-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] mb-3 focus:outline-none focus:border-[var(--nexly-sent)]" />
        <input type="text" placeholder="Description (optional)" value={desc} onChange={(e) => setDesc(e.target.value)}
          className="w-full py-2.5 px-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] mb-4 focus:outline-none focus:border-[var(--nexly-sent)]" />

        <p className="text-sm font-medium text-[var(--nexly-text-secondary)] mb-2">Add members</p>
        <div className="space-y-1 mb-4 max-h-48 overflow-y-auto">
          {contacts.map((c) => (
            <button key={c.id} onClick={() => toggle(c.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${selected.has(c.id) ? 'bg-[var(--nexly-sent)]/10' : 'hover:bg-[var(--nexly-border)]/30'}`}>
              <Avatar src={c.avatar_url} name={c.name} size={36} />
              <span className="text-sm text-[var(--nexly-text)]">{c.name}</span>
              {selected.has(c.id) && <span className="ml-auto text-[var(--nexly-sent)] text-sm font-bold">✓</span>}
            </button>
          ))}
        </div>

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
