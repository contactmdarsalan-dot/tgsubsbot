import { useState, useEffect } from "react";
import { toast } from "sonner";
import { CreditCard, Search, Loader2, Smartphone, RefreshCw, IndianRupee, CheckCircle, Clock, XCircle, ChevronLeft, ChevronRight, Eye, X } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}`, "Content-Type": "application/json" });

export default function MiniAppPayments() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [stats, setStats] = useState({ total: 0, verified: 0, revenue: 0 });
  const [page, setPage] = useState(1);
  const [screenshotModal, setScreenshotModal] = useState({ open: false, url: "" });

  useEffect(() => { fetchPayments(); }, [page, filter]);

  const fetchPayments = async () => {
    setLoading(true);
    try {
      let url = `${API}/miniapp-manage/payments?page=${page}&limit=50`;
      if (filter !== "all") url += `&status=${filter}`;
      const res = await fetch(url, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setPayments(data.payments || []);
        setStats({ total: data.total || 0, verified: data.verified || 0, revenue: data.revenue || 0 });
      }
    } catch (e) { toast.error("Failed to fetch payments"); }
    finally { setLoading(false); }
  };

  const handleAction = async (paymentId, action) => {
    try {
      const res = await fetch(`${API}/miniapp-manage/payment-action`, {
        method: "POST", headers: headers(),
        body: JSON.stringify({ payment_id: paymentId, action }),
      });
      if (res.ok) { toast.success(action === "approve" ? "Payment approved" : "Payment rejected"); fetchPayments(); }
    } catch (e) { toast.error("Action failed"); }
  };

  const filtered = search
    ? payments.filter(p => (p.telegram_user_id || "").includes(search) || (p.telegram_username || "").toLowerCase().includes(search.toLowerCase()) || (p.plan_name || "").toLowerCase().includes(search.toLowerCase()))
    : payments;

  const statusColors = { pending: "bg-amber-500/15 text-amber-400", verified: "bg-emerald-500/15 text-emerald-400", approved: "bg-emerald-500/15 text-emerald-400", rejected: "bg-lime-500/15 text-lime-400" };
  const filterTabs = [{ id: "all", label: "All" }, { id: "pending", label: "Pending" }, { id: "verified", label: "Verified" }, { id: "rejected", label: "Rejected" }];

  return (
    <div className="space-y-6" data-testid="miniapp-payments">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Smartphone className="w-6 h-6 text-emerald-400" /> Mini App Payments</h1>
        <p className="text-zinc-400 text-sm mt-1">Payments received through the Mini App (separate from Bot payments)</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-white">{stats.total}</p>
          <p className="text-xs text-zinc-500 mt-1">Total Payments</p>
        </div>
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400">{stats.verified}</p>
          <p className="text-xs text-zinc-500 mt-1">Verified</p>
        </div>
        <div className="bg-zinc-900/50 border border-white/5 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400 flex items-center justify-center gap-1"><IndianRupee className="w-5 h-5" />{stats.revenue}</p>
          <p className="text-xs text-zinc-500 mt-1">Revenue</p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 p-1 bg-zinc-900/50 border border-white/5 rounded-xl">
        {filterTabs.map(t => (
          <button key={t.id} onClick={() => { setFilter(t.id); setPage(1); }} data-testid={`filter-${t.id}`}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${filter === t.id ? "bg-emerald-600 text-white" : "text-zinc-400 hover:text-white"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Search + Refresh */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by user ID, username, or plan..." className="bg-zinc-900/50 border-white/10 text-white pl-10" data-testid="search-miniapp-payments" />
        </div>
        <button onClick={fetchPayments} className="text-xs text-zinc-400 flex items-center gap-1 hover:text-white px-3 py-2 bg-zinc-900/50 border border-white/5 rounded-lg">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-16"><Loader2 className="w-6 h-6 animate-spin text-emerald-400 mx-auto" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 bg-zinc-900/30 border border-white/5 rounded-xl">
          <CreditCard className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-400">No Mini App payments yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(p => (
            <div key={p.id} className="bg-zinc-900/50 border border-white/5 rounded-xl p-4" data-testid={`miniapp-payment-${p.id}`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-white">@{p.telegram_username || p.telegram_user_id || "unknown"}</p>
                  <p className="text-xs text-zinc-500">{p.plan_name || p.plan_id || "-"}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white flex items-center"><IndianRupee className="w-3 h-3" />{p.amount}</span>
                  <Badge className={`border-0 text-[10px] ${statusColors[p.status] || "bg-zinc-700 text-zinc-400"}`}>
                    {p.status}
                  </Badge>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-3">
                {p.status === "pending" && (
                  <>
                    <Button size="sm" onClick={() => handleAction(p.id, "approve")} className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs" data-testid={`approve-${p.id}`}>
                      <CheckCircle className="w-3 h-3 mr-1" /> Approve
                    </Button>
                    <Button size="sm" onClick={() => handleAction(p.id, "reject")} variant="outline" className="border-red-500/20 text-red-400 hover:bg-red-500/10 text-xs" data-testid={`reject-${p.id}`}>
                      <XCircle className="w-3 h-3 mr-1" /> Reject
                    </Button>
                  </>
                )}
                {(p.screenshot_url || p.screenshot_file_id) && (
                  <Button size="sm" variant="outline" onClick={() => setScreenshotModal({ open: true, url: p.screenshot_url || p.screenshot_file_id })} className="border-white/10 text-zinc-400 hover:text-white text-xs">
                    <Eye className="w-3 h-3 mr-1" /> Screenshot
                  </Button>
                )}
              </div>

              <div className="flex items-center justify-between mt-2">
                <p className="text-[10px] text-zinc-600">{p.created_at ? new Date(p.created_at).toLocaleString("en-IN") : ""}</p>
                {p.verified_by && <p className="text-[10px] text-zinc-600">by {p.verified_by}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {stats.total > 50 && (
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

      {/* Screenshot Modal */}
      <Dialog open={screenshotModal.open} onOpenChange={() => setScreenshotModal({ open: false, url: "" })}>
        <DialogContent className="bg-zinc-900 border-white/10 text-white max-w-lg">
          <DialogHeader><DialogTitle>Payment Screenshot</DialogTitle></DialogHeader>
          <img src={screenshotModal.url} alt="Payment screenshot" className="w-full rounded-lg" />
        </DialogContent>
      </Dialog>
    </div>
  );
}
