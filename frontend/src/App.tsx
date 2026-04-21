import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './stores/auth';
import { BottomNav } from './components/BottomNav';
import { CallOverlay } from './components/CallOverlay';
import { LoginPage } from './pages/LoginPage';
import { ChatsPage } from './pages/ChatsPage';
import { ChatRoom } from './pages/ChatRoom';
import { SavedMessagesPage } from './pages/SavedMessagesPage';
import { ArchivedChatsPage } from './pages/ArchivedChatsPage';
import { ContactsPage } from './pages/ContactsPage';
import { ProfilePage } from './pages/ProfilePage';
import { GroupsPage } from './pages/GroupsPage';
import { GroupChatRoom } from './pages/GroupChatRoom';
import { ChannelsPage } from './pages/ChannelsPage';
import { StoriesPage } from './pages/StoriesPage';
import { CallsPage } from './pages/CallsPage';

function AppRoutes() {
  const { token, user, loading, loadUser } = useAuth();

  useEffect(() => {
    if (token) loadUser();
    else useAuth.setState({ loading: false });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#6C5CE7] to-[#A29BFE] flex items-center justify-center">
            <span className="text-white text-2xl font-bold">N</span>
          </div>
          <div className="animate-spin w-6 h-6 border-2 border-[var(--nexly-sent)] border-t-transparent rounded-full" />
        </div>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="max-w-lg mx-auto bg-[var(--nexly-surface)] min-h-screen relative">
      <CallOverlay />
      <Routes>
        <Route path="/chats" element={<ChatsPage />} />
        <Route path="/chat/:userId" element={<ChatRoom />} />
        <Route path="/saved" element={<SavedMessagesPage />} />
        <Route path="/archived" element={<ArchivedChatsPage />} />
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/group/:groupId" element={<GroupChatRoom />} />
        <Route path="/channels" element={<ChannelsPage />} />
        <Route path="/stories" element={<StoriesPage />} />
        <Route path="/calls" element={<CallsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<Navigate to="/chats" replace />} />
      </Routes>
      <BottomNav />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
