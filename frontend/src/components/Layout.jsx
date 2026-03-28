import { useState, useEffect } from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
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
} from "lucide-react";
import { Button } from "./ui/button";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/dashboard/plans", label: "Plans", icon: Package },
  { path: "/dashboard/subscribers", label: "Subscribers", icon: Users },
  { path: "/dashboard/payments", label: "Payments", icon: CreditCard },
  { path: "/dashboard/revenue", label: "Revenue", icon: IndianRupee },
  { path: "/dashboard/paid-posts", label: "Paid Posts", icon: Lock },
  { path: "/dashboard/live-stream", label: "Live", icon: Radio },
  { path: "/dashboard/creators", label: "Creators", icon: Sparkles },
  { path: "/dashboard/chat-groups", label: "Groups", icon: MessagesSquare },
  { path: "/dashboard/broadcast", label: "Broadcast", icon: Radio },
  { path: "/dashboard/coupons", label: "Coupons", icon: Ticket },
  { path: "/dashboard/referrals", label: "Referrals", icon: Share2 },
  { path: "/dashboard/faqs", label: "FAQs", icon: HelpCircle },
  { path: "/dashboard/video-calls", label: "Video Calls", icon: Video },
  { path: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/dashboard/automation", label: "Automation", icon: Bell },
  { path: "/dashboard/settings", label: "Settings", icon: Settings },
  { path: "/dashboard/support", label: "Support", icon: MessageSquare },
];

const adminNavItems = [
  { path: "/dashboard/admin-subs", label: "SaaS Subs", icon: Crown, adminOnly: true },
];

const superAdminNavItems = [
  { path: "/dashboard/super-admin", label: "Admin Support", icon: Shield, superAdminOnly: true },
  { path: "/dashboard/user-management", label: "User Management", icon: Users, superAdminOnly: true },
];

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");

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

      {/* Sidebar - Romance Theme */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-72 sidebar-romance transform transition-transform duration-300 ease-out ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-border/30">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-rose-600 to-red-700 flex items-center justify-center shadow-lg glow-rose">
                <Heart className="w-5 h-5 text-white" fill="currentColor" />
              </div>
              <div>
                <h1 className="font-serif text-xl font-semibold tracking-tight text-foreground">
                  TGSubsBot
                </h1>
                <p className="text-xs text-muted-foreground font-light">
                  Premium Subscriptions
                </p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {allNavItems.map((item, index) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                  className={`nav-item flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? "active bg-primary/15 text-primary border-l-2 border-primary"
                      : "text-muted-foreground hover:text-foreground"
                  } ${item.adminOnly ? "border border-dashed border-primary/20 rounded-xl" : ""} 
                  ${item.superAdminOnly ? "border border-dashed border-amber-500/30 bg-amber-500/5 rounded-xl" : ""}
                  opacity-0 animate-fade-in-up stagger-${Math.min(index + 1, 5)}`}
                  style={{ animationFillMode: 'forwards' }}
                >
                  <Icon className="w-5 h-5" strokeWidth={1.5} />
                  <span>{item.label}</span>
                  {item.superAdminOnly && (
                    <Crown className="w-3 h-3 text-amber-500 ml-auto" />
                  )}
                </Link>
              );
            })}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-border/30">
            <div className="romance-card p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500/20 to-red-600/20 flex items-center justify-center border border-primary/20">
                  <span className="text-sm font-serif font-semibold text-primary">
                    {user.name?.charAt(0)?.toUpperCase() || "U"}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate text-foreground">{user.name || "User"}</p>
                  <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  data-testid="logout-btn"
                  className="text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-xl transition-all duration-200"
                >
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/30">
          <div className="flex items-center justify-between px-6 py-4">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden text-foreground hover:bg-primary/10 rounded-xl"
              onClick={() => setSidebarOpen(true)}
              data-testid="mobile-menu-btn"
            >
              <Menu className="w-5 h-5" />
            </Button>
            
            <div className="flex-1 flex items-center justify-center lg:justify-start lg:ml-4">
              <h2 className="font-serif text-lg font-medium text-foreground hidden md:block">
                {navItems.find(item => item.path === location.pathname)?.label || 
                 adminNavItems.find(item => item.path === location.pathname)?.label ||
                 superAdminNavItems.find(item => item.path === location.pathname)?.label ||
                 "Dashboard"}
              </h2>
            </div>
            
            <div className="flex items-center gap-4">
              <p className="text-sm text-muted-foreground hidden sm:block">
                {new Date().toLocaleDateString("en-IN", {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                })}
              </p>
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="System Online" />
            </div>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 p-4 md:p-6 lg:p-8 overflow-y-auto">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
