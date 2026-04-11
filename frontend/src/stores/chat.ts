import { create } from 'zustand';
import { api, type Conversation, type Message } from '../lib/api';

interface ChatStore {
  conversations: Conversation[];
  messages: Map<string, Message[]>;
  loadConversations: () => Promise<void>;
  loadMessages: (userId: string) => Promise<void>;
  addMessage: (msg: Message) => void;
  updateMessageStatus: (msgId: string, status: Message['status']) => void;
}

export const useChat = create<ChatStore>((set, get) => ({
  conversations: [],
  messages: new Map(),

  loadConversations: async () => {
    const conversations = await api.getConversations();
    set({ conversations });
  },

  loadMessages: async (userId) => {
    const msgs = await api.getMessages(userId);
    const map = new Map(get().messages);
    map.set(userId, msgs);
    set({ messages: map });
  },

  addMessage: (msg) => {
    const myId = localStorage.getItem('userId');
    const otherId = msg.sender_id === myId ? msg.receiver_id : msg.sender_id;
    const map = new Map(get().messages);
    const existing = map.get(otherId) || [];
    if (!existing.find((m) => m.id === msg.id)) {
      map.set(otherId, [...existing, msg]);
    }
    set({ messages: map });

    // Update conversation preview
    const convos = get().conversations.map((c) => {
      if (c.user.id === otherId) {
        return {
          ...c,
          last_message: msg,
          unread_count: msg.sender_id !== myId ? c.unread_count + 1 : c.unread_count,
        };
      }
      return c;
    });
    set({ conversations: convos });
  },

  updateMessageStatus: (msgId, status) => {
    const map = new Map(get().messages);
    for (const [key, msgs] of map) {
      const updated = msgs.map((m) => (m.id === msgId ? { ...m, status } : m));
      map.set(key, updated);
    }
    set({ messages: map });
  },
}));
