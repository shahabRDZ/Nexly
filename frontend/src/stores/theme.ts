import { create } from 'zustand';

interface ThemeStore {
  dark: boolean;
  toggle: () => void;
}

export const useTheme = create<ThemeStore>((set, get) => ({
  dark: localStorage.getItem('theme') === 'dark',
  toggle: () => {
    const next = !get().dark;
    localStorage.setItem('theme', next ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', next);
    set({ dark: next });
  },
}));

// Init on load
if (localStorage.getItem('theme') === 'dark') {
  document.documentElement.classList.add('dark');
}
