import { MessageCircle, Users, User, UsersRound, Radio, Eye, Phone } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

const tabs = [
  { path: '/chats', icon: MessageCircle, label: 'Chats' },
  { path: '/groups', icon: UsersRound, label: 'Groups' },
  { path: '/channels', icon: Radio, label: 'Channels' },
  { path: '/stories', icon: Eye, label: 'Stories' },
  { path: '/profile', icon: User, label: 'Profile' },
];

export function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  // Hide on detail pages
  const hidePaths = ['/chat/', '/group/', '/channel/'];
  if (hidePaths.some((p) => location.pathname.startsWith(p))) return null;

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-[var(--nexly-surface)] border-t border-[var(--nexly-border)] z-50">
      <div className="max-w-lg mx-auto flex">
        {tabs.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path;
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`flex-1 flex flex-col items-center py-2 gap-0.5 transition-colors ${
                active ? 'text-[var(--nexly-sent)]' : 'text-[var(--nexly-text-secondary)]'
              }`}
            >
              <Icon size={20} />
              <span className="text-[10px] font-medium">{label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
