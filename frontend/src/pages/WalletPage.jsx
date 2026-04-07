import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Wallet, IndianRupee, ArrowDownToLine, ArrowUpFromLine, Settings2,
  Check, X, Clock, TrendingUp, Building2, AlertTriangle, RefreshCw,
  ChevronDown, ExternalLink, Ban, CheckCircle2, Loader2,
} from "lucide-react";
import { Button } from "../components/ui/button";

const API = process.env.REACT_APP_BACKEND_URL;

function StatCard({ icon: Icon, label, value, sub, color = "lime" }) {
  const colors = {
    lime: "from-lime-500/20 to-lime-500/5 border-lime-500/30 text-lime-400",
    rose: "from-rose-500/20 to-rose-500/5 border-rose-500/30 text-rose-400",
    amber: "from-amber-500/20 to-amber-500/5 border-amber-500/30 text-amber-400",
    sky: "from-sky-500/20 to-sky-500/5 border-sky-500/30 text-sky-400",
    violet: "from-violet-500/20 to-violet-500/5 border-violet-500/30 text-violet-400",
  };
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-5`} data-testid={`stat-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} />
        <span className="text-xs uppercase tracking-wider opacity-70">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {sub && <div className="text-xs mt-1 opacity-60">{sub}</div>}
    </div>
  );
}

const statusColors = {
  pending: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  approved: "bg-sky-500/20 text-sky-300 border-sky-500/30",
  completed: "bg-lime-500/20 text-lime-300 border-lime-500/30",
  rejected: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  processing: "bg-violet-500/20 text-violet-300 border-violet-500/30",
};

