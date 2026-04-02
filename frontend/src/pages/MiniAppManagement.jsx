import { useState, useEffect, useRef, useCallback } from "react";
import { Video, Radio, MessageCircle, Calendar, Clock, PhoneCall, Eye, Send, Loader2, CheckCircle, XCircle, Play, Square, Search, ChevronRight, RefreshCw, User } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function MiniAppManagement() {
  const [activeTab, setActiveTab] = useState("video-calls");
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const tabs = [
    { id: "video-calls", label: "Video Calls", icon: Video },
    { id: "live-stream", label: "Live Stream", icon: Radio },
    { id: "messages", label: "Messages", icon: MessageCircle },
  ];

  return (
    <div className="space-y-6" data-testid="miniapp-management">
      <div>
        <h1 className="text-2xl font-bold text-white">Mini App Management</h1>
        <p className="text-zinc-400 text-sm mt-1">Manage video calls, live streams, and messages (separate from Bot features)</p>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1 p-1 bg-zinc-900/50 border border-white/5 rounded-xl">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} data-testid={`tab-${t.id}`}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === t.id ? "bg-lime-600 text-white" : "text-zinc-400 hover:text-white"}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {activeTab === "video-calls" && <VideoCallsTab headers={headers} />}
      {activeTab === "live-stream" && <LiveStreamTab headers={headers} />}
      {activeTab === "messages" && <MessagesTab headers={headers} />}
    </div>
  );
}


// ============== VIDEO CALLS TAB ==============
function VideoCallsTab({ headers }) {
  const [bookings, setBookings] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [scheduleDialog, setScheduleDialog] = useState(null);
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/miniapp-manage/video-bookings`, { headers });
      const data = await res.json();
      setBookings(data.bookings || []);
      setStats(data.stats || {});
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchBookings(); }, [fetchBookings]);

  const handleAction = async (bookingId, action, extra = {}) => {
    try {
      await fetch(`${API}/miniapp-manage/booking-action`, {
        method: "POST", headers,
        body: JSON.stringify({ booking_id: bookingId, action, ...extra }),
      });
      fetchBookings();
      setScheduleDialog(null);
    } catch (e) { console.error(e); }
  };

  const statusColors = {
    pending: "bg-amber-500/15 text-amber-400",
    scheduled: "bg-blue-500/15 text-blue-400",
    in_call: "bg-emerald-500/15 text-emerald-400",
    completed: "bg-zinc-500/15 text-zinc-400",
    rejected: "bg-lime-500/15 text-lime-400",
  };

  return (
    <div className="space-y-4" data-testid="video-calls-tab">
      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total", value: stats.total || 0, color: "text-white" },
          { label: "Pending", value: stats.pending || 0, color: "text-amber-400" },
          { label: "Scheduled", value: stats.scheduled || 0, color: "text-blue-400" },
          { label: "Completed", value: stats.completed || 0, color: "text-emerald-400" },
        ].map(s => (
          <div key={s.label} className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-zinc-500 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Refresh */}
      <div className="flex justify-end">
        <button onClick={fetchBookings} className="text-xs text-zinc-400 flex items-center gap-1 hover:text-white">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      {/* Bookings List */}
      {loading ? (
        <div className="text-center py-12"><Loader2 className="w-6 h-6 animate-spin text-lime-400 mx-auto" /></div>
      ) : bookings.length === 0 ? (
        <div className="text-center py-12 bg-zinc-900/30 border border-white/5 rounded-xl">
          <Video className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
          <p className="text-zinc-500 text-sm">No video call bookings yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {bookings.map(b => (
            <div key={b.id} className="bg-zinc-900/50 border border-white/5 rounded-xl p-4" data-testid={`booking-item-${b.id}`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-white">{b.booked_by_name || b.booked_by}</p>
                  <p className="text-xs text-zinc-500">{b.plan_name} - {b.call_duration_minutes} min</p>
                  {b.scheduled_date && <p className="text-xs text-blue-400 mt-1 flex items-center gap-1"><Calendar className="w-3 h-3" /> {b.scheduled_date} {b.scheduled_time}</p>}
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusColors[b.status] || ""}`}>{b.status}</span>
              </div>

              <div className="flex gap-2 mt-3">
                {b.status === "pending" && (
                  <>
                    <button onClick={() => setScheduleDialog(b.id)} className="flex-1 bg-blue-600 text-white text-xs font-semibold rounded-lg py-2 flex items-center justify-center gap-1" data-testid="schedule-btn">
                      <Calendar className="w-3 h-3" /> Schedule
                    </button>
                    <button onClick={() => handleAction(b.id, "reject")} className="bg-zinc-700 text-zinc-300 text-xs font-semibold rounded-lg py-2 px-3" data-testid="reject-btn">
                      <XCircle className="w-3 h-3" />
                    </button>
                  </>
                )}
                {b.status === "scheduled" && (
                  <button onClick={() => handleAction(b.id, "start")} className="flex-1 bg-emerald-600 text-white text-xs font-semibold rounded-lg py-2 flex items-center justify-center gap-1" data-testid="start-call-btn">
                    <PhoneCall className="w-3 h-3" /> Start Call
                  </button>
                )}
                {b.status === "in_call" && (
                  <button onClick={() => handleAction(b.id, "complete")} className="flex-1 bg-lime-600 text-white text-xs font-semibold rounded-lg py-2 flex items-center justify-center gap-1" data-testid="end-call-btn">
                    <Square className="w-3 h-3" /> End Call
                  </button>
                )}
              </div>

              {/* Schedule Dialog */}
              {scheduleDialog === b.id && (
                <div className="mt-3 p-3 bg-zinc-800 rounded-lg space-y-2">
                  <input type="date" value={scheduleDate} onChange={e => setScheduleDate(e.target.value)} className="w-full bg-zinc-700 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
                  <input type="time" value={scheduleTime} onChange={e => setScheduleTime(e.target.value)} className="w-full bg-zinc-700 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
                  <div className="flex gap-2">
                    <button onClick={() => handleAction(b.id, "schedule", { scheduled_date: scheduleDate, scheduled_time: scheduleTime })} className="flex-1 bg-blue-600 text-white text-xs font-semibold rounded-lg py-2">Confirm</button>
                    <button onClick={() => setScheduleDialog(null)} className="bg-zinc-700 text-zinc-300 text-xs font-semibold rounded-lg py-2 px-3">Cancel</button>
                  </div>
                </div>
              )}

              <p className="text-[10px] text-zinc-600 mt-2">{new Date(b.created_at).toLocaleString("en-IN")}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ============== LIVE STREAM TAB ==============
