import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MessageSquarePlus, Archive, Bookmark, Pin, BellOff, FolderPlus, Folder,
  MoreVertical, Trash2, ArchiveX,
} from 'lucide-react';
import { Avatar } from '../components/Avatar';
import { useChat } from '../stores/chat';
import { api, type ChatFolder, type Conversation } from '../lib/api';

export function ChatsPage() {
  const { conversations, loadConversations } = useChat();
  const [folders, setFolders] = useState<ChatFolder[]>([]);
  const [activeFolder, setActiveFolder] = useState<string | 'all'>('all');
  const [sheetFor, setSheetFor] = useState<Conversation | null>(null);
  const [showFolderModal, setShowFolderModal] = useState(false);
  const navigate = useNavigate();

  const loadFolders = async () => {
    try {
      const f = await api.getChatFolders();
      setFolders(f);
    } catch {}
  };

  useEffect(() => {
    loadConversations();
    loadFolders();
  }, []);

  const filtered = useMemo(() => {
    if (activeFolder === 'all') return conversations;
    return conversations.filter((c) => c.folder_id === activeFolder);
  }, [conversations, activeFolder]);

  const hasArchived = conversations.length > 0; // server filters archived out; button always visible

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 bg-[var(--nexly-surface)] border-b border-[var(--nexly-border)] z-40">
        <div className="px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold text-[var(--nexly-text)]">Chats</h1>
          <button
            onClick={() => navigate('/contacts')}
            className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-[var(--nexly-border)] transition-colors"
          >
            <MessageSquarePlus size={22} className="text-[var(--nexly-sent)]" />
          </button>
        </div>

        {/* Folder tabs */}
        <div className="flex gap-2 px-3 pb-2 overflow-x-auto">
          <FolderPill
            active={activeFolder === 'all'}
            onClick={() => setActiveFolder('all')}
            label="All"
          />
          {folders.map((f) => (
            <FolderPill
              key={f.id}
              active={activeFolder === f.id}
              onClick={() => setActiveFolder(f.id)}
              label={f.name}
              icon={f.icon}
            />
          ))}
          <button
            onClick={() => setShowFolderModal(true)}
            className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full border border-dashed border-[var(--nexly-border)] text-xs text-[var(--nexly-text-secondary)]"
          >
            <FolderPlus size={14} /> Folder
          </button>
        </div>
      </div>

      {/* Shortcuts */}
      <div className="divide-y divide-[var(--nexly-border)]">
        <ShortcutRow
          icon={<Bookmark size={22} className="text-[var(--nexly-sent)]" />}
          label="Saved Messages"
          sublabel="Your private notes"
          onClick={() => navigate('/saved')}
        />
        {hasArchived && (
          <ShortcutRow
            icon={<Archive size={22} className="text-[var(--nexly-text-secondary)]" />}
            label="Archived"
            sublabel="Chats you've archived"
            onClick={() => navigate('/archived')}
          />
        )}

        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <div className="w-16 h-16 rounded-full bg-[var(--nexly-border)] flex items-center justify-center mb-3">
              <MessageSquarePlus size={28} className="text-[var(--nexly-text-secondary)]" />
            </div>
            <p className="text-sm text-[var(--nexly-text-secondary)]">
              {activeFolder === 'all'
                ? 'No conversations yet'
                : 'No chats in this folder'}
            </p>
          </div>
        ) : (
          filtered.map((convo) => (
            <ConversationRow key={convo.user.id} convo={convo} onMore={() => setSheetFor(convo)} />
          ))
        )}
      </div>

      {/* Per-chat actions sheet */}
      {sheetFor && (
        <ChatActionsSheet
          convo={sheetFor}
          folders={folders}
          onClose={() => setSheetFor(null)}
          onChanged={() => {
            setSheetFor(null);
            loadConversations();
          }}
        />
      )}

      {/* Folder manage modal */}
      {showFolderModal && (
        <FolderManageModal
          folders={folders}
          onClose={() => setShowFolderModal(false)}
          onChanged={loadFolders}
        />
      )}
    </div>
  );
}

