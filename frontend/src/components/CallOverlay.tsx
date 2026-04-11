import { useEffect, useState, useRef, useCallback } from 'react';
import { Phone, PhoneOff, Video, Mic, MicOff, VideoOff } from 'lucide-react';
import { socket } from '../lib/ws';
import { api } from '../lib/api';
import { Avatar } from './Avatar';

interface CallState {
  callId: string;
  remoteUserId: string;
  remoteName: string;
  remoteAvatar: string | null;
  callType: 'voice' | 'video';
  direction: 'incoming' | 'outgoing';
  status: 'ringing' | 'connecting' | 'active';
}

export function CallOverlay() {
  const [call, setCall] = useState<CallState | null>(null);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [camOff, setCamOff] = useState(false);

  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const remoteAudioRef = useRef<HTMLAudioElement>(null);
  const pendingCandidates = useRef<RTCIceCandidateInit[]>([]);

  // ── Create RTCPeerConnection ──
  const createPC = useCallback((remoteUserId: string, callId: string) => {
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ],
    });

    pc.onicecandidate = (e) => {
      if (e.candidate) {
        socket.send('webrtc_ice', {
          target_id: remoteUserId,
          call_id: callId,
          candidate: e.candidate.candidate,
          sdp_mid: e.candidate.sdpMid,
          sdp_m_line_index: e.candidate.sdpMLineIndex,
        });
      }
    };

    pc.ontrack = (e) => {
      const [stream] = e.streams;
      if (e.track.kind === 'video' && remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = stream;
      } else if (e.track.kind === 'audio' && remoteAudioRef.current) {
        remoteAudioRef.current.srcObject = stream;
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'connected') {
        setCall((prev) => prev ? { ...prev, status: 'active' } : prev);
      } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
        endCall();
      }
    };

    pcRef.current = pc;
    return pc;
  }, []);

  // ── Get media stream ──
  const getMedia = useCallback(async (callType: 'voice' | 'video') => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: callType === 'video',
    });
    localStreamRef.current = stream;
    if (callType === 'video' && localVideoRef.current) {
      localVideoRef.current.srcObject = stream;
    }
    return stream;
  }, []);

  // ── WebSocket event handlers ──
  useEffect(() => {
    // Incoming call from another user
    const onIncoming = (data: any) => {
      setCall({
        callId: data.call_id,
        remoteUserId: data.caller_id,
        remoteName: data.caller_name,
        remoteAvatar: data.caller_avatar,
        callType: data.call_type,
        direction: 'incoming',
        status: 'ringing',
      });
    };

    // Our outgoing call was answered
    const onAnswered = async (data: any) => {
      setCall((prev) => prev ? { ...prev, status: 'connecting' } : prev);

      // Caller creates offer
      const currentCall = call;
      if (!currentCall) return;

      try {
        const stream = await getMedia(currentCall.callType);
        const pc = createPC(currentCall.remoteUserId, currentCall.callId);
        stream.getTracks().forEach((t) => pc.addTrack(t, stream));

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        socket.send('webrtc_offer', {
          target_id: currentCall.remoteUserId,
          call_id: currentCall.callId,
          sdp: offer.sdp,
          type: 'offer',
        });
      } catch (err) {
        console.error('Failed to create offer:', err);
        endCall();
      }
    };

    // Receive WebRTC offer (callee side)
    const onOffer = async (data: any) => {
      const pc = pcRef.current;
      if (!pc) return;

      try {
        await pc.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp: data.sdp }));

        // Flush pending ICE candidates
        for (const candidate of pendingCandidates.current) {
          await pc.addIceCandidate(new RTCIceCandidate(candidate));
        }
        pendingCandidates.current = [];

        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        socket.send('webrtc_answer', {
          target_id: data.from_user_id,
          call_id: data.call_id,
          sdp: answer.sdp,
          type: 'answer',
        });
      } catch (err) {
        console.error('Failed to handle offer:', err);
      }
    };

    // Receive WebRTC answer (caller side)
    const onAnswer = async (data: any) => {
      const pc = pcRef.current;
      if (!pc) return;
      try {
        await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: data.sdp }));
        // Flush pending ICE candidates
        for (const candidate of pendingCandidates.current) {
          await pc.addIceCandidate(new RTCIceCandidate(candidate));
        }
        pendingCandidates.current = [];
      } catch (err) {
        console.error('Failed to handle answer:', err);
      }
    };

    // Receive ICE candidate
    const onICE = async (data: any) => {
      if (!data.candidate) return;
      const candidate: RTCIceCandidateInit = {
        candidate: data.candidate,
        sdpMid: data.sdp_mid,
        sdpMLineIndex: data.sdp_m_line_index,
      };
      const pc = pcRef.current;
      if (pc && pc.remoteDescription) {
        try { await pc.addIceCandidate(new RTCIceCandidate(candidate)); } catch {}
      } else {
        pendingCandidates.current.push(candidate);
      }
    };

    const onDeclined = () => cleanup();
    const onEnded = () => cleanup();

    // Outgoing call from ChatRoom
    const onOutgoing = (e: Event) => {
      const d = (e as CustomEvent).detail;
      setCall({
        callId: d.call_id,
        remoteUserId: d.callee_id,
        remoteName: d.callee_name,
        remoteAvatar: d.callee_avatar,
        callType: d.call_type,
        direction: 'outgoing',
        status: 'ringing',
      });
    };

    const unsubs = [
      socket.on('call_incoming', onIncoming),
      socket.on('call_answered', onAnswered),
      socket.on('call_declined', onDeclined),
      socket.on('call_ended', onEnded),
      socket.on('webrtc_offer', onOffer),
      socket.on('webrtc_answer', onAnswer),
      socket.on('webrtc_ice', onICE),
    ];

    window.addEventListener('nexly:call_outgoing', onOutgoing);
    return () => {
      unsubs.forEach((fn) => fn());
      window.removeEventListener('nexly:call_outgoing', onOutgoing);
    };
  }, [call, createPC, getMedia]);

  // Duration timer
  useEffect(() => {
    if (call?.status === 'active') {
      setDuration(0);
      timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [call?.status]);

  // ── Actions ──
  const answerCall = async () => {
    if (!call) return;
    try {
      await api.answerCall(call.callId);
      setCall((prev) => prev ? { ...prev, status: 'connecting' } : prev);

      const stream = await getMedia(call.callType);
      const pc = createPC(call.remoteUserId, call.callId);
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));
    } catch (err) {
      console.error('Answer failed:', err);
      cleanup();
    }
  };

  const declineCall = async () => {
    if (call) await api.declineCall(call.callId);
    cleanup();
  };

  const endCall = async () => {
    if (call) {
      try { await api.endCall(call.callId); } catch {}
    }
    cleanup();
  };

  const cleanup = () => {
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
    localStreamRef.current = null;
    pcRef.current?.close();
    pcRef.current = null;
    pendingCandidates.current = [];
    setCall(null);
    setDuration(0);
    setMuted(false);
    setCamOff(false);
    clearInterval(timerRef.current);
  };

  const toggleMute = () => {
    const stream = localStreamRef.current;
    if (!stream) return;
    stream.getAudioTracks().forEach((t) => { t.enabled = muted; });
    setMuted(!muted);
  };

  const toggleCam = () => {
    const stream = localStreamRef.current;
    if (!stream) return;
    stream.getVideoTracks().forEach((t) => { t.enabled = camOff; });
    setCamOff(!camOff);
  };

  const fmtTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  if (!call) return null;

  // ── Ringing UI (incoming) ──
  if (call.status === 'ringing' && call.direction === 'incoming') {
    return (
      <div className="fixed inset-0 bg-gradient-to-b from-[#1a1a2e] to-[#16213e] z-[100] flex flex-col items-center justify-center">
        <div className="animate-pulse mb-6">
          <Avatar src={call.remoteAvatar} name={call.remoteName} size={96} />
        </div>
        <h2 className="text-white text-2xl font-bold mb-1">{call.remoteName}</h2>
        <p className="text-white/60 mb-12">Incoming {call.callType} call...</p>
        <div className="flex gap-16">
          <button onClick={declineCall} className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center shadow-lg">
            <PhoneOff size={28} className="text-white" />
          </button>
          <button onClick={answerCall} className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center shadow-lg animate-bounce">
            {call.callType === 'video' ? <Video size={28} className="text-white" /> : <Phone size={28} className="text-white" />}
          </button>
        </div>
      </div>
    );
  }

  // ── Ringing UI (outgoing) ──
  if (call.status === 'ringing' && call.direction === 'outgoing') {
    return (
      <div className="fixed inset-0 bg-gradient-to-b from-[#1a1a2e] to-[#16213e] z-[100] flex flex-col items-center justify-center">
        <Avatar src={call.remoteAvatar} name={call.remoteName} size={96} />
        <h2 className="text-white text-2xl font-bold mt-6 mb-1">{call.remoteName}</h2>
        <p className="text-white/60 mb-12">Calling...</p>
        <button onClick={endCall} className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center shadow-lg">
          <PhoneOff size={28} className="text-white" />
        </button>
      </div>
    );
  }

  // ── Active / Connecting Call UI ──
  return (
    <div className="fixed inset-0 bg-gradient-to-b from-[#1a1a2e] to-[#16213e] z-[100] flex flex-col">
      {/* Remote video (full screen background) */}
      {call.callType === 'video' && (
        <video ref={remoteVideoRef} autoPlay playsInline className="absolute inset-0 w-full h-full object-cover" />
      )}

      {/* Hidden audio element for voice calls */}
      <audio ref={remoteAudioRef} autoPlay playsInline />

      {/* Overlay content */}
      <div className="relative z-10 flex flex-col items-center justify-center flex-1">
        {/* Local video (small PiP) */}
        {call.callType === 'video' && (
          <video ref={localVideoRef} autoPlay playsInline muted
            className="absolute top-4 right-4 w-28 h-40 rounded-xl object-cover border-2 border-white/20" />
        )}

        {/* Avatar (voice call or connecting) */}
        {(call.callType === 'voice' || call.status === 'connecting') && (
          <Avatar src={call.remoteAvatar} name={call.remoteName} size={96} />
        )}

        <h2 className="text-white text-2xl font-bold mt-4 mb-1">{call.remoteName}</h2>
        <p className="text-white/60 text-lg">
          {call.status === 'connecting' ? 'Connecting...' : fmtTime(duration)}
        </p>
      </div>

      {/* Controls */}
      <div className="relative z-10 flex justify-center gap-6 pb-12">
        <button onClick={toggleMute}
          className={`w-14 h-14 rounded-full flex items-center justify-center ${muted ? 'bg-red-500/80' : 'bg-white/15'}`}>
          {muted ? <MicOff size={24} className="text-white" /> : <Mic size={24} className="text-white" />}
        </button>

        {call.callType === 'video' && (
          <button onClick={toggleCam}
            className={`w-14 h-14 rounded-full flex items-center justify-center ${camOff ? 'bg-red-500/80' : 'bg-white/15'}`}>
            {camOff ? <VideoOff size={24} className="text-white" /> : <Video size={24} className="text-white" />}
          </button>
        )}

        <button onClick={endCall} className="w-14 h-14 rounded-full bg-red-500 flex items-center justify-center">
          <PhoneOff size={24} className="text-white" />
        </button>
      </div>
    </div>
  );
}
