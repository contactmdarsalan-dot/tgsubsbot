import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Users, Search, Loader2, Smartphone, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "application/json" });

export default function MiniAppSubscribers() {
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [total, setTotal] = useState(0);
  const [active, setActive] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => { fetchSubscribers(); }, [page]);

  const fetchSubscribers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/miniapp-manage/subscribers?page=${page}&limit=50`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setSubscribers(data.subscribers || []);
        setTotal(data.total || 0);
        setActive(data.active || 0);
      }
    } catch (e) { toast.error("Failed to fetch subscribers"); }
    finally { setLoading(false); }
  };

  const filtered = search
    ? subscribers.filter(s => (s.telegram_user_id || "").includes(search) || (s.telegram_username || "").toLowerCase().includes(search.toLowerCase()) || (s.plan_name || "").toLowerCase().includes(search.toLowerCase()))
    : subscribers;

  return (
    <div className="space-y-6" data-testid="miniapp-subscribers">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Smartphone className="w-6 h-6 text-emerald-400" /> Mini App Subscribers</h1>
        <p className="text-zinc-400 text-sm mt-1">Users subscribed through the Mini App (separate from Bot subscribers)</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-white">{total}</p>
          <p className="text-xs text-zinc-500 mt-1">Total</p>
        </div>
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400">{active}</p>
          <p className="text-xs text-zinc-500 mt-1">Active</p>
        </div>
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-zinc-400">{total - active}</p>
          <p className="text-xs text-zinc-500 mt-1">Expired</p>
        </div>
      </div>

      {/* Search + Refresh */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by user ID, username, or plan..." className="bg-zinc-900/50 border-white/10 text-white pl-10" data-testid="search-miniapp-subs" />
        </div>
        <button onClick={fetchSubscribers} className="text-xs text-zinc-400 flex items-center gap-1 hover:text-white px-3 py-2 bg-zinc-900/50 border border-white/5 rounded-lg">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-16"><Loader2 className="w-6 h-6 animate-spin text-emerald-400 mx-auto" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/30 border border-white/5 rounded-xl">
          <Users className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400">No Mini App subscribers yet</p>
        </div>
      ) : (
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">User</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Plan</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Started</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Expires</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(sub => (
                  <tr key={sub.id} className="border-b border-white/3 hover:bg-white/2" data-testid={`miniapp-sub-${sub.id}`}>
                    <td className="px-4 py-3">
                      <p className="text-white font-medium">@{sub.telegram_username || sub.telegram_user_id || "unknown"}</p>
                      <p className="text-zinc-500 text-xs">{sub.telegram_user_id}</p>
                    </td>
                    <td className="px-4 py-3 text-zinc-300">{sub.plan_name || sub.plan_id || "-"}</td>
                    <td className="px-4 py-3">
                      <Badge className={`border-0 ${sub.status === "active" ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-700 text-zinc-400"}`}>
                        {sub.status || "unknown"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs">{sub.start_date ? new Date(sub.start_date).toLocaleDateString("en-IN") : "-"}</td>
                    <td className="px-4 py-3 text-zinc-400 text-xs">{sub.end_date ? new Date(sub.end_date).toLocaleDateString("en-IN") : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="text-xs text-zinc-400 flex items-center gap-1 px-3 py-1.5 bg-zinc-900/50 border border-white/5 rounded-lg disabled:opacity-40">
            <ChevronLeft className="w-3 h-3" /> Prev
          </button>
          <span className="text-xs text-zinc-500">Page {page}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={filtered.length < 50} className="text-xs text-zinc-400 flex items-center gap-1 px-3 py-1.5 bg-zinc-900/50 border border-white/5 rounded-lg disabled:opacity-40">
            Next <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
}