export default function WalletPage() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isSuperAdmin = user.role === "super_admin";
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Bearer ${token}` };

  const [tab, setTab] = useState(isSuperAdmin ? "overview" : "balance");
  const [loading, setLoading] = useState(true);

  // Super Admin state
  const [platformRevenue, setPlatformRevenue] = useState(null);
  const [allWithdrawals, setAllWithdrawals] = useState([]);
  const [walletConfig, setWalletConfig] = useState(null);

  // Tenant state
  const [balance, setBalance] = useState(null);
  const [myWithdrawals, setMyWithdrawals] = useState([]);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [bankDetails, setBankDetails] = useState({ account_name: "", account_number: "", ifsc: "", upi_id: "" });
  const [withdrawNotes, setWithdrawNotes] = useState("");
  const [showWithdrawForm, setShowWithdrawForm] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);

  // Config edit state
  const [editConfig, setEditConfig] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (isSuperAdmin) {
        const [rev, withdrawals, config] = await Promise.all([
          axios.get(`${API}/api/wallet/platform-revenue`, { headers }),
          axios.get(`${API}/api/wallet/all-withdrawals`, { headers }),
          axios.get(`${API}/api/wallet/config`, { headers }),
        ]);
        setPlatformRevenue(rev.data);
        setAllWithdrawals(withdrawals.data);
        setWalletConfig(config.data);
      } else {
        const [bal, withdrawals] = await Promise.all([
          axios.get(`${API}/api/wallet/balance`, { headers }),
          axios.get(`${API}/api/wallet/withdrawals`, { headers }),
        ]);
        setBalance(bal.data);
        setMyWithdrawals(withdrawals.data);
      }
    } catch (err) {
      console.error("Wallet fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, [isSuperAdmin]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleWithdraw = async () => {
    if (!withdrawAmount || parseFloat(withdrawAmount) <= 0) return;
    setActionLoading("withdraw");
    try {
      await axios.post(`${API}/api/wallet/withdraw`, {
        amount: parseFloat(withdrawAmount),
        bank_details: bankDetails,
        notes: withdrawNotes,
      }, { headers });
      setWithdrawAmount(""); setWithdrawNotes(""); setShowWithdrawForm(false);
      setBankDetails({ account_name: "", account_number: "", ifsc: "", upi_id: "" });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || "Withdrawal failed");
    } finally { setActionLoading(null); }
  };

  const handleAction = async (id, action, extraData = {}) => {
    setActionLoading(id);
    try {
      await axios.put(`${API}/api/wallet/withdrawals/${id}/${action}`, extraData, { headers });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || `Action failed`);
    } finally { setActionLoading(null); }
  };

  const saveConfig = async () => {
    setActionLoading("config");
    try {
      await axios.put(`${API}/api/wallet/config`, editConfig, { headers });
      setWalletConfig({ ...walletConfig, ...editConfig });
      setEditConfig(null);
      fetchData();
    } catch (err) { alert("Failed to save config"); }
    finally { setActionLoading(null); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="wallet-loading">
        <Loader2 className="animate-spin text-lime-400" size={32} />
      </div>
    );
  }

  const tabs = isSuperAdmin
    ? [
        { id: "overview", label: "Platform Revenue", icon: TrendingUp },
        { id: "withdrawals", label: "Withdrawal Requests", icon: ArrowUpFromLine },
        { id: "tenants", label: "Tenant Breakdown", icon: Building2 },
        { id: "config", label: "Wallet Config", icon: Settings2 },
      ]
    : [
        { id: "balance", label: "My Balance", icon: Wallet },
        { id: "withdrawals", label: "My Withdrawals", icon: ArrowUpFromLine },
      ];

  return (
    <div className="space-y-6" data-testid="wallet-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Wallet className="text-lime-400" /> Wallet
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            {isSuperAdmin ? "Platform revenue & withdrawal management" : "Your earnings & withdrawals"}
          </p>
        </div>
        <Button onClick={fetchData} variant="outline" size="sm" className="border-zinc-700 text-zinc-300" data-testid="refresh-wallet">
          <RefreshCw size={14} className="mr-1" /> Refresh
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-900/50 p-1 rounded-lg border border-zinc-800" data-testid="wallet-tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`tab-${t.id}`}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm transition-all ${
              tab === t.id ? "bg-lime-500/20 text-lime-400 border border-lime-500/30" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {/* SUPER ADMIN — Overview */}
      {isSuperAdmin && tab === "overview" && platformRevenue && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon={IndianRupee} label="Total Revenue" value={`₹${platformRevenue.total_revenue.toLocaleString()}`} color="lime" />
            <StatCard icon={TrendingUp} label="Platform Commission" value={`₹${platformRevenue.platform_earnings.toLocaleString()}`} sub={platformRevenue.commission_config} color="violet" />
            <StatCard icon={ArrowUpFromLine} label="Total Payouts" value={`₹${platformRevenue.total_payouts.toLocaleString()}`} color="sky" />
            <StatCard icon={Clock} label="Pending Payouts" value={`₹${platformRevenue.pending_payouts.toLocaleString()}`} sub={`${platformRevenue.pending_payout_count} requests`} color="amber" />
          </div>
        </div>
      )}

      {/* SUPER ADMIN — Withdrawals */}
      {isSuperAdmin && tab === "withdrawals" && (
        <div className="space-y-4">
          <div className="flex gap-2">
            {["all", "pending", "approved", "completed", "rejected"].map(s => (
              <button key={s} className="text-xs px-3 py-1 rounded-full border border-zinc-700 text-zinc-300 hover:bg-zinc-800 capitalize"
                onClick={() => {}} data-testid={`filter-${s}`}>
                {s}
              </button>
            ))}
          </div>
          {allWithdrawals.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">No withdrawal requests yet</div>
          ) : (
            <div className="space-y-3">
              {allWithdrawals.map(w => (
                <div key={w.id} className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4" data-testid={`withdrawal-${w.id}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-semibold text-lg">₹{w.amount?.toLocaleString()}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[w.status] || ""}`}>{w.status}</span>
                      </div>
                      <div className="text-xs text-zinc-400 mt-1">
                        {w.tenant_name} ({w.tenant_email}) &bull; {new Date(w.created_at).toLocaleDateString()}
                      </div>
                      {w.bank_details?.upi_id && <div className="text-xs text-zinc-500 mt-0.5">UPI: {w.bank_details.upi_id}</div>}
                      {w.bank_details?.account_number && <div className="text-xs text-zinc-500 mt-0.5">A/C: {w.bank_details.account_number} | IFSC: {w.bank_details.ifsc}</div>}
                      {w.notes && <div className="text-xs text-zinc-500 mt-0.5 italic">Note: {w.notes}</div>}
                    </div>
                    <div className="flex gap-2">
                      {w.status === "pending" && (
                        <>
                          <Button size="sm" className="bg-lime-600 hover:bg-lime-700 text-white" onClick={() => handleAction(w.id, "approve")}
                            disabled={actionLoading === w.id} data-testid={`approve-${w.id}`}>
                            {actionLoading === w.id ? <Loader2 className="animate-spin" size={14} /> : <Check size={14} />} Approve
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => handleAction(w.id, "reject", { reason: prompt("Rejection reason:") || "" })}
                            disabled={actionLoading === w.id} data-testid={`reject-${w.id}`}>
                            <X size={14} /> Reject
                          </Button>
                        </>
                      )}
                      {w.status === "approved" && (
                        <Button size="sm" className="bg-sky-600 hover:bg-sky-700 text-white"
                          onClick={() => handleAction(w.id, "complete", { transaction_ref: prompt("Transaction ref:") || "" })}
                          disabled={actionLoading === w.id} data-testid={`complete-${w.id}`}>
                          <CheckCircle2 size={14} className="mr-1" /> Mark Paid
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SUPER ADMIN — Tenant Breakdown */}
      {isSuperAdmin && tab === "tenants" && platformRevenue && (
        <div className="space-y-3">
          {platformRevenue.tenant_breakdown.map(t => (
            <div key={t.tenant_id} className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 flex items-center justify-between" data-testid={`tenant-${t.tenant_id}`}>
              <div>
                <div className="text-white font-medium">{t.tenant_name}</div>
                <div className="text-xs text-zinc-400">{t.payment_count} payments</div>
              </div>
              <div className="text-right">
                <div className="text-lime-400 font-semibold">₹{t.revenue.toLocaleString()}</div>
                <div className="text-xs text-zinc-500">Commission: ₹{t.commission.toLocaleString()} | Net: ₹{t.net_to_tenant.toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* SUPER ADMIN — Config */}
      {isSuperAdmin && tab === "config" && (
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 max-w-xl space-y-4" data-testid="wallet-config-form">
          <h3 className="text-lg font-semibold text-white">Withdrawal Rules</h3>
          {[
            { key: "commission_type", label: "Commission Type", type: "select", options: ["percentage", "fixed"] },
            { key: "commission_value", label: "Commission Value", type: "number" },
            { key: "min_withdrawal", label: "Min Withdrawal (₹)", type: "number" },
            { key: "max_withdrawal_per_day", label: "Max Per Day (₹)", type: "number" },
            { key: "processing_days", label: "Processing Days", type: "number" },
            { key: "auto_approve_below", label: "Auto-Approve Below (₹)", type: "number" },
            { key: "payout_method", label: "Payout Method", type: "select", options: ["manual", "razorpay_payout"] },
          ].map(f => (
            <div key={f.key} className="flex items-center justify-between gap-4">
              <label className="text-sm text-zinc-300 min-w-[180px]">{f.label}</label>
              {f.type === "select" ? (
                <select
                  className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm flex-1"
                  value={(editConfig || walletConfig)?.[f.key] ?? ""}
                  onChange={e => setEditConfig({ ...(editConfig || walletConfig), [f.key]: e.target.value })}
                  data-testid={`config-${f.key}`}
                >
                  {f.options.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input
                  type="number"
                  className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-white text-sm flex-1"
                  value={(editConfig || walletConfig)?.[f.key] ?? ""}
                  onChange={e => setEditConfig({ ...(editConfig || walletConfig), [f.key]: parseFloat(e.target.value) || 0 })}
                  data-testid={`config-${f.key}`}
                />
              )}
            </div>
          ))}
          <Button onClick={saveConfig} className="bg-lime-600 hover:bg-lime-700 w-full" disabled={actionLoading === "config"} data-testid="save-config">
            {actionLoading === "config" ? <Loader2 className="animate-spin mr-2" size={14} /> : null}
            Save Configuration
          </Button>
        </div>
      )}

      {/* TENANT — Balance */}
      {!isSuperAdmin && tab === "balance" && balance && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon={IndianRupee} label="Total Revenue" value={`₹${balance.total_revenue.toLocaleString()}`} color="lime" />
            <StatCard icon={TrendingUp} label="Net Earnings" value={`₹${balance.net_earnings.toLocaleString()}`} sub={`Commission: ${balance.commission_rate}`} color="violet" />
            <StatCard icon={Wallet} label="Available Balance" value={`₹${balance.available_balance.toLocaleString()}`} color="sky" />
            <StatCard icon={Clock} label="Pending Withdrawals" value={`₹${balance.pending_withdrawals.toLocaleString()}`} color="amber" />
          </div>

          <div className="flex items-center gap-3">
            <Button onClick={() => setShowWithdrawForm(!showWithdrawForm)} className="bg-lime-600 hover:bg-lime-700" data-testid="request-withdrawal-btn">
              <ArrowDownToLine size={16} className="mr-1" /> Request Withdrawal
            </Button>
          </div>

          {showWithdrawForm && (
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 max-w-lg space-y-4" data-testid="withdraw-form">
              <h3 className="text-lg font-semibold text-white">New Withdrawal Request</h3>
              <div>
                <label className="text-xs text-zinc-400">Amount (₹)</label>
                <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white mt-1"
                  value={withdrawAmount} onChange={e => setWithdrawAmount(e.target.value)} placeholder="Enter amount"
                  data-testid="withdraw-amount" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400">Account Name</label>
                  <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white mt-1"
                    value={bankDetails.account_name} onChange={e => setBankDetails({ ...bankDetails, account_name: e.target.value })}
                    data-testid="bank-account-name" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">Account Number</label>
                  <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white mt-1"
                    value={bankDetails.account_number} onChange={e => setBankDetails({ ...bankDetails, account_number: e.target.value })}
                    data-testid="bank-account-number" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">IFSC Code</label>
                  <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white mt-1"
                    value={bankDetails.ifsc} onChange={e => setBankDetails({ ...bankDetails, ifsc: e.target.value })}
                    data-testid="bank-ifsc" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">UPI ID</label>
                  <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white mt-1"
                    value={bankDetails.upi_id} onChange={e => setBankDetails({ ...bankDetails, upi_id: e.target.value })}
                    data-testid="bank-upi" />
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400">Notes (optional)</label>
                <textarea className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white mt-1 h-20"
                  value={withdrawNotes} onChange={e => setWithdrawNotes(e.target.value)} data-testid="withdraw-notes" />
              </div>
              <Button onClick={handleWithdraw} className="w-full bg-lime-600 hover:bg-lime-700" disabled={actionLoading === "withdraw"} data-testid="submit-withdrawal">
                {actionLoading === "withdraw" ? <Loader2 className="animate-spin mr-2" size={14} /> : <ArrowDownToLine size={14} className="mr-1" />}
                Submit Withdrawal Request
              </Button>
            </div>
          )}
        </div>
      )}

      {/* TENANT — Withdrawal History */}
      {!isSuperAdmin && tab === "withdrawals" && (
        <div className="space-y-3">
          {myWithdrawals.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">No withdrawals yet</div>
          ) : (
            myWithdrawals.map(w => (
              <div key={w.id} className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 flex items-center justify-between" data-testid={`my-withdrawal-${w.id}`}>
                <div>
                  <span className="text-white font-semibold">₹{w.amount?.toLocaleString()}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ml-2 ${statusColors[w.status] || ""}`}>{w.status}</span>
                  <div className="text-xs text-zinc-400 mt-1">{new Date(w.created_at).toLocaleDateString()}</div>
                  {w.rejection_reason && <div className="text-xs text-rose-400 mt-0.5">Reason: {w.rejection_reason}</div>}
                  {w.transaction_ref && <div className="text-xs text-lime-400 mt-0.5">Ref: {w.transaction_ref}</div>}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
