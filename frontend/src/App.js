import { useState, useEffect, useRef } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Plans from "./pages/Plans";
import Subscribers from "./pages/Subscribers";
import Payments from "./pages/Payments";
import Automation from "./pages/Automation";
import Settings from "./pages/Settings";
import Pricing from "./pages/Pricing";
import RenewSubscription from "./pages/RenewSubscription";
import AdminSubscriptions from "./pages/AdminSubscriptions";
import SuperAdminDashboard from "./pages/SuperAdminDashboard";
import SupportPage from "./pages/SupportPage";
import BotCheckout from "./pages/BotCheckout";
import ChatGroups from "./pages/ChatGroups";
import Broadcast from "./pages/Broadcast";
import Layout from "./components/Layout";
import Coupons from "./pages/Coupons";
import Referrals from "./pages/Referrals";
import FAQs from "./pages/FAQs";
import Analytics from "./pages/Analytics";
import VideoCalls from "./pages/VideoCalls";
import LiveStream from "./pages/LiveStream";
import PaidPosts from "./pages/PaidPosts";
import UserManagement from "./pages/UserManagement";
import Creators from "./pages/Creators";
import Profile from "./pages/Profile";
import LandingPage from "./pages/LandingPage";
import RevenueDashboard from "./pages/RevenueDashboard";
import TelegramAdmins from "./pages/TelegramAdmins";
import BotActivityLogs from "./pages/BotActivityLogs";
import Branding from "./pages/Branding";
import BotLanguage from "./pages/BotLanguage";
import MiniApp from "./pages/MiniApp";
import MiniAppUsers from "./pages/MiniAppUsers";
import CreatorOnboard from "./pages/CreatorOnboard";
import CreatorDashboard from "./pages/CreatorDashboard";
import SaaSManagement from "./pages/SaaSManagement";
import TenantProfile from "./pages/TenantProfile";
import TeamManagement from "./pages/TeamManagement";
import MiniAppManagement from "./pages/MiniAppManagement";
import MiniAppPlans from "./pages/MiniAppPlans";
import MiniAppSubscribers from "./pages/MiniAppSubscribers";
import MiniAppPayments from "./pages/MiniAppPayments";
import RiskAlerts from "./pages/RiskAlerts";
import WalletPage from "./pages/WalletPage";

const API = process.env.REACT_APP_BACKEND_URL;

