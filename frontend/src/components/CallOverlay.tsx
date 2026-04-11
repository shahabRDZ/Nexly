import { useEffect, useState, useRef } from 'react';
import { Phone, PhoneOff, Video, Mic, MicOff, VideoOff } from 'lucide-react';
import { socket } from '../lib/ws';
import { api } from '../lib/api';
import { Avatar } from './Avatar';

interface IncomingCall {
  call_id: string;
  caller_id: string;
  caller_name: string;
  caller_avatar: string | null;
  call_type: 'voice' | 'video';
}

export function CallOverlay() {
  const [incoming, setIncoming] = useState<IncomingCall | null>(null);
  const [activeCall, setActiveCall] = useState<{ id: string; type: string; remoteName: string; remoteAvatar: string | null } | null>(null);
  const [callDuration, setCallDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [videoOff, setVideoOff] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const localStream = useRef<MediaStream | null>(null);
  const pc = useRef<RTCPeerConnection | null>(null);

  useEffect(() => {
    const unsubs = [
      socket.on('call_incoming', (data: IncomingCall) => setIncoming(data)),
      socket.on('call_answered', async (data: { call_id: string }) => {
        setIncoming(null);
        // Start WebRTC connection
        await setupWebRTC(data.call_id);
      }),
      socket.on('call_declined', () => { cleanup(); }),
      socket.on('call_ended', () => { cleanup(); }),
      socket.on('webrtc_offer', async (data: any) => {
        if (pc.current) {
          await pc.current.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp: data.sdp }));
          const answer = await pc.current.createAnswer();
          await pc.current.setLocalDescription(answer);
          socket.send('webrtc_answer', { target_id: data.from_user_id, call_id: data.call_id, sdp: answer.sdp });
        }
      }),
      socket.on('webrtc_answer', async (data: any) => {
        if (pc.current) {
          await pc.current.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: data.sdp }));
        }
      }),
      socket.on('webrtc_ice', async (data: any) => {
        if (pc.current && data.candidate) {
          await pc.current.addIceCandidate(new RTCIceCandidate({ candidate: data.candidate, sdpMid: data.sdp_mid }));
        }
      }),
    ];
    return () => unsubs.forEach((fn) => fn());
  }, []);

  useEffect(() => {
    if (activeCall) {
      timerRef.current = setInterval(() => setCallDuration((d) => d + 1), 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [activeCall]);

  const setupWebRTC = async (callId: string) => {
    const isVideo = activeCall?.type === 'video';
    localStream.current = await navigator.mediaDevices.getUserMedia({ audio: true, video: isVideo });

    pc.current = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    localStream.current.getTracks().forEach((t) => pc.current!.addTrack(t, localStream.current!));

    pc.current.onicecandidate = (e) => {
      if (e.candidate) {
        socket.send('webrtc_ice', { target_id: activeCall?.id, call_id: callId, candidate: e.candidate.candidate, sdp_mid: e.candidate.sdpMid });
      }
    };
  };

  const answerCall = async () => {
    if (!incoming) return;
    await api.answerCall(incoming.call_id);
    setActiveCall({ id: incoming.call_id, type: incoming.call_type, remoteName: incoming.caller_name, remoteAvatar: incoming.caller_avatar });
    setIncoming(null);
    setCallDuration(0);
  };

  const declineCall = async () => {
    if (incoming) await api.declineCall(incoming.call_id);
    setIncoming(null);
  };

  const endCall = async () => {
    if (activeCall) await api.endCall(activeCall.id);
    cleanup();
  };

  const cleanup = () => {
    localStream.current?.getTracks().forEach((t) => t.stop());
    pc.current?.close();
    pc.current = null;
    setActiveCall(null);
    setIncoming(null);
    setCallDuration(0);
    clearInterval(timerRef.current);
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  // Incoming call
  if (incoming) {
    return (
      <div className="fixed inset-0 bg-gradient-to-b from-[#1a1a2e] to-[#16213e] z-[100] flex flex-col items-center justify-center">
        <div className="animate-pulse mb-6">
          <Avatar src={incoming.caller_avatar} name={incoming.caller_name} size={96} />
        </div>
        <h2 className="text-white text-2xl font-bold mb-1">{incoming.caller_name}</h2>
        <p className="text-white/60 mb-12">Incoming {incoming.call_type} call...</p>
        <div className="flex gap-16">
          <button onClick={declineCall} className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center shadow-lg">
            <PhoneOff size={28} className="text-white" />
          </button>
          <button onClick={answerCall} className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center shadow-lg animate-bounce">
            {incoming.call_type === 'video' ? <Video size={28} className="text-white" /> : <Phone size={28} className="text-white" />}
          </button>
        </div>
      </div>
    );
  }

  // Active call
  if (activeCall) {
    return (
      <div className="fixed inset-0 bg-gradient-to-b from-[#1a1a2e] to-[#16213e] z-[100] flex flex-col items-center justify-center">
        <Avatar src={activeCall.remoteAvatar} name={activeCall.remoteName} size={96} />
        <h2 className="text-white text-2xl font-bold mt-4 mb-1">{activeCall.remoteName}</h2>
        <p className="text-white/60 text-lg mb-12">{formatTime(callDuration)}</p>
        <div className="flex gap-8">
          <button onClick={() => setMuted(!muted)}
            className={`w-14 h-14 rounded-full flex items-center justify-center ${muted ? 'bg-white/20' : 'bg-white/10'}`}>
            {muted ? <MicOff size={24} className="text-red-400" /> : <Mic size={24} className="text-white" />}
          </button>
          {activeCall.type === 'video' && (
            <button onClick={() => setVideoOff(!videoOff)}
              className={`w-14 h-14 rounded-full flex items-center justify-center ${videoOff ? 'bg-white/20' : 'bg-white/10'}`}>
              {videoOff ? <VideoOff size={24} className="text-red-400" /> : <Video size={24} className="text-white" />}
            </button>
          )}
          <button onClick={endCall} className="w-14 h-14 rounded-full bg-red-500 flex items-center justify-center">
            <PhoneOff size={24} className="text-white" />
          </button>
        </div>
      </div>
    );
  }

  return null;
}
