import { create } from 'zustand';
import { api, type User } from '../lib/api';
import { socket } from '../lib/ws';

interface AuthStore {
  user: User | null;
  token: string | null;
  loading: boolean;
  setToken: (token: string, userId: string) => void;
  loadUser: () => Promise<void>;
  updateUser: (data: Partial<User>) => void;
  logout: () => void;
}

export const useAuth = create<AuthStore>((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  loading: true,

  setToken: (token, userId) => {
    localStorage.setItem('token', token);
    localStorage.setItem('userId', userId);
    set({ token });
  },

  loadUser: async () => {
    try {
      const user = await api.getMe();
      set({ user, loading: false });
      socket.connect();
    } catch {
      localStorage.removeItem('token');
      localStorage.removeItem('userId');
      set({ user: null, token: null, loading: false });
    }
  },

  updateUser: (data) => {
    const user = get().user;
    if (user) set({ user: { ...user, ...data } });
  },

  logout: () => {
    socket.disconnect();
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    set({ user: null, token: null });
  },
}));
