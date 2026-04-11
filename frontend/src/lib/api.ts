const BASE = '/api/v1';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // Auth
  sendOtp: (phone: string) =>
    request<{ message: string; debug_code: string }>('/auth/send-otp', {
      method: 'POST', body: JSON.stringify({ phone }),
    }),
  verifyOtp: (phone: string, code: string) =>
    request<{ access_token: string; user_id: string; is_new_user: boolean }>('/auth/verify-otp', {
      method: 'POST', body: JSON.stringify({ phone, code }),
    }),

  // Users
  getMe: () => request<User>('/users/me'),
  updateMe: (data: { name?: string; status_text?: string }) =>
    request<User>('/users/me', { method: 'PATCH', body: JSON.stringify(data) }),
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<User>('/users/me/avatar', { method: 'POST', body: form });
  },
  getUser: (id: string) => request<User>(`/users/${id}`),
  searchUsers: (q: string) => request<User[]>(`/users/search/?q=${encodeURIComponent(q)}`),

  // Messages
  getConversations: () => request<Conversation[]>('/messages/conversations'),
  getMessages: (userId: string, limit = 50, before?: string) =>
    request<Message[]>(`/messages/${userId}?limit=${limit}${before ? `&before=${before}` : ''}`),
  markStatus: (messageIds: string[], status: string) =>
    request('/messages/status', { method: 'PATCH', body: JSON.stringify({ message_ids: messageIds, status }) }),
  sendVoice: (receiverId: string, file: Blob, ext = 'webm') => {
    const form = new FormData();
    form.append('file', file, `voice.${ext}`);
    return request<Message>(`/messages/voice/${receiverId}`, { method: 'POST', body: form });
  },
  sendMedia: (receiverId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<Message>(`/messages/media/${receiverId}`, { method: 'POST', body: form });
  },
  replyToMessage: (messageId: string, receiverId: string, content: string) =>
    request<Message>(`/messages/reply/${messageId}?receiver_id=${receiverId}&content=${encodeURIComponent(content)}`, { method: 'POST' }),
  forwardMessage: (messageId: string, receiverId: string) =>
    request<Message>(`/messages/forward/${messageId}?receiver_id=${receiverId}`, { method: 'POST' }),
  deleteMessage: (messageId: string, forAll = false) =>
    request(`/messages/${messageId}?for_all=${forAll}`, { method: 'DELETE' }),
  pinMessage: (messageId: string) =>
    request(`/messages/${messageId}/pin`, { method: 'POST' }),
  unpinMessage: (messageId: string) =>
    request(`/messages/${messageId}/pin`, { method: 'DELETE' }),
  getReadReceipts: (messageId: string) =>
    request<ReadReceipt[]>(`/messages/${messageId}/receipts`),

  // Contacts
  syncContacts: (phones: string[]) =>
    request<{ registered: User[]; not_found: string[] }>('/contacts/sync', {
      method: 'POST', body: JSON.stringify({ phone_numbers: phones }),
    }),
  getContacts: () => request<User[]>('/contacts/'),
  removeContact: (userId: string) => request(`/contacts/${userId}`, { method: 'DELETE' }),

  // Groups
  createGroup: (name: string, description: string, memberIds: string[]) =>
    request<Group>('/groups/', {
      method: 'POST', body: JSON.stringify({ name, description, member_ids: memberIds }),
    }),
  getMyGroups: () => request<Group[]>('/groups/'),
  getGroup: (id: string) => request<Group>(`/groups/${id}`),
  updateGroup: (id: string, data: { name?: string; description?: string }) =>
    request<Group>(`/groups/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getGroupMembers: (id: string) => request<GroupMember[]>(`/groups/${id}/members`),
  addGroupMember: (groupId: string, userId: string) =>
    request(`/groups/${groupId}/members/${userId}`, { method: 'POST' }),
  removeGroupMember: (groupId: string, userId: string) =>
    request(`/groups/${groupId}/members/${userId}`, { method: 'DELETE' }),
  leaveGroup: (id: string) => request(`/groups/${id}/leave`, { method: 'POST' }),
  getGroupMessages: (id: string, limit = 50) =>
    request<Message[]>(`/groups/${id}/messages?limit=${limit}`),
  getGroupPinned: (id: string) => request<Message[]>(`/groups/${id}/pinned`),

  // Channels
  createChannel: (name: string, username: string, description: string, isPublic: boolean) =>
    request<Channel>('/channels/', {
      method: 'POST', body: JSON.stringify({ name, username, description, is_public: isPublic }),
    }),
  getMyChannels: () => request<Channel[]>('/channels/'),
  exploreChannels: (q = '') => request<Channel[]>(`/channels/explore?q=${encodeURIComponent(q)}`),
  subscribeChannel: (id: string) => request(`/channels/${id}/subscribe`, { method: 'POST' }),
  unsubscribeChannel: (id: string) => request(`/channels/${id}/subscribe`, { method: 'DELETE' }),
  createPost: (channelId: string, content: string) =>
    request(`/channels/${channelId}/post`, { method: 'POST', body: JSON.stringify({ content }) }),
  getChannelPosts: (id: string) => request<Message[]>(`/channels/${id}/posts`),

  // Stories
  createTextStory: (text: string, bgColor: string) =>
    request<StoryItem>('/stories/text', { method: 'POST', body: JSON.stringify({ text_content: text, bg_color: bgColor }) }),
  createMediaStory: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<StoryItem>('/stories/media', { method: 'POST', body: form });
  },
  getStoryFeed: () => request<StoryGroup[]>('/stories/feed'),
  viewStory: (id: string) => request(`/stories/${id}/view`, { method: 'POST' }),
  getStoryViewers: (id: string) => request<StoryViewer[]>(`/stories/${id}/viewers`),
  deleteStory: (id: string) => request(`/stories/${id}`, { method: 'DELETE' }),

  // Calls
  initiateCall: (calleeId: string, callType: 'voice' | 'video') =>
    request<CallRecord>('/calls/initiate', { method: 'POST', body: JSON.stringify({ callee_id: calleeId, call_type: callType }) }),
  answerCall: (id: string) => request(`/calls/${id}/answer`, { method: 'POST' }),
  declineCall: (id: string) => request(`/calls/${id}/decline`, { method: 'POST' }),
  endCall: (id: string) => request(`/calls/${id}/end`, { method: 'POST' }),
  sendOffer: (callId: string, sdp: string) =>
    request('/calls/signal/offer', { method: 'POST', body: JSON.stringify({ call_id: callId, sdp }) }),
  sendAnswer: (callId: string, sdp: string) =>
    request('/calls/signal/answer', { method: 'POST', body: JSON.stringify({ call_id: callId, sdp, type: 'answer' }) }),
  sendICE: (callId: string, candidate: string) =>
    request('/calls/signal/ice', { method: 'POST', body: JSON.stringify({ call_id: callId, candidate }) }),
  getCallHistory: () => request<CallRecord[]>('/calls/history'),

  // Security
  enable2FA: () => request<{ secret: string; otpauth_url: string }>('/security/2fa/enable', { method: 'POST' }),
  verify2FA: (code: string) => request('/security/2fa/verify', { method: 'POST', body: JSON.stringify({ code }) }),
  disable2FA: (code: string) => request('/security/2fa/disable', { method: 'POST', body: JSON.stringify({ code }) }),
  uploadPublicKey: (key: string) =>
    request('/security/keys/upload', { method: 'POST', body: JSON.stringify({ public_key: key }) }),
  getPublicKey: (userId: string) => request<{ user_id: string; public_key: string }>(`/security/keys/${userId}`),

  // Translation
  getLanguages: () => request<Language[]>('/translation/languages'),
  setLanguage: (language: string) =>
    request('/translation/set-language', { method: 'POST', body: JSON.stringify({ language }) }),
  translateText: (text: string, source: string, target: string) =>
    request<{ translated_text: string; source_language: string; target_language: string; confidence: number }>(
      '/translation/translate', { method: 'POST', body: JSON.stringify({ text, source, target }) }),
  getOriginalMessage: (messageId: string) =>
    request<{ message_id: string; original_content: string; translated_content: string; source_language: string; was_translated: boolean }>(
      `/translation/message/${messageId}/original`),
};

// ── Types ──

export interface User {
  id: string; phone: string; name: string; avatar_url: string | null;
  status_text: string; preferred_language: string; is_online: boolean; last_seen: string | null;
  two_fa_enabled?: boolean;
}

export interface Language {
  code: string; name: string;
}

export interface Message {
  id: string; sender_id: string; receiver_id: string | null;
  group_id: string | null; channel_id: string | null;
  content: string | null; original_content: string | null;
  source_language: string | null; translated: boolean;
  message_type: string;
  media_url: string | null; media_name: string | null; media_size: number | null;
  status: 'sent' | 'delivered' | 'seen';
  reply_to_id: string | null; is_forwarded: boolean; is_pinned: boolean;
  deleted_for_all: boolean; created_at: string; edited_at: string | null;
}

export interface Conversation {
  user: User; last_message: Message | null; unread_count: number;
}

export interface ReadReceipt {
  user_id: string; name: string; avatar_url: string | null; read_at: string;
}

export interface Group {
  id: string; name: string; description: string; avatar_url: string | null;
  creator_id: string; member_count: number;
}

export interface GroupMember {
  user_id: string; name: string; phone: string; avatar_url: string | null;
  role: string; is_online: boolean;
}

export interface Channel {
  id: string; name: string; username: string | null; description: string;
  avatar_url: string | null; is_public: boolean; subscriber_count: number;
  creator_id: string; is_admin?: boolean;
}

export interface StoryItem {
  id: string; user_id: string; story_type: string;
  media_url: string | null; text_content: string | null; bg_color: string | null;
  view_count: number; created_at: string; expires_at: string; is_viewed: boolean;
}

export interface StoryGroup {
  user_id: string; name: string; avatar_url: string | null;
  stories: StoryItem[]; has_unviewed: boolean;
}

export interface StoryViewer {
  user_id: string; name: string; avatar_url: string | null; viewed_at: string;
}

export interface CallRecord {
  id: string; caller_id: string; callee_id: string; call_type: string;
  status: string; duration_seconds: number | null; started_at: string; ended_at: string | null;
}
