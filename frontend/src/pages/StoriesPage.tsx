import { useEffect, useState, useRef } from 'react';
import { Plus, Eye, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { api, type StoryGroup, type StoryItem } from '../lib/api';
import { Avatar } from '../components/Avatar';

export function StoriesPage() {
  const [feed, setFeed] = useState<StoryGroup[]>([]);
  const [viewingGroup, setViewingGroup] = useState<StoryGroup | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => { loadFeed(); }, []);
  const loadFeed = () => api.getStoryFeed().then(setFeed);

  const myId = localStorage.getItem('userId') ?? '';

  return (
    <div className="pb-20">
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] px-4 py-3 flex items-center justify-between z-40">
        <h1 className="text-xl font-bold text-[var(--nexly-text)]">Stories</h1>
        <button onClick={() => setShowCreate(true)} className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-[var(--nexly-border)]">
          <Plus size={22} className="text-[var(--nexly-sent)]" />
        </button>
      </div>

      {/* Story circles */}
      <div className="px-4 py-4 flex gap-4 overflow-x-auto">
        {feed.map((group) => (
          <button key={group.user_id} onClick={() => setViewingGroup(group)} className="flex flex-col items-center gap-1 shrink-0">
            <div className={`p-0.5 rounded-full ${group.has_unviewed ? 'bg-gradient-to-br from-[#6C5CE7] to-[#00CEC9]' : 'bg-[var(--nexly-border)]'}`}>
              <div className="p-0.5 bg-[var(--nexly-surface)] rounded-full">
                <Avatar src={group.avatar_url} name={group.name} size={56} />
              </div>
            </div>
            <span className="text-xs text-[var(--nexly-text)] max-w-[64px] truncate">
              {group.user_id === myId ? 'You' : group.name}
            </span>
          </button>
        ))}
      </div>

      {feed.length === 0 && (
        <div className="flex flex-col items-center py-16 text-center">
          <Eye size={48} className="text-[var(--nexly-text-secondary)] mb-3" />
          <h3 className="text-lg font-semibold text-[var(--nexly-text)]">No stories yet</h3>
          <p className="text-sm text-[var(--nexly-text-secondary)]">Add a story to share with your contacts</p>
        </div>
      )}

      {showCreate && <CreateStoryModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); loadFeed(); }} />}
      {viewingGroup && <StoryViewer group={viewingGroup} onClose={() => { setViewingGroup(null); loadFeed(); }} />}
    </div>
  );
}

function StoryViewer({ group, onClose }: { group: StoryGroup; onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const story = group.stories[idx];
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    let cancelled = false;
    if (story && !story.is_viewed) api.viewStory(story.id);
    timerRef.current = setTimeout(() => {
      if (cancelled) return;
      if (idx < group.stories.length - 1) setIdx(idx + 1);
      else onClose();
    }, 5000);
    return () => { cancelled = true; clearTimeout(timerRef.current); };
  }, [idx]);

  if (!story) return null;

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col">
      {/* Progress bars */}
      <div className="flex gap-1 px-3 pt-3">
        {group.stories.map((_, i) => (
          <div key={i} className="flex-1 h-0.5 rounded-full bg-white/30">
            <div className={`h-full rounded-full bg-white transition-all duration-[5000ms] ${i < idx ? 'w-full' : i === idx ? 'w-full animate-[grow_5s_linear]' : 'w-0'}`} />
          </div>
        ))}
      </div>

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        <Avatar src={group.avatar_url} name={group.name} size={36} />
        <div className="flex-1">
          <p className="text-white text-sm font-semibold">{group.name}</p>
          <p className="text-white/60 text-xs">{new Date(story.created_at).toLocaleTimeString()}</p>
        </div>
        <button onClick={onClose}><X size={24} className="text-white" /></button>
      </div>

      {/* Story content */}
      <div className="flex-1 flex items-center justify-center relative">
        {story.story_type === 'text' ? (
          <div className="w-full h-full flex items-center justify-center p-8" style={{ backgroundColor: story.bg_color || '#6C5CE7' }}>
            <p className="text-white text-2xl font-bold text-center">{story.text_content}</p>
          </div>
        ) : (
          <img src={story.media_url!} className="max-w-full max-h-full object-contain" alt="" />
        )}

        {/* Navigation */}
        <button onClick={() => idx > 0 && setIdx(idx - 1)} className="absolute left-0 top-0 bottom-0 w-1/3" />
        <button onClick={() => idx < group.stories.length - 1 ? setIdx(idx + 1) : onClose()} className="absolute right-0 top-0 bottom-0 w-1/3" />
      </div>

      <div className="px-4 py-3 text-center">
        <span className="text-white/60 text-sm"><Eye size={14} className="inline mr-1" />{story.view_count} views</span>
      </div>
    </div>
  );
}

function CreateStoryModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [tab, setTab] = useState<'text' | 'media'>('text');
  const [text, setText] = useState('');
  const [bgColor, setBgColor] = useState('#6C5CE7');
  const [loading, setLoading] = useState(false);
  const colors = ['#6C5CE7', '#00CEC9', '#E17055', '#00B894', '#FDCB6E', '#E84393', '#2D3436'];

  const createText = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try { await api.createTextStory(text, bgColor); onCreated(); } catch {}
    setLoading(false);
  };

  const createMedia = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try { await api.createMediaStory(file); onCreated(); } catch {}
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--nexly-surface)] w-full max-w-md rounded-t-2xl sm:rounded-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-[var(--nexly-text)] mb-4">New Story</h2>
        <div className="flex mb-4 border-b border-[var(--nexly-border)]">
          {(['text', 'media'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-2 text-sm font-medium ${tab === t ? 'text-[var(--nexly-sent)] border-b-2 border-[var(--nexly-sent)]' : 'text-[var(--nexly-text-secondary)]'}`}>
              {t === 'text' ? 'Text' : 'Photo/Video'}
            </button>
          ))}
        </div>

        {tab === 'text' ? (
          <>
            <div className="rounded-xl p-6 mb-3 min-h-[150px] flex items-center justify-center" style={{ backgroundColor: bgColor }}>
              <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your story..."
                className="bg-transparent text-white text-xl font-bold text-center w-full resize-none focus:outline-none placeholder:text-white/50" rows={3} />
            </div>
            <div className="flex gap-2 mb-4 justify-center">
              {colors.map((c) => (
                <button key={c} onClick={() => setBgColor(c)}
                  className={`w-8 h-8 rounded-full ${bgColor === c ? 'ring-2 ring-offset-2 ring-[var(--nexly-sent)]' : ''}`} style={{ backgroundColor: c }} />
              ))}
            </div>
            <button onClick={createText} disabled={loading || !text.trim()}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] text-white font-semibold disabled:opacity-50">
              {loading ? 'Posting...' : 'Share Story'}
            </button>
          </>
        ) : (
          <label className="block cursor-pointer">
            <div className="border-2 border-dashed border-[var(--nexly-border)] rounded-xl p-10 text-center hover:border-[var(--nexly-sent)] transition-colors">
              <Plus size={32} className="mx-auto text-[var(--nexly-text-secondary)] mb-2" />
              <p className="text-sm text-[var(--nexly-text-secondary)]">{loading ? 'Uploading...' : 'Tap to select photo or video'}</p>
            </div>
            <input type="file" accept="image/*,video/*" className="hidden" onChange={createMedia} />
          </label>
        )}
      </div>
    </div>
  );
}
