import { useState, useEffect } from "react";
import { useMiniApp, API } from "./context";
import { Video, Calendar, Clock, CheckCircle, XCircle, PhoneCall, Loader2 } from "lucide-react";

export default function BookingsScreen() {
  const { userId, tenantId } = useMiniApp();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeCallRoom, setActiveCallRoom] = useState(null);

  useEffect(() => {
    fetchBookings();
  }, [userId, tenantId]);

  const fetchBookings = async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const tParam = tenantId ? `&tenant_id=${tenantId}` : "";
      const res = await fetch(`${API}/miniapp/my-bookings/${userId}?${tParam}`);
      setBookings(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const statusColors = {
    pending: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Pending" },
    scheduled: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Scheduled" },
    in_call: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "In Call" },
    completed: { bg: "bg-zinc-500/15", text: "text-zinc-400", label: "Completed" },
    rejected: { bg: "bg-lime-500/15", text: "text-lime-400", label: "Rejected" },
  };

  const joinCall = (booking) => {
    setActiveCallRoom(booking.room_id);
  };

  if (activeCallRoom) {
    return <VideoCallRoom roomId={activeCallRoom} onBack={() => { setActiveCallRoom(null); fetchBookings(); }} />;
  }

  return (
    <div className="pb-24" data-testid="bookings-screen">
      <h2 className="font-heading text-xl font-bold text-white mb-4 flex items-center gap-2">
        <Video className="w-5 h-5 text-lime-400" /> My Video Calls
      </h2>

      {loading ? (
        <div className="glass-card rounded-2xl p-8 text-center"><Loader2 className="w-6 h-6 animate-spin text-lime-400 mx-auto" /></div>
      ) : bookings.length === 0 ? (
        <div className="glass-card rounded-2xl p-8 text-center">
          <Video className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">No video call bookings yet</p>
          <p className="text-zinc-600 text-xs mt-1">Purchase a video call plan to book a call</p>
        </div>
      ) : (
        <div className="space-y-3">
          {bookings.map(b => {
            const st = statusColors[b.status] || statusColors.pending;
            return (
              <div key={b.id} className="glass-card rounded-xl p-4" data-testid={`booking-${b.id}`}>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-sm font-semibold text-white">{b.plan_name || b.title}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">{b.call_duration_minutes} min call</p>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${st.bg} ${st.text}`}>{st.label}</span>
                </div>

                {b.scheduled_date && (
                  <div className="flex items-center gap-4 text-xs text-zinc-400 mb-2">
                    <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {b.scheduled_date}</span>
                    {b.scheduled_time && <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {b.scheduled_time}</span>}
                  </div>
                )}

                {(b.status === "scheduled" || b.status === "in_call") && (
                  <button onClick={() => joinCall(b)} className="gradient-cta text-white text-xs font-bold rounded-xl py-2 px-4 w-full mt-2 flex items-center justify-center gap-1.5 active:scale-95 transition-transform" data-testid="join-call-btn">
                    <PhoneCall className="w-3.5 h-3.5" /> {b.status === "in_call" ? "Join Call Now" : "Join When Ready"}
                  </button>
                )}

                <p className="text-[10px] text-zinc-600 mt-2">{new Date(b.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


// ============== VIDEO CALL ROOM ==============
function VideoCallRoom({ roomId, onBack }) {
  const { userId } = useMiniApp();
  const [localStream, setLocalStream] = useState(null);
  const [remoteStream, setRemoteStream] = useState(null);
  const [connected, setConnected] = useState(false);
  const [muted, setMuted] = useState(false);
  const [videoOff, setVideoOff] = useState(false);
  const [callTime, setCallTime] = useState(0);
  const [status, setStatus] = useState("connecting");

  const wsRef = { current: null };
  const pcRef = { current: null };
  const localVideoRef = { current: null };
  const remoteVideoRef = { current: null };
  const timerRef = { current: null };

  useEffect(() => {
    startCall();
    return () => { endCall(); };
  }, []);

  useEffect(() => {
    if (connected) {
      timerRef.current = setInterval(() => setCallTime(t => t + 1), 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [connected]);

  const startCall = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setLocalStream(stream);
      if (localVideoRef.current) localVideoRef.current.srcObject = stream;

      const wsUrl = `${API.replace("https://", "wss://").replace("http://", "ws://").replace("/api", "")}/api/ws/call/${roomId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      const config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }, { urls: "stun:stun1.l.google.com:19302" }] };
      const pc = new RTCPeerConnection(config);
      pcRef.current = pc;

      stream.getTracks().forEach(t => pc.addTrack(t, stream));

      pc.ontrack = (e) => {
        setRemoteStream(e.streams[0]);
        if (remoteVideoRef.current) remoteVideoRef.current.srcObject = e.streams[0];
        setConnected(true);
        setStatus("connected");
      };

      pc.onicecandidate = (e) => {
        if (e.candidate && ws.readyState === 1) {
          ws.send(JSON.stringify({ type: "ice-candidate", candidate: e.candidate }));
        }
      };

      ws.onopen = () => setStatus("waiting");

      ws.onmessage = async (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "user-joined") {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          ws.send(JSON.stringify({ type: "offer", sdp: offer.sdp }));
        } else if (msg.type === "offer") {
          await pc.setRemoteDescription({ type: "offer", sdp: msg.sdp });
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          ws.send(JSON.stringify({ type: "answer", sdp: answer.sdp }));
        } else if (msg.type === "answer") {
          await pc.setRemoteDescription({ type: "answer", sdp: msg.sdp });
        } else if (msg.type === "ice-candidate" && msg.candidate) {
          await pc.addIceCandidate(msg.candidate);
        } else if (msg.type === "user-left") {
          setConnected(false);
          setStatus("ended");
        }
      };
    } catch (err) {
      console.error("Call error:", err);
      setStatus("error");
    }
  };

  const endCall = () => {
    if (localStream) localStream.getTracks().forEach(t => t.stop());
    if (pcRef.current) pcRef.current.close();
    if (wsRef.current) wsRef.current.close();
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const toggleMute = () => {
    if (localStream) {
      localStream.getAudioTracks().forEach(t => { t.enabled = !t.enabled; });
      setMuted(!muted);
    }
  };

  const toggleVideo = () => {
    if (localStream) {
      localStream.getVideoTracks().forEach(t => { t.enabled = !t.enabled; });
      setVideoOff(!videoOff);
    }
  };

  const formatTime = (s) => `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: "hsl(0,0%,2%)" }} data-testid="video-call-room">
      {/* Remote Video (Full Screen) */}
      <div className="flex-1 relative">
        {remoteStream ? (
          <video ref={el => { remoteVideoRef.current = el; if (el) el.srcObject = remoteStream; }} autoPlay playsInline className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-4">
                <Video className="w-8 h-8 text-zinc-600" />
              </div>
              <p className="text-zinc-400 text-sm">{status === "waiting" ? "Waiting for creator to join..." : status === "connecting" ? "Connecting..." : status === "ended" ? "Call ended" : "Camera error"}</p>
            </div>
          </div>
        )}

        {/* Local Video (PiP) */}
        <div className="absolute top-4 right-4 w-28 h-36 rounded-xl overflow-hidden border-2 border-white/20 bg-zinc-900">
          <video ref={el => { localVideoRef.current = el; if (el && localStream) el.srcObject = localStream; }} autoPlay playsInline muted className="w-full h-full object-cover" />
        </div>

        {/* Call Timer */}
        {connected && (
          <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full">
            <span className="text-white text-xs font-mono">{formatTime(callTime)}</span>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="p-4 flex items-center justify-center gap-4" style={{ background: "hsla(340,50%,4%,0.95)" }}>
        <button onClick={toggleMute} className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${muted ? "bg-lime-500" : "bg-zinc-700"}`} data-testid="mute-btn">
          {muted ? <span className="text-white text-xs">UN</span> : <span className="text-white text-xs">MIC</span>}
        </button>
        <button onClick={() => { endCall(); onBack(); }} className="w-14 h-14 rounded-full bg-lime-600 flex items-center justify-center active:scale-90 transition-transform" data-testid="end-call-btn">
          <PhoneCall className="w-6 h-6 text-white rotate-[135deg]" />
        </button>
        <button onClick={toggleVideo} className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${videoOff ? "bg-lime-500" : "bg-zinc-700"}`} data-testid="video-toggle-btn">
          <Video className="w-5 h-5 text-white" />
        </button>
      </div>
    </div>
  );
}
