import { useState, useEffect, useRef } from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import {
  LayoutDashboard, CreditCard, Users, Package, Settings, LogOut, Menu, X,
  Shield, Radio, Ticket, Share2, HelpCircle, BarChart3, Video, Lock,
  Sparkles, IndianRupee, Activity, User, ChevronDown, Building2,
  TrendingUp, AlertTriangle, Headphones, Globe, Search, Plus, Bell,
  ChevronRight, Zap, MessagesSquare, Languages, Smartphone, Crown, Palette,
  UserCog, MessageSquare, ShieldCheck,
} from "lucide-react";
import { Button } from "./ui/button";

const superAdminNav = [
  { path: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { path: "/dashboard/saas-management", label: "Tenants", icon: Building2 },
  { path: "/dashboard/revenue", label: "Revenue", icon: IndianRupee },
  { path: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/dashboard/admin-subs", label: "Subscriptions", icon: Crown },
  { path: "/dashboard/miniapp-users", label: "Mini App Users", icon: Smartphone },
  { path: "/dashboard/support", label: "Support", icon: Headphones },
  { path: "/dashboard/user-management", label: "Users", icon: Users },
  { path: "/dashboard/branding", label: "Platform Settings", icon: Settings },
];

const botNav = [
  { path: "/dashboard/plans", label: "Plans", icon: Package },
  { path: "/dashboard/subscribers", label: "Subscribers", icon: Users },
  { path: "/dashboard/payments", label: "Payments", icon: CreditCard },
  { path: "/dashboard/telegram-admins", label: "TG Admins", icon: ShieldCheck },
  { path: "/dashboard/bot-activity", label: "Bot Activity", icon: Activity },
  { path: "/dashboard/paid-posts", label: "Paid Posts", icon: Lock },
  { path: "/dashboard/creators", label: "Creators", icon: Sparkles },
  { path: "/dashboard/chat-groups", label: "Groups & Channels", icon: MessagesSquare },
  { path: "/dashboard/referrals", label: "Referrals", icon: Share2 },
  { path: "/dashboard/faqs", label: "FAQs", icon: HelpCircle },
  { path: "/dashboard/automation", label: "Automation", icon: Bell },
  { path: "/dashboard/settings", label: "Settings", icon: Settings },
  { path: "/dashboard/bot-language", label: "Bot Language", icon: Languages },
];

const miniAppNav = [
  { path: "/dashboard/miniapp-manage", label: "Mini App Hub", icon: Smartphone },
  { path: "/dashboard/miniapp-plans", label: "Plans", icon: Package },
  { path: "/dashboard/miniapp-subscribers", label: "Subscribers", icon: Users },
  { path: "/dashboard/miniapp-payments", label: "Payments", icon: CreditCard },
  { path: "/dashboard/video-calls", label: "Video Calls", icon: Video },
  { path: "/dashboard/live-stream", label: "Live", icon: Radio },
];

const accountNav = [
  { path: "/dashboard/broadcast", label: "Broadcast", icon: Radio },
  { path: "/dashboard/coupons", label: "Coupons", icon: Ticket },
  { path: "/dashboard/team", label: "Team", icon: UserCog },
  { path: "/dashboard/support", label: "Support", icon: MessageSquare },
];

const tenantOpsNav = [...botNav, ...miniAppNav, ...accountNav];

const tenantOnlyNav = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  ...tenantOpsNav,
];

function NavItem({ item, isActive, onClick }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.path}
      onClick={onClick}
      data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
      className={`flex items-center gap-3 px-3 py-2 text-sm rounded-xl transition-all duration-200 group ${
        isActive
          ? "bg-rose-500/15 text-white border border-rose-500/30 font-semibold"
          : "text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent"
      }`}
    >
      <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-rose-400" : "text-zinc-500 group-hover:text-zinc-300"}`} strokeWidth={1.8} />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [branding, setBranding] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const profileRef = useRef(null);

  const API = process.env.REACT_APP_BACKEND_URL + "/api";
  const SUPER_ADMIN_EMAILS = ["gamerxboys8958@gmail.com", "contactmdarsalan@gmail.com"];

  useEffect(() => {
    const role = user.role || "";
    setIsSuperAdmin(role === "super_admin" || SUPER_ADMIN_EMAILS.includes(user.email));
  }, [user.email, user.role]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    axios.get(`${API}/branding`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => setBranding(res.data))
      .catch(() => {});
  }, [API]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("isFirstUser");
    navigate("/login");
  };

  const allNav = isSuperAdmin ? superAdminNav : tenantOnlyNav;
  const currentPage = [...allNav, ...tenantOpsNav].find(item => item.path === location.pathname);

  // Breadcrumb
  const breadcrumb = [];
  if (location.pathname !== "/dashboard") {
    breadcrumb.push({ label: "Dashboard", path: "/dashboard" });
    if (currentPage) breadcrumb.push({ label: currentPage.label, path: currentPage.path });
  }

  return (
    <div className="min-h-screen flex" style={{ background: "hsl(340, 50%, 4%)" }}>
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-64 sidebar-saas transform transition-transform duration-300 ease-out flex-shrink-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
        <div className="flex flex-col h-screen overflow-hidden">
          {/* Logo */}
          <div className="p-5 border-b border-white/6 flex-shrink-0">
            <Link to="/dashboard" className="flex items-center gap-3" data-testid="sidebar-logo">
              <div className="w-9 h-9 rounded-xl gradient-cta flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <div>
                <h1 className="font-heading text-lg font-bold tracking-tight text-white">
                  {branding?.brand_name || "TGSubsBot"}
                </h1>
                <p className="text-[10px] text-zinc-500 font-medium leading-none">
                  {isSuperAdmin ? "Control Center" : "Dashboard"}
                </p>
              </div>
            </Link>
          </div>

          <nav className="flex-1 px-3 py-4 overflow-y-auto scrollbar-thin">
            {/* Super Admin: Platform section ONLY */}
            {isSuperAdmin && (
              <>
                <div className="px-3 pt-1 pb-2">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-rose-400/60">Platform</span>
                </div>
                <div className="space-y-0.5 mb-4">
                  {superAdminNav.map(item => (
                    <NavItem key={item.path} item={item} isActive={location.pathname === item.path} onClick={() => setSidebarOpen(false)} />
                  ))}
                </div>
              </>
            )}

            {/* Tenant Admin items - separated into Bot & Mini App */}
            {!isSuperAdmin && (
              <>
                <div className="space-y-0.5 mb-2">
                  <NavItem item={{ path: "/dashboard", label: "Dashboard", icon: LayoutDashboard }} isActive={location.pathname === "/dashboard"} onClick={() => setSidebarOpen(false)} />
                </div>

                <div className="px-3 pt-2 pb-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-rose-400/60">Telegram Bot</span>
                </div>
                <div className="space-y-0.5 mb-2">
                  {botNav.map(item => (
                    <NavItem key={item.path} item={item} isActive={location.pathname === item.path} onClick={() => setSidebarOpen(false)} />
                  ))}
                </div>

                <div className="px-3 pt-2 pb-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-400/60">Mini App</span>
                </div>
                <div className="space-y-0.5 mb-2">
                  {miniAppNav.map(item => (
                    <NavItem key={item.path} item={item} isActive={location.pathname === item.path} onClick={() => setSidebarOpen(false)} />
                  ))}
                </div>

                <div className="px-3 pt-2 pb-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500/60">Account</span>
                </div>
                <div className="space-y-0.5">
                  {accountNav.map(item => (
                    <NavItem key={item.path} item={item} isActive={location.pathname === item.path} onClick={() => setSidebarOpen(false)} />
                  ))}
                </div>
              </>
            )}
          </nav>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top Bar */}
        <header className="sticky top-0 z-30 border-b border-white/6 flex-shrink-0" style={{ background: "hsla(340,50%,4%,0.85)", backdropFilter: "blur(20px)" }}>
          <div className="flex items-center justify-between px-4 md:px-6 py-3">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" className="lg:hidden text-white hover:bg-white/10 rounded-xl" onClick={() => setSidebarOpen(true)} data-testid="mobile-menu-btn">
                <Menu className="w-5 h-5" />
              </Button>

              {/* Breadcrumb */}
              <div className="hidden md:flex items-center gap-1.5 text-sm">
                {breadcrumb.length === 0 ? (
                  <span className="font-heading font-semibold text-white">Overview</span>
                ) : (
                  breadcrumb.map((b, i) => (
                    <span key={b.path} className="flex items-center gap-1.5">
                      {i > 0 && <ChevronRight className="w-3 h-3 text-zinc-600" />}
                      {i === breadcrumb.length - 1 ? (
                        <span className="font-heading font-semibold text-white">{b.label}</span>
                      ) : (
                        <Link to={b.path} className="text-zinc-500 hover:text-zinc-300 transition-colors">{b.label}</Link>
                      )}
                    </span>
                  ))
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Quick Actions */}
              {isSuperAdmin && (
                <div className="hidden md:flex items-center gap-1.5">
                  <button onClick={() => navigate("/dashboard/saas-management")} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-all border border-white/6" data-testid="quick-add-tenant">
                    <Plus className="w-3.5 h-3.5" />
                    Tenant
                  </button>
                </div>
              )}

              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Online" />

              {/* Profile */}
              <div className="relative" ref={profileRef}>
                <button onClick={() => setProfileOpen(!profileOpen)} className="flex items-center gap-2 px-3 py-1.5 rounded-xl hover:bg-white/5 transition-colors" data-testid="profile-dropdown-btn">
                  <div className="w-8 h-8 rounded-lg gradient-cta flex items-center justify-center">
                    <span className="text-xs font-bold text-white">{user.name?.charAt(0)?.toUpperCase() || "U"}</span>
                  </div>
                  <span className="text-sm font-medium hidden md:block max-w-[120px] truncate text-zinc-300">{user.name || "User"}</span>
                  <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${profileOpen ? "rotate-180" : ""}`} />
                </button>

                {profileOpen && (
                  <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-white/10 shadow-2xl py-1 z-50" style={{ background: "hsl(340, 40%, 7%)" }}>
                    <div className="px-4 py-3 border-b border-white/6">
                      <p className="text-sm font-semibold text-white truncate">{user.name || "User"}</p>
                      <p className="text-xs text-zinc-500 truncate">{user.email}</p>
                      {isSuperAdmin && <span className="inline-block mt-1 px-2 py-0.5 text-[10px] font-bold bg-rose-500/20 text-rose-400 rounded-full">Super Admin</span>}
                    </div>
                    <Link to="/dashboard/profile" onClick={() => setProfileOpen(false)} className="flex items-center gap-3 px-4 py-2.5 text-sm text-zinc-400 hover:text-white hover:bg-white/5 transition-colors" data-testid="profile-link">
                      <User className="w-4 h-4" /> Profile
                    </Link>
                    <Link to="/dashboard/settings" onClick={() => setProfileOpen(false)} className="flex items-center gap-3 px-4 py-2.5 text-sm text-zinc-400 hover:text-white hover:bg-white/5 transition-colors">
                      <Settings className="w-4 h-4" /> Settings
                    </Link>
                    <div className="border-t border-white/6 mt-1 pt-1">
                      <button onClick={() => { setProfileOpen(false); handleLogout(); }} className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-rose-400 hover:bg-rose-500/10 transition-colors" data-testid="logout-btn">
                        <LogOut className="w-4 h-4" /> Logout
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 p-4 md:p-6 overflow-y-auto scrollbar-thin" style={{ background: "hsl(340, 50%, 4%)" }}>
          <div className="max-w-[1400px] mx-auto pb-8">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
