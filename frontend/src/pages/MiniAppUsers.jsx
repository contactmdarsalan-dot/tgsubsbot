import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function MiniAppUsers() {
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState({ total: 0, today: 0 });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    const token = localStorage.getItem("token");
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const [usersRes, statsRes] = await Promise.all([
        fetch(`${API}/miniapp-users`, { headers }),
        fetch(`${API}/miniapp-users/stats`, { headers }),
      ]);
      setUsers(await usersRes.json());
      setStats(await statsRes.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const filtered = users.filter(
    (u) =>
      u.phone?.includes(search) ||
      u.telegram_username?.toLowerCase().includes(search.toLowerCase()) ||
      u.telegram_user_id?.includes(search)
  );

  return (
    <div className="space-y-5" data-testid="miniapp-users-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" data-testid="miniapp-users-title">Mini App Users</h1>
          <p className="text-sm text-muted-foreground">Phone numbers collected from Telegram Mini App</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <Card data-testid="miniapp-users-total-card">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Users</p>
            <p className="text-2xl font-bold mt-1" data-testid="miniapp-users-total">{stats.total}</p>
          </CardContent>
        </Card>
        <Card data-testid="miniapp-users-today-card">
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Today</p>
            <p className="text-2xl font-bold mt-1" data-testid="miniapp-users-today">{stats.today}</p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Input
        placeholder="Search by phone, username, or Telegram ID..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        data-testid="miniapp-users-search"
        className="max-w-sm"
      />

      {/* Table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Collected Phone Numbers ({filtered.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">No users found</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="miniapp-users-table">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">#</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Phone</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">TG Username</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">TG ID</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Discount</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Registered</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u, i) => (
                    <tr key={u.id || i} className="border-b border-border/50 hover:bg-muted/30" data-testid={`miniapp-user-row-${i}`}>
                      <td className="py-2.5 px-3 text-muted-foreground">{i + 1}</td>
                      <td className="py-2.5 px-3 font-mono font-medium">{u.phone || "—"}</td>
                      <td className="py-2.5 px-3">{u.telegram_username ? `@${u.telegram_username}` : "—"}</td>
                      <td className="py-2.5 px-3 font-mono text-xs text-muted-foreground">{u.telegram_user_id || "—"}</td>
                      <td className="py-2.5 px-3">
                        <span className="text-xs bg-green-500/10 text-green-500 px-2 py-0.5 rounded-full font-medium">
                          {u.discount_percent || 20}% OFF
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-muted-foreground text-xs">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
