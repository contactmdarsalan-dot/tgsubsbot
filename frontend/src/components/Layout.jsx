import { useState, useEffect, useRef } from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import {
  LayoutDashboard,
  CreditCard,
  Users,
  Package,
  Bell,
  Settings,
  LogOut,
  Menu,
  X,
  Crown,
  Shield,
  MessageSquare,
  UserCog,
  MessagesSquare,
  Radio,
  Ticket,
  Share2,
  HelpCircle,
  BarChart3,
  Video,
  Lock,
  Sparkles,
  Heart,
  IndianRupee,
  ShieldCheck,
  Activity,
  User,
  ChevronDown,
  Palette,
  Smartphone,
  Languages,
} from "lucide-react";
import { Button } from "./ui/button";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/dashboard/plans", label: "Plans", icon: Package },
  { path: "/dashboard/subscribers", label: "Subscribers", icon: Users },
  { path: "/dashboard/payments", label: "Payments", icon: CreditCard },
  { path: "/dashboard/revenue", label: "Revenue", icon: IndianRupee },
  { path: "/dashboard/telegram-admins", label: "TG Admins", icon: ShieldCheck },
  { path: "/dashboard/bot-activity", label: "Bot Activity", icon: Activity },
  { path: "/dashboard/paid-posts", label: "Paid Posts", icon: Lock },
  { path: "/dashboard/live-stream", label: "Live", icon: Radio },
  { path: "/dashboard/creators", label: "Creators", icon: Sparkles },
  { path: "/dashboard/chat-groups", label: "Groups & Channels", icon: MessagesSquare },
  { path: "/dashboard/broadcast", label: "Broadcast", icon: Radio },
  { path: "/dashboard/coupons", label: "Coupons", icon: Ticket },
  { path: "/dashboard/referrals", label: "Referrals", icon: Share2 },
  { path: "/dashboard/faqs", label: "FAQs", icon: HelpCircle },
  { path: "/dashboard/video-calls", label: "Video Calls", icon: Video },
  { path: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/dashboard/automation", label: "Automation", icon: Bell },
  { path: "/dashboard/settings", label: "Settings", icon: Settings },
  { path: "/dashboard/bot-language", label: "Bot Language", icon: Languages },
  { path: "/dashboard/support", label: "Support", icon: MessageSquare },
  { path: "/dashboard/miniapp-users", label: "Mini App Users", icon: Smartphone },
];

const adminNavItems = [
  { path: "/dashboard/admin-subs", label: "SaaS Subs", icon: Crown, adminOnly: true },
];

