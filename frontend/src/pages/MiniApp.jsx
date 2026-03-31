import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./MiniApp.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// Telegram WebApp SDK
const tg = window.Telegram?.WebApp;

export default function MiniApp() {
  const [user, setUser] = useState(null);
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("plans");
  const [selectedPlan, setSelectedPlan] = useState(null);

  // Get Telegram user data
  const getTelegramUser = useCallback(() => {
    if (tg?.initDataUnsafe?.user) {
      return tg.initDataUnsafe.user;
    }
    return null;
  }, []);

  useEffect(() => {
    // Init Telegram WebApp
    if (tg) {
      tg.ready();
      tg.expand();
      tg.setHeaderColor("#0f172a");
      tg.setBackgroundColor("#0f172a");
    }
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const tgUser = getTelegramUser();
      const userId = tgUser?.id || "";

      // Fetch plans
      const plansRes = await fetch(`${API}/miniapp/plans`);
      const plansData = await plansRes.json();
      setPlans(plansData || []);

      // Fetch user subscription status
      if (userId) {
        const subRes = await fetch(`${API}/miniapp/status/${userId}`);
        const subData = await subRes.json();
        setSubscription(subData);
        setUser(tgUser);
      }
    } catch (err) {
      console.error("Failed to fetch:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlan = (plan) => {
    setSelectedPlan(plan);
    setActiveTab("pay");
  };

  const handlePayNow = (plan) => {
    // Send data back to bot to initiate payment
    if (tg) {
      tg.sendData(JSON.stringify({
        action: "select_plan",
        plan_id: plan.id,
        plan_name: plan.name,
        amount: plan.price,
      }));
    }
  };

  if (loading) {
    return (
      <div className="miniapp-container">
        <div className="loading-spinner">
          <div className="spinner" />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="miniapp-container">
      {/* Header */}
      <div className="miniapp-header">
        <div className="header-info">
          <div className="header-avatar">
            {user?.first_name?.[0] || "S"}
          </div>
          <div>
            <h1 className="header-title">TGSubsBot</h1>
            <p className="header-subtitle">
              {user ? `Hi, ${user.first_name}` : "Premium Subscriptions"}
            </p>
          </div>
        </div>
        {subscription?.is_active && (
          <div className="active-badge">Active</div>
        )}
      </div>

      {/* Active Subscription Card */}
      {subscription?.is_active && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="sub-card"
        >
          <div className="sub-card-header">
            <span className="sub-card-icon">&#9733;</span>
            <span className="sub-card-label">Current Plan</span>
          </div>
          <h3 className="sub-card-plan">{subscription.plan_name}</h3>
          <div className="sub-card-details">
            <div className="sub-detail">
              <span className="sub-detail-label">Expires</span>
              <span className="sub-detail-value">
                {subscription.end_date ? new Date(subscription.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "N/A"}
              </span>
            </div>
            <div className="sub-detail">
              <span className="sub-detail-label">Days Left</span>
              <span className="sub-detail-value highlight">
                {subscription.days_remaining || 0}
              </span>
            </div>
          </div>
          <div className="sub-progress-bar">
            <div
              className="sub-progress-fill"
              style={{
                width: `${Math.min(100, Math.max(5, ((subscription.days_remaining || 0) / (subscription.total_days || 30)) * 100))}%`,
              }}
            />
          </div>
        </motion.div>
      )}

      {/* Tab Navigation */}
      <div className="tab-nav">
        {[
          { id: "plans", label: "Plans", icon: "\u{1F4E6}" },
          { id: "status", label: "Status", icon: "\u{1F4CA}" },
          { id: "help", label: "Help", icon: "\u{2753}" },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {/* Plans Tab */}
        {activeTab === "plans" && (
          <motion.div
            key="plans"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="tab-content"
          >
            <h2 className="section-title">Choose Your Plan</h2>
            <div className="plans-grid">
              {plans.map((plan, index) => (
                <motion.div
                  key={plan.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className={`plan-card ${subscription?.plan_id === plan.id ? "current" : ""}`}
                  onClick={() => handleSelectPlan(plan)}
                >
                  {plan.is_popular && <div className="popular-badge">Popular</div>}
                  {subscription?.plan_id === plan.id && <div className="current-badge">Current</div>}
                  <h3 className="plan-name">{plan.name}</h3>
                  <div className="plan-price">
                    <span className="currency">Rs.</span>
                    <span className="amount">{plan.price}</span>
                  </div>
                  <p className="plan-duration">{plan.duration_days} days</p>
                  {plan.features && plan.features.length > 0 && (
                    <ul className="plan-features">
                      {plan.features.slice(0, 3).map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                  )}
                  <button
                    className="plan-select-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectPlan(plan);
                    }}
                  >
                    {subscription?.plan_id === plan.id ? "Renew" : "Select"}
                  </button>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Pay Tab */}
        {activeTab === "pay" && selectedPlan && (
          <motion.div
            key="pay"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="tab-content"
          >
            <h2 className="section-title">Complete Payment</h2>
            <div className="pay-card">
              <div className="pay-plan-info">
                <h3>{selectedPlan.name}</h3>
                <p className="pay-price">Rs.{selectedPlan.price}</p>
                <p className="pay-duration">{selectedPlan.duration_days} days access</p>
              </div>
              <div className="pay-steps">
                <div className="pay-step">
                  <span className="step-num">1</span>
                  <span>Send payment to the UPI ID shown in bot</span>
                </div>
                <div className="pay-step">
                  <span className="step-num">2</span>
                  <span>Take a screenshot of the payment</span>
                </div>
                <div className="pay-step">
                  <span className="step-num">3</span>
                  <span>Send the screenshot to the bot</span>
                </div>
              </div>
              <button className="pay-now-btn" onClick={() => handlePayNow(selectedPlan)}>
                Pay Now - Rs.{selectedPlan.price}
              </button>
              <button className="back-btn" onClick={() => setActiveTab("plans")}>
                Back to Plans
              </button>
            </div>
          </motion.div>
        )}

        {/* Status Tab */}
        {activeTab === "status" && (
          <motion.div
            key="status"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="tab-content"
          >
            <h2 className="section-title">Your Status</h2>
            {subscription?.is_active ? (
              <div className="status-active">
                <div className="status-icon active">&#10003;</div>
                <h3>Subscription Active</h3>
                <p>Plan: <strong>{subscription.plan_name}</strong></p>
                <p>Expires: <strong>{subscription.end_date ? new Date(subscription.end_date).toLocaleDateString("en-IN") : "N/A"}</strong></p>
                <p>Days Left: <strong className="highlight">{subscription.days_remaining}</strong></p>
              </div>
            ) : (
              <div className="status-inactive">
                <div className="status-icon inactive">!</div>
                <h3>No Active Subscription</h3>
                <p>Choose a plan to get started!</p>
                <button className="plan-select-btn" onClick={() => setActiveTab("plans")}>
                  View Plans
                </button>
              </div>
            )}
          </motion.div>
        )}

        {/* Help Tab */}
        {activeTab === "help" && (
          <motion.div
            key="help"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="tab-content"
          >
            <h2 className="section-title">Help & FAQ</h2>
            <div className="help-list">
              {[
                { q: "How to subscribe?", a: "Choose a plan, pay via UPI, and send the screenshot to the bot." },
                { q: "Payment not verified?", a: "Wait for admin verification or send the screenshot again." },
                { q: "How to renew?", a: "Just select your current plan again and make a new payment." },
                { q: "Need help?", a: "Send /help in the bot chat or contact the admin." },
              ].map((item, i) => (
                <div key={i} className="help-item">
                  <h4>{item.q}</h4>
                  <p>{item.a}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
