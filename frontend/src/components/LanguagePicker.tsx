import { useEffect, useState } from 'react';
import { Globe, Check, Search } from 'lucide-react';
import { api, type Language } from '../lib/api';

interface Props {
  selected: string;
  onSelect: (code: string) => void;
  compact?: boolean;
}

export function LanguagePicker({ selected, onSelect, compact }: Props) {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  useEffect(() => {
    api.getLanguages().then(setLanguages).catch(() => {
      // Fallback if API is down
      setLanguages([
        { code: 'en', name: 'English' },
        { code: 'fa', name: 'فارسی (Persian)' },
        { code: 'ar', name: 'العربية (Arabic)' },
        { code: 'es', name: 'Español (Spanish)' },
        { code: 'fr', name: 'Français (French)' },
        { code: 'de', name: 'Deutsch (German)' },
        { code: 'it', name: 'Italiano (Italian)' },
        { code: 'ru', name: 'Русский (Russian)' },
        { code: 'zh', name: '中文 (Chinese)' },
        { code: 'ja', name: '日本語 (Japanese)' },
        { code: 'ko', name: '한국어 (Korean)' },
        { code: 'tr', name: 'Türkçe (Turkish)' },
        { code: 'hi', name: 'हिन्दी (Hindi)' },
        { code: 'pt', name: 'Português (Portuguese)' },
      ]);
    });
  }, []);

  const selectedLang = languages.find((l) => l.code === selected);
  const filtered = languages.filter((l) =>
    l.name.toLowerCase().includes(search.toLowerCase()) || l.code.includes(search.toLowerCase())
  );

  if (compact) {
    return (
      <>
        <button onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-4 py-3 rounded-xl hover:bg-[var(--nexly-border)]/30 w-full transition-colors">
          <Globe size={20} className="text-[var(--nexly-sent)]" />
          <div className="flex-1 text-left">
            <p className="text-[var(--nexly-text)] text-sm">Language</p>
            <p className="text-xs text-[var(--nexly-text-secondary)]">{selectedLang?.name || selected}</p>
          </div>
        </button>
        {open && <LanguageModal languages={filtered} selected={selected} onSelect={(c) => { onSelect(c); setOpen(false); }} onClose={() => setOpen(false)} search={search} onSearch={setSearch} />}
      </>
    );
  }

  return (
    <div>
      <label className="text-sm font-medium text-[var(--nexly-text-secondary)] mb-2 block">
        <Globe size={16} className="inline mr-1" /> Your Language
      </label>
      <p className="text-xs text-[var(--nexly-text-secondary)] mb-3">
        All messages will be automatically translated to your language
      </p>
      <button onClick={() => setOpen(true)}
        className="w-full py-3 px-4 rounded-xl bg-[var(--nexly-surface)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-left flex items-center justify-between hover:border-[var(--nexly-sent)] transition-colors">
        <span>{selectedLang?.name || 'Select language'}</span>
        <Globe size={18} className="text-[var(--nexly-text-secondary)]" />
      </button>
      {open && <LanguageModal languages={filtered} selected={selected} onSelect={(c) => { onSelect(c); setOpen(false); }} onClose={() => setOpen(false)} search={search} onSearch={setSearch} />}
    </div>
  );
}

function LanguageModal({ languages, selected, onSelect, onClose, search, onSearch }: {
  languages: Language[]; selected: string; onSelect: (code: string) => void; onClose: () => void; search: string; onSearch: (v: string) => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--nexly-surface)] w-full max-w-md rounded-t-2xl sm:rounded-2xl max-h-[70vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="p-4 border-b border-[var(--nexly-border)]">
          <h2 className="text-lg font-bold text-[var(--nexly-text)] mb-3">Select Language</h2>
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--nexly-text-secondary)]" />
            <input type="text" value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search languages..."
              className="w-full pl-10 pr-4 py-2 rounded-lg bg-[var(--nexly-bg)] border border-[var(--nexly-border)] text-[var(--nexly-text)] text-sm focus:outline-none focus:border-[var(--nexly-sent)]" autoFocus />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {languages.map((lang) => (
            <button key={lang.code} onClick={() => onSelect(lang.code)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                selected === lang.code ? 'bg-[var(--nexly-sent)]/10 text-[var(--nexly-sent)]' : 'hover:bg-[var(--nexly-border)]/30 text-[var(--nexly-text)]'
              }`}>
              <span className="flex-1 text-left text-sm">{lang.name}</span>
              <span className="text-xs text-[var(--nexly-text-secondary)] uppercase">{lang.code}</span>
              {selected === lang.code && <Check size={18} className="text-[var(--nexly-sent)]" />}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
