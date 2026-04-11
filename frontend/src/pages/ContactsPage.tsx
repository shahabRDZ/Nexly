import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, UserPlus } from 'lucide-react';
import { api, type User } from '../lib/api';
import { Avatar } from '../components/Avatar';

export function ContactsPage() {
  const [contacts, setContacts] = useState<User[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [searching, setSearching] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getContacts().then(setContacts);
  }, []);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await api.searchUsers(searchQuery);
        const myId = localStorage.getItem('userId');
        setSearchResults(results.filter((u) => u.id !== myId));
      } catch {}
      setSearching(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const displayUsers = searchQuery.trim() ? searchResults : contacts;

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] z-40">
        <div className="px-4 py-3">
          <h1 className="text-xl font-bold text-[var(--nexly-text)]">Contacts</h1>
        </div>
        <div className="px-4 pb-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--nexly-text-secondary)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name or phone..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]"
            />
          </div>
        </div>
      </div>

      {/* Sync prompt */}
      {!searchQuery && contacts.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
          <div className="w-20 h-20 rounded-full bg-[var(--nexly-border)] flex items-center justify-center mb-4">
            <UserPlus size={36} className="text-[var(--nexly-text-secondary)]" />
          </div>
          <h3 className="text-lg font-semibold text-[var(--nexly-text)] mb-1">Find your friends</h3>
          <p className="text-sm text-[var(--nexly-text-secondary)] mb-4">
            Search by phone number or name to find people on Nexly
          </p>
        </div>
      )}

      {searching && (
        <div className="flex justify-center py-8">
          <div className="animate-spin w-6 h-6 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" />
        </div>
      )}

      {/* User list */}
      <div className="divide-y divide-[var(--nexly-border)]">
        {displayUsers.map((user) => (
          <button
            key={user.id}
            onClick={() => navigate(`/chat/${user.id}`)}
            className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--nexly-border)]/30 transition-colors text-left"
          >
            <Avatar src={user.avatar_url} name={user.name} size={48} online={user.is_online} />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-[var(--nexly-text)] truncate">{user.name}</p>
              <p className="text-sm text-[var(--nexly-text-secondary)] truncate">{user.status_text}</p>
            </div>
          </button>
        ))}
      </div>

      {searchQuery && !searching && searchResults.length === 0 && (
        <p className="text-center text-sm text-[var(--nexly-text-secondary)] py-8">
          No users found for "{searchQuery}"
        </p>
      )}
    </div>
  );
}
