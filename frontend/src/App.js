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
          window.location.href = '/';
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
      <Route path="/login" element={<Login />} />
      <Route path="/pricing" element={<PricingRoute />} />
      <Route path="/renew" element={<RenewSubscription />} />
      <Route path="/bot-checkout" element={<BotCheckout />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="plans" element={<Plans />} />
        <Route path="subscribers" element={<Subscribers />} />
        <Route path="payments" element={<Payments />} />
        <Route path="chat-groups" element={<ChatGroups />} />
        <Route path="broadcast" element={<Broadcast />} />
        <Route path="automation" element={<Automation />} />
        <Route path="settings" element={<Settings />} />
        <Route path="admin-subs" element={<AdminSubscriptions />} />
        <Route path="super-admin" element={<SuperAdminDashboard />} />
        <Route path="support" element={<SupportPage />} />
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
  
  // Check if user has active subscription
  const subStatus = user.dashboard_subscription_status;
  const subEnd = user.dashboard_subscription_end;
  const isAdmin = user.isAdmin || localStorage.getItem("isFirstUser") === "true";
  
  // Admin gets free access
  if (isAdmin) {
    return children;
  }
  
  // Expired subscription - show renewal page
  if (subStatus === "expired") {
    return <Navigate to="/renew" replace />;
  }
  
  // Check if subscription expired by date
  if (subStatus === "active" && subEnd) {
    const endDate = new Date(subEnd);
    if (new Date() > endDate) {
      return <Navigate to="/renew" replace />;
    }
    return children;
  }
  
  // No subscription - show pricing
  if (subStatus !== "active") {
    return <Navigate to="/pricing" replace />;
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
  
  // If already subscribed or admin, go to dashboard
  if (subStatus === "active" || isAdmin) {
    return <Navigate to="/" replace />;
  }
  
  return <Pricing />;
};

function App() {
  // Check if first user on mount
  useEffect(() => {
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
