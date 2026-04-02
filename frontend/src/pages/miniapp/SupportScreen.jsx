import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useMiniApp, API } from "./context";
import { Send, Loader2, Bot, User, Headphones } from "lucide-react";

export default function SupportScreen() {
  const { userId, tenantId } = useMiniApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);
  const sessionId = useRef(`support-${userId}-${Date.now()}`);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", message: msg }]);
    setLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/support/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, message: msg, session_id: sessionId.current, tenant_id: tenantId }),
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: "assistant", message: data.reply, escalated: data.escalated }]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", message: "Sorry, couldn't connect. Try again." }]);
    } finally { setLoading(false); }
  };

  return (
    <div className="pb-24 flex flex-col" style={{ height: "calc(100vh - 140px)" }}>
      <div className="text-center mb-4">
        <h2 className="font-heading text-xl font-bold text-white mb-1">AI Support</h2>
        <p className="text-xs text-zinc-500">Powered by AI - Ask anything</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 px-1 mb-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-lime-500/20 flex items-center justify-center mb-3">
              <Bot className="w-7 h-7 text-lime-400" />
            </div>
            <p className="text-zinc-500 text-sm">Ask me about plans, payments, or any help</p>
          </div>
        )}
        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${m.role === "user" ? "bg-lime-500 text-white" : "glass-card text-zinc-300"}`}>
              {m.message}
              {m.escalated && <p className="text-xs text-amber-400 mt-1 flex items-center gap-1"><Headphones className="w-3 h-3" /> Escalated to support</p>}
            </div>
          </motion.div>
        ))}
        {loading && (
          <div className="flex justify-start"><div className="glass-card rounded-2xl px-4 py-3"><Loader2 className="w-4 h-4 animate-spin text-lime-400" /></div></div>
        )}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendMessage()} placeholder="Type your message..." className="flex-1 bg-white/5 border border-white/10 rounded-2xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-lime-500/50" data-testid="support-chat-input" />
        <button onClick={sendMessage} disabled={loading || !input.trim()} className="w-12 h-12 gradient-cta rounded-2xl flex items-center justify-center disabled:opacity-30 active:scale-90 transition-transform" data-testid="support-send-btn">
          <Send className="w-5 h-5 text-white" />
        </button>
      </div>
    </div>
  );
}