function FolderPill({
  active,
  onClick,
  label,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  icon?: string | null;
}) {
  return (
    <button
      onClick={onClick}
      className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
        active
          ? 'bg-[var(--nexly-sent)] text-white'
          : 'bg-[var(--nexly-bg)] text-[var(--nexly-text-secondary)] border border-[var(--nexly-border)]'
      }`}
    >
      {icon ? <span>{icon}</span> : <Folder size={12} />}
      <span>{label}</span>
    </button>
  );
}

function ShortcutRow({
  icon,
  label,
  sublabel,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--nexly-border)]/30 transition-colors text-left"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--nexly-sent)]/10 flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-[var(--nexly-text)] truncate">{label}</div>
        <div className="text-xs text-[var(--nexly-text-secondary)] truncate">{sublabel}</div>
      </div>
    </button>
  );
}

function ConversationRow({
  convo,
  onMore,
}: {
  convo: Conversation;
  onMore: () => void;
}) {
  const navigate = useNavigate();
  const { user, last_message, unread_count, is_pinned, is_muted } = convo;

  const time = last_message
    ? new Date(last_message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  const preview =
    last_message?.message_type === 'voice'
      ? 'Voice message'
      : last_message?.content?.slice(0, 50) || '';

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 transition-colors text-left ${
        is_pinned ? 'bg-[var(--nexly-sent)]/5' : 'hover:bg-[var(--nexly-border)]/30'
      }`}
    >
      <button
        onClick={() => navigate(`/chat/${user.id}`)}
        className="flex-1 flex items-center gap-3 min-w-0 text-left"
      >
        <Avatar src={user.avatar_url} name={user.name} size={52} online={user.is_online} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-[var(--nexly-text)] truncate flex items-center gap-1">
              {user.name}
              {is_pinned && <Pin size={12} className="text-[var(--nexly-sent)] shrink-0" />}
              {is_muted && <BellOff size={12} className="text-[var(--nexly-text-secondary)] shrink-0" />}
            </span>
            <span className="text-xs text-[var(--nexly-text-secondary)] shrink-0 ml-2">{time}</span>
          </div>
          <div className="flex items-center justify-between mt-0.5">
            <span className="text-sm text-[var(--nexly-text-secondary)] truncate">{preview}</span>
            {unread_count > 0 && (
              <span
                className={`ml-2 shrink-0 min-w-[20px] h-5 rounded-full text-white text-xs flex items-center justify-center px-1.5 font-medium ${
                  is_muted ? 'bg-[var(--nexly-text-secondary)]' : 'bg-[var(--nexly-sent)]'
                }`}
              >
                {unread_count}
              </span>
            )}
          </div>
        </div>
      </button>
      <button
        onClick={onMore}
        className="p-2 rounded-full hover:bg-[var(--nexly-border)]/50"
      >
        <MoreVertical size={18} className="text-[var(--nexly-text-secondary)]" />
      </button>
    </div>
  );
}

