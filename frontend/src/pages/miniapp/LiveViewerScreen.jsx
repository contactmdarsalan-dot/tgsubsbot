import { useState, useEffect, useRef } from "react";
import { useMiniApp, API } from "./context";
import { Radio, Eye, Send, MessageCircle, Loader2 } from "lucide-react";

export default function LiveViewerScreen() {
  const { userId, tenantId } = useMiniApp();
  const [liveSession, setLiveSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewerCount, setViewerCount] = useState(0);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isWatching, setIsWatching] = useState(false);

  const videoRef = useRef(null);
  const wsRef = useRef(null);
  const pcRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    checkLive();
    return () => cleanup();
  }, [tenantId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const checkLive = async () => {
    setLoading(true);
    try {
      const tParam = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetch(`${API}/miniapp/active-live${tParam}`);
      const data = await res.json();
      if (data && data.id) {
        setLiveSession(data);
        setViewerCount(data.viewer_count || 0);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const joinLive = async () => {
    if (!liveSession) return;
    setIsWatching(true);

    const wsUrl = `${API.replace("https://", "wss://").replace("http://", "ws://").replace("/api", "")}/api/ws/live/${liveSession.id}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    const config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
    const pc = new RTCPeerConnection(config);
    pcRef.current = pc;

    pc.ontrack = (e) => {
      if (videoRef.current) videoRef.current.srcObject = e.streams[0];
    };

    pc.onicecandidate = (e) => {
      if (e.candidate && ws.readyState === 1) {
        ws.send(JSON.stringify({ type: "ice-candidate", candidate: e.candidate, target: liveSession.started_by }));
      }
    };

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "viewer-join" }));
    };

    ws.onmessage = async (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "offer") {
        await pc.setRemoteDescription({ type: "offer", sdp: msg.sdp });
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: "answer", sdp: answer.sdp, target: msg.from }));
      } else if (msg.type === "ice-candidate" && msg.candidate) {
        await pc.addIceCandidate(msg.candidate);
      } else if (msg.type === "viewer-ready") {
        setViewerCount(msg.viewerCount || 0);
      } else if (msg.type === "chat") {
        setChatMessages(prev => [...prev, msg]);
      } else if (msg.type === "broadcaster-left") {
        setIsWatching(false);
        setLiveSession(null);
      }
    };
  };

  const sendChat = () => {
    if (!chatInput.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "chat", text: chatInput.trim(), name: `User ${userId?.slice(-4) || ""}` }));
    setChatInput("");
  };

  const cleanup = () => {
    if (pcRef.current) pcRef.current.close();
    if (wsRef.current) wsRef.current.close();
  };

  if (loading) {
    return <div className="py-12 text-center"><Loader2 className="w-6 h-6 animate-spin text-rose-400 mx-auto" /></div>;
  }

  if (!liveSession) {
    return (
      <div className="pb-24" data-testid="live-screen-empty">
        <h2 className="font-heading text-xl font-bold text-white mb-4 flex items-center gap-2">
          <Radio className="w-5 h-5 text-rose-400" /> Live
        </h2>
        <div className="glass-card rounded-2xl p-8 text-center">
          <Radio className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">No live stream right now</p>
          <p className="text-zinc-600 text-xs mt-1">Check back later when the creator goes live</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-24" data-testid="live-viewer-screen">
      <h2 className="font-heading text-xl font-bold text-white mb-4 flex items-center gap-2">
        <Radio className="w-5 h-5 text-rose-400 animate-pulse" /> LIVE
      </h2>

      {/* Video Area */}
      <div className="rounded-xl overflow-hidden bg-black aspect-video mb-3 relative">
        {isWatching ? (
          <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <button onClick={joinLive} className="gradient-cta text-white font-bold rounded-2xl px-6 py-3 flex items-center gap-2 active:scale-95 transition-transform" data-testid="join-live-btn">
              <Radio className="w-5 h-5" /> Watch Live
            </button>
          </div>
        )}
        <div className="absolute top-2 left-2 bg-rose-600 px-2 py-0.5 rounded-full flex items-center gap-1">
          <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
          <span className="text-[10px] text-white font-bold">LIVE</span>
        </div>
        <div className="absolute top-2 right-2 bg-black/60 px-2 py-0.5 rounded-full flex items-center gap-1">
          <Eye className="w-3 h-3 text-white" />
          <span className="text-[10px] text-white">{viewerCount}</span>
        </div>
      </div>

      {/* Info */}
      <div className="glass-card rounded-xl p-3 mb-3">
        <p className="text-sm font-semibold text-white">{liveSession.title}</p>
        {liveSession.description && <p className="text-xs text-zinc-400 mt-1">{liveSession.description}</p>}
        <p className="text-xs text-zinc-500 mt-1">by {liveSession.started_by_name || "Creator"}</p>
      </div>

      {/* Live Chat */}
      {isWatching && (
        <div className="glass-card rounded-xl p-3">
          <p className="text-xs font-semibold text-zinc-400 mb-2 flex items-center gap-1"><MessageCircle className="w-3 h-3" /> Live Chat</p>
          <div className="max-h-32 overflow-y-auto space-y-1 mb-2">
            {chatMessages.map((m, i) => (
              <div key={i} className="text-xs"><span className="text-rose-400 font-semibold">{m.name}: </span><span className="text-white">{m.text}</span></div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div className="flex items-center gap-2">
            <input value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendChat()} placeholder="Say something..." className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none placeholder-zinc-600" data-testid="live-chat-input" />
            <button onClick={sendChat} className="w-7 h-7 rounded-lg gradient-cta flex items-center justify-center" data-testid="live-chat-send">
              <Send className="w-3 h-3 text-white" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