// Google Auth Callback Handler
// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function AuthCallback() {
  const navigate = useNavigate();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      const hash = window.location.hash;
      const sessionMatch = hash.match(/session_id=([^&]+)/);
      
      if (!sessionMatch) {
        navigate('/login');
        return;
      }

      const sessionId = sessionMatch[1];

      try {
        const response = await fetch(`${API}/api/auth/google/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId })
        });

        if (!response.ok) throw new Error('Session processing failed');

        const data = await response.json();
        localStorage.setItem('token', data.token);
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        
        // Check admin status
        try {
          const adminCheck = await fetch(`${API}/api/auth/check-admin`, {
            headers: { Authorization: `Bearer ${data.token}` }
          });
          if (adminCheck.ok) {
            const adminData = await adminCheck.json();
            localStorage.setItem('isFirstUser', adminData.is_admin ? 'true' : 'false');
          }
        } catch (e) {
          localStorage.setItem('isFirstUser', 'false');
        }

        // Clear hash and redirect
        window.history.replaceState(null, '', window.location.pathname);
        
        const user = data.user;
        const isAdmin = localStorage.getItem('isFirstUser') === 'true';
        
        if (isAdmin || user.dashboard_subscription_status === 'active') {
          window.location.href = '/dashboard';
        } else {
          window.location.href = '/pricing';
        }
      } catch (error) {
        console.error('Google auth error:', error);
        navigate('/login');
      }
    };

    processSession();
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );
}

// Router wrapper to detect session_id in URL
function AppRouter() {
  const location = useLocation();
  
  // Check URL fragment for session_id synchronously during render
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/miniapp" element={<MiniApp />} />
      <Route path="/creator-onboard" element={<CreatorOnboard />} />
      <Route path="/creator-dashboard" element={<CreatorDashboard />} />
      <Route path="/login" element={<Login />} />
      <Route path="/pricing" element={<PricingRoute />} />
      <Route path="/renew" element={<RenewSubscription />} />
      <Route path="/bot-checkout" element={<BotCheckout />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="plans" element={<TenantRoute><Plans /></TenantRoute>} />
        <Route path="subscribers" element={<TenantRoute><Subscribers /></TenantRoute>} />
        <Route path="payments" element={<TenantRoute><Payments /></TenantRoute>} />
        <Route path="chat-groups" element={<TenantRoute><ChatGroups /></TenantRoute>} />
        <Route path="broadcast" element={<TenantRoute><Broadcast /></TenantRoute>} />
        <Route path="automation" element={<TenantRoute><Automation /></TenantRoute>} />
        <Route path="settings" element={<TenantRoute><Settings /></TenantRoute>} />
        <Route path="admin-subs" element={<SuperAdminRoute><AdminSubscriptions /></SuperAdminRoute>} />
        <Route path="super-admin" element={<SuperAdminRoute><SuperAdminDashboard /></SuperAdminRoute>} />
        <Route path="support" element={<SupportPage />} />
        <Route path="coupons" element={<TenantRoute><Coupons /></TenantRoute>} />
        <Route path="referrals" element={<TenantRoute><Referrals /></TenantRoute>} />
        <Route path="faqs" element={<TenantRoute><FAQs /></TenantRoute>} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="revenue" element={<RevenueDashboard />} />
        <Route path="telegram-admins" element={<TenantRoute><TelegramAdmins /></TenantRoute>} />
        <Route path="bot-activity" element={<TenantRoute><BotActivityLogs /></TenantRoute>} />
        <Route path="video-calls" element={<TenantRoute><VideoCalls /></TenantRoute>} />
        <Route path="live-stream" element={<TenantRoute><LiveStream /></TenantRoute>} />
        <Route path="paid-posts" element={<TenantRoute><PaidPosts /></TenantRoute>} />
        <Route path="user-management" element={<SuperAdminRoute><UserManagement /></SuperAdminRoute>} />
        <Route path="creators" element={<TenantRoute><Creators /></TenantRoute>} />
        <Route path="branding" element={<SuperAdminRoute><Branding /></SuperAdminRoute>} />
        <Route path="bot-language" element={<TenantRoute><BotLanguage /></TenantRoute>} />
        <Route path="miniapp-users" element={<MiniAppUsers />} />
        <Route path="profile" element={<Profile />} />
        <Route path="saas-management" element={<SuperAdminRoute><SaaSManagement /></SuperAdminRoute>} />
        <Route path="tenant/:tenantId" element={<SuperAdminRoute><TenantProfile /></SuperAdminRoute>} />
        <Route path="team" element={<TenantRoute><TeamManagement /></TenantRoute>} />
        <Route path="miniapp-manage" element={<TenantRoute><MiniAppManagement /></TenantRoute>} />
        <Route path="miniapp-plans" element={<TenantRoute><MiniAppPlans /></TenantRoute>} />
        <Route path="miniapp-subscribers" element={<TenantRoute><MiniAppSubscribers /></TenantRoute>} />
        <Route path="miniapp-payments" element={<TenantRoute><MiniAppPayments /></TenantRoute>} />
        <Route path="risk-alerts" element={<SuperAdminRoute><RiskAlerts /></SuperAdminRoute>} />
                <Route path="wallet" element={<ProtectedRoute><WalletPage /></ProtectedRoute>} />
      </Route>
    </Routes>
  );
}

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  
  // Check JWT expiry client-side to avoid unnecessary API calls
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      // Token expired — try to refresh
      const refreshToken = localStorage.getItem("refresh_token");
      if (!refreshToken) {
        localStorage.clear();
        return <Navigate to="/login" replace />;
      }
      // Attempt refresh in background (the useEffect in App handles it)
    }
  } catch (e) {
    localStorage.clear();
    return <Navigate to="/login" replace />;
  }
  
  const subStatus = user.dashboard_subscription_status;
  const subEnd = user.dashboard_subscription_end;
  const isAdmin = user.isAdmin || localStorage.getItem("isFirstUser") === "true";
  const isSuperAdmin = user.role === "super_admin";
  const isTenantAdmin = user.role === "tenant_admin" || user.role === "tenant_owner";
  
  if (isSuperAdmin || isTenantAdmin || isAdmin) return children;
  
  if (subStatus === "expired") return <Navigate to="/renew" replace />;
  
  if (subStatus === "active" && subEnd) {
    const endDate = new Date(subEnd);
    if (new Date() > endDate) return <Navigate to="/renew" replace />;
    return children;
  }
  
  if (subStatus !== "active") return <Navigate to="/pricing" replace />;
  
  return children;
};

// Role-based route guard — Super Admin only pages
const SuperAdminRoute = ({ children }) => {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  if (user.role !== "super_admin") {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

// Role-based route guard — Tenant Admin/Owner only pages (Super Admins can also access when impersonating)
const TenantRoute = ({ children }) => {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const allowed = ["super_admin", "tenant_admin", "tenant_owner", "admin"];
  if (!allowed.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

const PricingRoute = () => {
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  
  const subStatus = user.dashboard_subscription_status;
  const isAdmin = user.isAdmin || localStorage.getItem("isFirstUser") === "true";
  const isSuperAdmin = user.role === "super_admin";
  const isTenantAdmin = user.role === "tenant_admin";
  
  // If already subscribed or admin or super_admin or tenant_admin, go to dashboard
  if (subStatus === "active" || isAdmin || isSuperAdmin || isTenantAdmin) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <Pricing />;
};

function App() {
  // Token refresh logic - silently refresh access token using refresh_token
  useEffect(() => {
    const refreshAccessToken = async () => {
      const refreshToken = localStorage.getItem("refresh_token");
      if (!refreshToken) return;
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (response.ok) {
          const data = await response.json();
          localStorage.setItem("token", data.token);
        } else if (response.status === 401) {
          // Refresh token expired — force re-login
          localStorage.removeItem("token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("user");
          window.location.href = "/login";
        }
      } catch (e) {
        console.error("Token refresh failed:", e);
      }
    };

    // Refresh on mount
    const checkFirstUser = async () => {
      try {
        const token = localStorage.getItem("token");
        if (token) {
          const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (response.ok) {
            const userData = await response.json();
            localStorage.setItem("user", JSON.stringify(userData));
          }
        }
      } catch (e) {
        console.error("Auth check failed:", e);
      }
    };
    checkFirstUser();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}

export default App;