const superAdminNavItems = [
  { path: "/dashboard/branding", label: "Branding", icon: Palette, superAdminOnly: true },
  { path: "/dashboard/super-admin", label: "Admin Support", icon: Shield, superAdminOnly: true },
  { path: "/dashboard/user-management", label: "User Management", icon: Users, superAdminOnly: true },
];

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [branding, setBranding] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const profileRef = useRef(null);

  const API = process.env.REACT_APP_BACKEND_URL + "/api";
  const SUPER_ADMIN_EMAILS = ["gamerxboys8958@gmail.com", "contactmdarsalan@gmail.com"];

  useEffect(() => {
    const adminStatus = localStorage.getItem("isFirstUser") === "true" || 
                        user.is_admin === true || 
                        user.role === "admin" || 
                        user.role === "super_admin";
    setIsAdmin(adminStatus);
    
    const superAdminStatus = user.role === "super_admin" || SUPER_ADMIN_EMAILS.includes(user.email);
    setIsSuperAdmin(superAdminStatus);
  }, [user.email, user.role, user.is_admin]);

  // Fetch and apply branding
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    axios.get(`${API}/branding`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => {
        const b = res.data;
        setBranding(b);
        // Apply CSS variables for branding colors
        const root = document.documentElement;
        if (b.primary_color) {
          // Convert hex to HSL for shadcn CSS vars
          const hex = b.primary_color;
          const r = parseInt(hex.slice(1,3), 16) / 255;
          const g = parseInt(hex.slice(3,5), 16) / 255;
          const bl = parseInt(hex.slice(5,7), 16) / 255;
          const max = Math.max(r, g, bl), min = Math.min(r, g, bl);
          let h = 0, s = 0, l = (max + min) / 2;
          if (max !== min) {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            if (max === r) h = ((g - bl) / d + (g < bl ? 6 : 0)) / 6;
            else if (max === g) h = ((bl - r) / d + 2) / 6;
            else h = ((r - g) / d + 4) / 6;
          }
          h = Math.round(h * 360);
          s = Math.round(s * 100);
          l = Math.round(l * 100);
          root.style.setProperty('--primary', `${h} ${s}% ${l}%`);
          root.style.setProperty('--ring', `${h} ${s}% ${l}%`);
        }
        // Set favicon
        if (b.favicon_url) {
          let link = document.querySelector("link[rel~='icon']");
          if (link) link.href = b.favicon_url;
        }
        // Set page title
        if (b.brand_name) {
          document.title = b.brand_name;
        }
      })
      .catch(() => {}); // Ignore errors, use defaults
  }, [API]);

  // Close profile dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setProfileOpen(false);
      }
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

  let allNavItems = [...navItems];
  if (isAdmin) {
    allNavItems = [...allNavItems, ...adminNavItems];
  }
  if (isSuperAdmin) {
    allNavItems = [...allNavItems, ...superAdminNavItems];
  }

  return (
    <div className="min-h-screen flex bg-background">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 sidebar-romance transform transition-transform duration-300 ease-out flex-shrink-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div className="flex flex-col h-screen overflow-hidden">
          {/* Logo */}
          <div className="p-5 border-b border-border/30 flex-shrink-0">
            <Link to="/dashboard" className="flex items-center gap-3">
              {branding?.logo_url ? (
                <img src={branding.logo_url} alt={branding.brand_name || "Logo"} className="w-9 h-9 rounded-xl object-cover shadow-lg" />
              ) : (
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/90 to-primary flex items-center justify-center shadow-lg glow-rose">
                  <Heart className="w-4 h-4 text-white" fill="currentColor" />
                </div>
              )}
              <div>
                <h1 className="font-serif text-lg font-semibold tracking-tight text-foreground">
                  {branding?.brand_name || "TGSubsBot"}
                </h1>
                <p className="text-[10px] text-muted-foreground font-light leading-none">
                  {branding?.tagline || "Premium Subscriptions"}
                </p>
              </div>
            </Link>
          </div>

          {/* Navigation - scrollable */}
          <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto scrollbar-thin">
            {allNavItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                  className={`flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-all duration-150 ${
                    isActive
                      ? "bg-primary/15 text-primary border-l-2 border-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  } ${item.adminOnly ? "border border-dashed border-primary/20" : ""} 
                  ${item.superAdminOnly ? "border border-dashed border-amber-500/30 bg-amber-500/5" : ""}`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                  <span className="truncate">{item.label}</span>
                  {item.superAdminOnly && (
                    <Crown className="w-3 h-3 text-amber-500 ml-auto flex-shrink-0" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Header with Profile */}
        <header className="sticky top-0 z-30 glass border-b border-border/30 flex-shrink-0">
          <div className="flex items-center justify-between px-4 md:px-6 py-3">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden text-foreground hover:bg-primary/10 rounded-xl"
                onClick={() => setSidebarOpen(true)}
                data-testid="mobile-menu-btn"
              >
                <Menu className="w-5 h-5" />
              </Button>
              
              <h2 className="font-serif text-lg font-medium text-foreground hidden md:block">
                {allNavItems.find(item => item.path === location.pathname)?.label || "Dashboard"}
              </h2>
            </div>
            
            <div className="flex items-center gap-4">
              <p className="text-sm text-muted-foreground hidden sm:block">
                {new Date().toLocaleDateString("en-IN", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
              </p>
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Online" />

              {/* Profile Dropdown */}
              <div className="relative" ref={profileRef}>
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl hover:bg-muted/50 transition-colors border border-transparent hover:border-border/50"
                  data-testid="profile-dropdown-btn"
                >
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-rose-500/20 to-red-600/20 flex items-center justify-center border border-primary/20">
                    <span className="text-xs font-serif font-semibold text-primary">
                      {user.name?.charAt(0)?.toUpperCase() || "U"}
                    </span>
                  </div>
                  <span className="text-sm font-medium hidden md:block max-w-[120px] truncate">
                    {user.name || "User"}
                  </span>
                  <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${profileOpen ? "rotate-180" : ""}`} />
                </button>

                {/* Dropdown Menu */}
                {profileOpen && (
                  <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-border/50 bg-card shadow-xl py-1 z-50">
                    <div className="px-4 py-3 border-b border-border/30">
                      <p className="text-sm font-medium truncate">{user.name || "User"}</p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    <Link
                      to="/dashboard/profile"
                      onClick={() => setProfileOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-muted/50 transition-colors"
                      data-testid="profile-link"
                    >
                      <User className="w-4 h-4" />
                      Profile
                    </Link>
                    <Link
                      to="/dashboard/settings"
                      onClick={() => setProfileOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-muted/50 transition-colors"
                    >
                      <Settings className="w-4 h-4" />
                      Settings
                    </Link>
                    <div className="border-t border-border/30 mt-1 pt-1">
                      <button
                        onClick={() => { setProfileOpen(false); handleLogout(); }}
                        className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                        data-testid="logout-btn"
                      >
                        <LogOut className="w-4 h-4" />
                        Logout
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page content - ONLY this scrolls */}
        <div className="flex-1 p-4 md:p-6 lg:p-8 overflow-y-auto">
          <div className="max-w-7xl mx-auto pb-8">
            <Outlet />
          </div>
          {branding?.footer_text && (
            <div className="text-center py-3 text-xs text-muted-foreground/50 border-t border-border/20">
              {branding.footer_text}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