function LiveStreamTab({ headers }) {
  const [streams, setStreams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchStreams = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/miniapp-manage/live-streams`, { headers });
      setStreams(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchStreams(); }, [fetchStreams]);

  const startLive = async () => {
    if (!title.trim()) return;
    setCreating(true);
    try {
      await fetch(`${API}/miniapp-manage/start-live`, {
        method: "POST", headers,
        body: JSON.stringify({ title: title.trim(), description: desc.trim() }),
      });
      setTitle("");
      setDesc("");
      setShowCreate(false);
      fetchStreams();
    } catch (e) { console.error(e); }
    finally { setCreating(false); }
  };

  const endLive = async (sessionId) => {
    try {
      await fetch(`${API}/miniapp-manage/end-live`, {
        method: "POST", headers,
        body: JSON.stringify({ session_id: sessionId }),
      });
      fetchStreams();
    } catch (e) { console.error(e); }
  };

  const activeStream = streams.find(s => s.status === "live");

  return (
    <div className="space-y-4" data-testid="live-stream-tab">
      {/* Active Live */}
      {activeStream && (
        <div className="bg-lime-900/20 border border-lime-500/30 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-lime-500 animate-pulse" />
              <p className="text-sm font-bold text-lime-400">Currently LIVE</p>
            </div>
            <div className="flex items-center gap-1 text-zinc-400 text-xs"><Eye className="w-3 h-3" /> {activeStream.viewer_count || 0}</div>
          </div>
          <p className="text-white font-semibold">{activeStream.title}</p>
          <p className="text-xs text-zinc-400 mt-1">Room: {activeStream.room_id}</p>
          <button onClick={() => endLive(activeStream.id)} className="mt-3 w-full bg-lime-600 text-white text-xs font-semibold rounded-lg py-2 flex items-center justify-center gap-1" data-testid="end-live-btn">
            <Square className="w-3 h-3" /> End Live
          </button>
        </div>
      )}

      {/* Start Live Button */}
      {!activeStream && (
        <button onClick={() => setShowCreate(!showCreate)} className="w-full bg-lime-600 text-white font-semibold rounded-xl py-3 flex items-center justify-center gap-2 hover:bg-lime-500 transition-colors" data-testid="start-live-btn">
          <Radio className="w-5 h-5" /> Go Live in Mini App
        </button>
      )}

      {showCreate && (
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 space-y-3">
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Live stream title..." className="w-full bg-zinc-800 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-lime-500/30" />
          <textarea value={desc} onChange={e => setDesc(e.target.value)} placeholder="Description (optional)..." rows={2} className="w-full bg-zinc-800 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-lime-500/30 resize-none" />
          <button onClick={startLive} disabled={!title.trim() || creating} className="w-full bg-lime-600 text-white font-semibold rounded-lg py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2">
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Start Live
          </button>
        </div>
      )}

      {/* Stream History */}
      <h3 className="text-sm font-semibold text-zinc-400">Stream History</h3>
      {loading ? (
        <div className="text-center py-8"><Loader2 className="w-5 h-5 animate-spin text-lime-400 mx-auto" /></div>
      ) : streams.length === 0 ? (
        <div className="text-center py-8 bg-zinc-900/30 border border-white/5 rounded-xl">
          <Radio className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
          <p className="text-zinc-500 text-sm">No live streams yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {streams.map(s => (
            <div key={s.id} className="bg-zinc-900/50 border border-white/5 rounded-xl p-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">{s.title}</p>
                <p className="text-xs text-zinc-500">{new Date(s.created_at).toLocaleString("en-IN")} - {s.viewer_count || 0} viewers</p>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${s.status === "live" ? "bg-lime-500/15 text-lime-400" : "bg-zinc-700 text-zinc-400"}`}>{s.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ============== MESSAGES TAB ==============
function MessagesTab({ headers }) {
  const [conversations, setConversations] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeChat, setActiveChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const chatEndRef = useRef(null);

  const fetchChats = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/miniapp-manage/chats`, { headers });
      const data = await res.json();
      setConversations(data.conversations || []);
      setStats(data.stats || {});
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchChats(); }, [fetchChats]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openChat = async (userId) => {
    setActiveChat(userId);
    try {
      const res = await fetch(`${API}/miniapp-manage/chat/${userId}`, { headers });
      setMessages(await res.json());
    } catch (e) { console.error(e); }
  };

  const sendReply = async () => {
    if (!reply.trim() || !activeChat || sending) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/miniapp-manage/chat/reply`, {
        method: "POST", headers,
        body: JSON.stringify({ recipient_id: activeChat, message: reply.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        setMessages(prev => [...prev, data.message]);
        setReply("");
      }
    } catch (e) { console.error(e); }
    finally { setSending(false); }
  };

  if (activeChat) {
    const conv = conversations.find(c => c.user_id === activeChat);
    return (
      <div className="space-y-3" data-testid="chat-detail">
        <button onClick={() => { setActiveChat(null); fetchChats(); }} className="text-xs text-zinc-400 hover:text-white flex items-center gap-1">
          Back to conversations
        </button>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-full bg-lime-600/20 flex items-center justify-center"><User className="w-4 h-4 text-lime-400" /></div>
          <div><p className="text-sm font-semibold text-white">{conv?.name || activeChat}</p></div>
        </div>

        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-3 max-h-96 overflow-y-auto space-y-2">
          {messages.map((m, i) => (
            <div key={m.id || i} className={`flex ${m.sender_type === "admin" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] rounded-2xl px-3 py-2 ${m.sender_type === "admin" ? "bg-lime-600/80 rounded-br-sm" : "bg-zinc-800 rounded-bl-sm"}`}>
                <p className="text-sm text-white">{m.message}</p>
                <p className="text-[9px] text-white/40 mt-0.5 text-right">{m.created_at ? new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : ""}</p>
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        <div className="flex items-center gap-2">
          <input value={reply} onChange={e => setReply(e.target.value)} onKeyDown={e => e.key === "Enter" && sendReply()} placeholder="Type a reply..." className="flex-1 bg-zinc-800 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none" data-testid="dashboard-chat-input" />
          <button onClick={sendReply} disabled={!reply.trim() || sending} className="bg-lime-600 text-white rounded-lg px-4 py-2.5 text-sm font-semibold disabled:opacity-50 flex items-center gap-1" data-testid="dashboard-chat-send">
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="messages-tab">
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-white">{stats.total_conversations || 0}</p>
          <p className="text-xs text-zinc-500 mt-1">Conversations</p>
        </div>
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-lime-400">{stats.unread_total || 0}</p>
          <p className="text-xs text-zinc-500 mt-1">Unread</p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12"><Loader2 className="w-6 h-6 animate-spin text-lime-400 mx-auto" /></div>
      ) : conversations.length === 0 ? (
        <div className="text-center py-12 bg-zinc-900/30 border border-white/5 rounded-xl">
          <MessageCircle className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
          <p className="text-zinc-500 text-sm">No conversations yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {conversations.map(c => (
            <button key={c.user_id} onClick={() => openChat(c.user_id)} className="w-full bg-zinc-900/50 border border-white/5 rounded-xl p-3 flex items-center gap-3 hover:border-lime-500/20 transition-colors text-left" data-testid={`conv-${c.user_id}`}>
              <div className="w-10 h-10 rounded-full bg-lime-600/20 flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-lime-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-white truncate">{c.name || c.user_id}</p>
                  {c.unread > 0 && <span className="bg-lime-600 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">{c.unread}</span>}
                </div>
                <p className="text-xs text-zinc-500 truncate">{c.last_message}</p>
              </div>
              <ChevronRight className="w-4 h-4 text-zinc-600 flex-shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
