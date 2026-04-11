import { useState, useRef } from 'react';
import { Camera, LogOut, Moon, Sun, Check } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../stores/auth';
import { useTheme } from '../stores/theme';
import { Avatar } from '../components/Avatar';

export function ProfilePage() {
  const { user, updateUser, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const [name, setName] = useState(user?.name || '');
  const [statusText, setStatusText] = useState(user?.status_text || '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!user) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await api.updateMe({ name, status_text: statusText });
      updateUser(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    setSaving(false);
  };

  const handleAvatar = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const updated = await api.uploadAvatar(file);
      updateUser(updated);
    } catch {}
  };

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-4 py-3 z-40">
        <h1 className="text-xl font-bold text-[var(--nexly-text)]">Profile</h1>
      </div>

      <div className="px-4 py-6 max-w-sm mx-auto space-y-6">
        {/* Avatar */}
        <div className="flex flex-col items-center">
          <div className="relative cursor-pointer" onClick={() => fileRef.current?.click()}>
            <Avatar src={user.avatar_url} name={user.name} size={96} />
            <div className="absolute bottom-0 right-0 w-8 h-8 rounded-full bg-[var(--nexly-sent)] flex items-center justify-center shadow-lg">
              <Camera size={14} className="text-white" />
            </div>
          </div>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleAvatar} />
          <p className="text-sm text-[var(--nexly-text-secondary)] mt-2">{user.phone}</p>
        </div>

        {/* Name */}
        <div>
          <label className="text-sm font-medium text-[var(--nexly-text-secondary)] mb-1.5 block">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full py-3 px-4 rounded-xl bg-[var(--nexly-surface)] border border-[var(--nexly-border)] text-[var(--nexly-text)] focus:outline-none focus:border-[var(--nexly-sent)]"
          />
        </div>

        {/* Status */}
        <div>
          <label className="text-sm font-medium text-[var(--nexly-text-secondary)] mb-1.5 block">
            Status
          </label>
          <input
            type="text"
            value={statusText}
            onChange={(e) => setStatusText(e.target.value)}
            className="w-full py-3 px-4 rounded-xl bg-[var(--nexly-surface)] border border-[var(--nexly-border)] text-[var(--nexly-text)] focus:outline-none focus:border-[var(--nexly-sent)]"
          />
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] text-white font-semibold flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50"
        >
          {saved ? <><Check size={18} /> Saved!</> : saving ? 'Saving...' : 'Save Changes'}
        </button>

        {/* Settings */}
        <div className="space-y-2 pt-4 border-t border-[var(--nexly-border)]">
          <button
            onClick={toggle}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-[var(--nexly-border)]/30 transition-colors"
          >
            {dark ? <Sun size={20} className="text-amber-400" /> : <Moon size={20} className="text-[var(--nexly-text-secondary)]" />}
            <span className="text-[var(--nexly-text)]">{dark ? 'Light Mode' : 'Dark Mode'}</span>
          </button>

          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-red-500"
          >
            <LogOut size={20} />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </div>
  );
}