function ChatActionsSheet({
  convo,
  folders,
  onClose,
  onChanged,
}: {
  convo: Conversation;
  folders: ChatFolder[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [folderMode, setFolderMode] = useState(false);
  const uid = convo.user.id;

  const run = async (fn: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
      onChanged();
    } catch {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-end"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg mx-auto bg-[var(--nexly-surface)] rounded-t-2xl p-4 space-y-1"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center text-sm font-semibold text-[var(--nexly-text)] pb-2">
          {convo.user.name}
        </div>

        {!folderMode ? (
          <>
            <SheetAction
              icon={<Pin size={18} />}
              label={convo.is_pinned ? 'Unpin chat' : 'Pin chat'}
              onClick={() =>
                run(() => (convo.is_pinned ? api.unpinChat(uid) : api.pinChat(uid)))
              }
            />
            <SheetAction
              icon={<BellOff size={18} />}
              label={convo.is_muted ? 'Unmute' : 'Mute notifications'}
              onClick={() =>
                run(() =>
                  convo.is_muted ? api.unmuteChat(uid) : api.muteChat(uid, 8)
                )
              }
              sublabel={convo.is_muted ? undefined : '8 hours'}
            />
            <SheetAction
              icon={<Folder size={18} />}
              label={convo.folder_id ? 'Change folder' : 'Add to folder'}
              onClick={() => setFolderMode(true)}
              disabled={busy}
            />
            <SheetAction
              icon={convo.is_archived ? <ArchiveX size={18} /> : <Archive size={18} />}
              label={convo.is_archived ? 'Unarchive' : 'Archive chat'}
              onClick={() =>
                run(() =>
                  convo.is_archived ? api.unarchiveChat(uid) : api.archiveChat(uid)
                )
              }
            />
            <button
              onClick={onClose}
              className="w-full mt-2 py-3 rounded-xl bg-[var(--nexly-border)] text-[var(--nexly-text)] font-medium"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <div className="text-xs text-[var(--nexly-text-secondary)] px-2 pb-1">
              Choose a folder
            </div>
            <SheetAction
              icon={<span className="text-base">—</span>}
              label="No folder"
              onClick={() => run(() => api.assignChatFolder(uid, null))}
              active={!convo.folder_id}
            />
            {folders.map((f) => (
              <SheetAction
                key={f.id}
                icon={f.icon ? <span className="text-base">{f.icon}</span> : <Folder size={18} />}
                label={f.name}
                onClick={() => run(() => api.assignChatFolder(uid, f.id))}
                active={convo.folder_id === f.id}
              />
            ))}
            {folders.length === 0 && (
              <div className="text-center text-xs text-[var(--nexly-text-secondary)] py-4">
                No folders yet. Create one from the Chats screen.
              </div>
            )}
            <button
              onClick={() => setFolderMode(false)}
              className="w-full mt-2 py-3 rounded-xl bg-[var(--nexly-border)] text-[var(--nexly-text)] font-medium"
            >
              Back
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function SheetAction({
  icon,
  label,
  sublabel,
  onClick,
  disabled,
  active,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel?: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-left disabled:opacity-50 ${
        active ? 'bg-[var(--nexly-sent)]/10' : 'hover:bg-[var(--nexly-border)]/40'
      }`}
    >
      <span className={`w-8 h-8 rounded-full flex items-center justify-center ${
        active ? 'bg-[var(--nexly-sent)] text-white' : 'bg-[var(--nexly-border)] text-[var(--nexly-text)]'
      }`}>
        {icon}
      </span>
      <span className="flex-1">
        <span className="block text-sm font-medium text-[var(--nexly-text)]">{label}</span>
        {sublabel && (
          <span className="block text-xs text-[var(--nexly-text-secondary)]">{sublabel}</span>
        )}
      </span>
    </button>
  );
}

function FolderManageModal({
  folders,
  onClose,
  onChanged,
}: {
  folders: ChatFolder[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [newName, setNewName] = useState('');
  const [newIcon, setNewIcon] = useState('📁');
  const [saving, setSaving] = useState(false);

  const create = async () => {
    const name = newName.trim();
    if (!name || saving) return;
    setSaving(true);
    try {
      await api.createChatFolder(name, newIcon);
      setNewName('');
      onChanged();
    } catch {}
    setSaving(false);
  };

  const remove = async (id: string) => {
    try {
      await api.deleteChatFolder(id);
      onChanged();
    } catch {}
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm bg-[var(--nexly-surface)] rounded-2xl p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-[var(--nexly-text)] mb-3">Folders</h3>

        <div className="space-y-2 max-h-64 overflow-y-auto mb-3">
          {folders.length === 0 && (
            <p className="text-sm text-[var(--nexly-text-secondary)] text-center py-4">
              No folders yet.
            </p>
          )}
          {folders.map((f) => (
            <div
              key={f.id}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--nexly-bg)]"
            >
              <span className="text-lg">{f.icon || '📁'}</span>
              <span className="flex-1 text-sm text-[var(--nexly-text)]">{f.name}</span>
              <button
                onClick={() => remove(f.id)}
                className="text-red-500 p-1"
                aria-label="Delete folder"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 mb-2">
          <input
            type="text"
            value={newIcon}
            onChange={(e) => setNewIcon(e.target.value.slice(0, 4))}
            placeholder="📁"
            className="w-12 text-center py-2 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)]"
          />
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && create()}
            placeholder="Folder name"
            className="flex-1 py-2 px-3 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm"
          />
          <button
            onClick={create}
            disabled={!newName.trim() || saving}
            className="px-3 py-2 rounded-lg bg-[var(--nexly-sent)] text-white text-sm disabled:opacity-50"
          >
            Add
          </button>
        </div>

        <button
          onClick={onClose}
          className="w-full mt-2 py-2.5 rounded-lg bg-[var(--nexly-border)] text-[var(--nexly-text)] font-medium"
        >
          Done
        </button>
      </div>
    </div>
  );
}
