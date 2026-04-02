import { useState, useEffect, useRef } from "react";
import { useMiniApp, API } from "./context";
import { Send, ArrowLeft, Loader2, MessageCircle, User } from "lucide-react";

export default function PrivateChatScreen() {
  const { userId, tenantId } = useMiniApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    fetchHistory();
    connectWS();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, [userId, tenantId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchHistory = async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const tParam = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetch(`${API}/miniapp/chat/history/${userId}${tParam}`);
      setMessages(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const connectWS = () => {
    try {
      const wsUrl = `${API.replace("https://", "wss://").replace("http://", "ws://").replace("/api", "")}/api/ws/chat/user/${userId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "new-message") {
          setMessages(prev => [...prev, msg]);
        }
      };
    } catch (e) { console.error("WS error:", e); }
  };

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/miniapp/chat/send`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, message: input.trim(), tenant_id: tenantId }),
      });
      const data = await res.json();
      if (data.success) {
        setMessages(prev => [...prev, data.message]);
        setInput("");
      }
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  };

  return (
    <div className="pb-24 flex flex-col" style={{ minHeight: "calc(100vh - 120px)" }} data-testid="chat-screen">
      <h2 className="font-heading text-xl font-bold text-white mb-4 flex items-center gap-2">
        <MessageCircle className="w-5 h-5 text-lime-400" /> Chat with Creator
      </h2>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-2 mb-3" style={{ maxHeight: "calc(100vh - 240px)" }}>
        {loading ? (
          <div className="text-center py-8"><Loader2 className="w-5 h-5 animate-spin text-lime-400 mx-auto" /></div>
        ) : messages.length === 0 ? (
          <div className="text-center py-8">
            <MessageCircle className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-500 text-sm">Start a conversation with the creator</p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={m.id || i} className={`flex ${m.sender_type === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 ${m.sender_type === "user" ? "bg-lime-600/80 rounded-br-sm" : "bg-zinc-800 rounded-bl-sm"}`}>
                {m.sender_type === "admin" && <p className="text-[10px] text-lime-400 font-semibold mb-0.5">{m.sender_name || "Creator"}</p>}
                <p className="text-sm text-white break-words">{m.message}</p>
                <p className="text-[9px] text-white/40 mt-0.5 text-right">{m.created_at ? new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : ""}</p>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="fixed bottom-16 left-0 right-0 px-4 pb-2" style={{ background: "hsl(0, 0%, 2%)" }}>
        <div className="flex items-center gap-2 glass-card rounded-2xl p-1.5">
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendMessage()} placeholder="Type a message..." className="flex-1 bg-transparent text-white text-sm px-3 py-2 focus:outline-none placeholder-zinc-600" data-testid="chat-input" />
          <button onClick={sendMessage} disabled={!input.trim() || sending} className="w-9 h-9 rounded-xl gradient-cta flex items-center justify-center disabled:opacity-30 active:scale-90 transition-transform" data-testid="chat-send-btn">
            {sending ? <Loader2 className="w-4 h-4 text-white animate-spin" /> : <Send className="w-4 h-4 text-white" />}
          </button>
        </div>
      </div>
    </div>
  );
}
