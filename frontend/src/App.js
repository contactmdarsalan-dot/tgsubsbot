import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
import Layout from "./components/Layout";

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
  
  // Check if subscription expired
  if (subStatus === "active" && subEnd) {
    const endDate = new Date(subEnd);
    if (new Date() > endDate) {
      // Subscription expired - show renewal page
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
            // Simple check: if subscription status is undefined/null, might be admin
            // Real check happens on backend
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
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/pricing" element={<PricingRoute />} />
          <Route path="/renew" element={<RenewSubscription />} />
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
            <Route path="automation" element={<Automation />} />
            <Route path="settings" element={<Settings />} />
            <Route path="admin-subs" element={<AdminSubscriptions />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}

export default App;
