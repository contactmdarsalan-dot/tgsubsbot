import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./MiniApp.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";
const tg = window.Telegram?.WebApp;

export default function MiniApp() {
  const [user, setUser] = useState(null);
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("plans");
  const [selectedPlan, setSelectedPlan] = useState(null);

  // Phone Login
  const [phoneScreen, setPhoneScreen] = useState(true);
  const [phoneNum, setPhoneNum] = useState("");
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [loginDiscount, setLoginDiscount] = useState(0);
  const [discountPopup, setDiscountPopup] = useState(false);

  // Coupon
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState(null);
  const [couponLoading, setCouponLoading] = useState(false);

  // Manual payment sheet
  const [showManualSheet, setShowManualSheet] = useState(false);
  const [upiDetails, setUpiDetails] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);

  // Referral
  const [referralCode, setReferralCode] = useState("");
  const [applyRefCode, setApplyRefCode] = useState("");
  const [referralData, setReferralData] = useState(null);
  const [referralMsg, setReferralMsg] = useState("");

  // Payment history
  const [payments, setPayments] = useState([]);

  // Notifications
  const [notifications, setNotifications] = useState([]);

  // Support chat
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);
  const sessionIdRef = useRef(`support-${Date.now()}`);

  // Admin Panel
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminPerms, setAdminPerms] = useState([]);
  const [adminName, setAdminName] = useState("");
  const [adminStats, setAdminStats] = useState(null);
  const [pendingPayments, setPendingPayments] = useState([]);
  const [adminSubs, setAdminSubs] = useState([]);
  const [liveSessions, setLiveSessions] = useState([]);
  const [broadcastMsg, setBroadcastMsg] = useState("");
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminSubTab, setAdminSubTab] = useState("stats");
  const [showCreateLive, setShowCreateLive] = useState(false);
  const [newLive, setNewLive] = useState({ title: "", description: "", scheduled_date: "", scheduled_time: "", price: 0, stream_link: "", max_viewers: 100, superchat_enabled: false, superchat_min_amount: 50 });
  const [paidPosts, setPaidPosts] = useState([]);
  const [showCreatePost, setShowCreatePost] = useState(false);
  const [newPost, setNewPost] = useState({ caption: "", price: 0, blur_level: 10, channel_id: "", content_type: "text" });
  const [postMediaFile, setPostMediaFile] = useState(null);
  const [postMediaPreview, setPostMediaPreview] = useState(null);
  const postFileRef = useRef(null);

  // Payment
  const [payProcessing, setPayProcessing] = useState(false);
  const [paySuccess, setPaySuccess] = useState(null);
  const [screenshotFile, setScreenshotFile] = useState(null);
  const [screenshotPreview, setScreenshotPreview] = useState(null);
  const [uploadStep, setUploadStep] = useState(null); // null | "pick" | "uploading" | "result"
  const [uploadResult, setUploadResult] = useState(null);
  const fileInputRef = useRef(null);

  // More menu
  const [moreOpen, setMoreOpen] = useState(false);

  // Live sessions (user view)
  const [publicLiveSessions, setPublicLiveSessions] = useState([]);
  const [liveTicketFile, setLiveTicketFile] = useState(null);
  const [liveTicketPreview, setLiveTicketPreview] = useState(null);
  const [liveTicketUploading, setLiveTicketUploading] = useState(false);
  const [liveTicketResult, setLiveTicketResult] = useState(null);
  const [selectedLiveSession, setSelectedLiveSession] = useState(null);
  const liveFileInputRef = useRef(null);

  const getTelegramUser = useCallback(() => {
    if (tg?.initDataUnsafe?.user) return tg.initDataUnsafe.user;
    // Fallback for testing: ?tg_id=123456789
    const params = new URLSearchParams(window.location.search);
    const testId = params.get("tg_id");
    if (testId) return { id: parseInt(testId), first_name: params.get("tg_name") || "Tester" };
    return null;
  }, []);

  const userId = getTelegramUser()?.id?.toString() || "";

  // Tenant context from URL
  const tenantParam = new URLSearchParams(window.location.search).get("tenant") || "";

  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
      tg.setHeaderColor("#0e0e0e");
      tg.setBackgroundColor("#0e0e0e");
    }
    checkUserAndFetch();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const checkUserAndFetch = async () => {
    try {
      const tgUser = getTelegramUser();
      if (tgUser) setUser(tgUser);
      const uid = tgUser?.id?.toString() || "";

      // Check if user already logged in with phone
      if (uid) {
        const discRes = await fetch(`${API}/miniapp/user-discount/${uid}`);
        const discData = await discRes.json();
        if (discData.has_discount) {
          setLoginDiscount(discData.discount_percent);
          setPhoneScreen(false);
        }
      }

      await fetchData();
      
      // Check if user is admin
      if (uid) {
        try {
          const adminRes = await fetch(`${API}/miniapp/admin/check/${uid}`);
          const adminData = await adminRes.json();
          if (adminData.is_admin) {
            setIsAdmin(true);
            setAdminPerms(adminData.permissions || []);
            setAdminName(adminData.name || "Admin");
          }
        } catch (e) { console.error("Admin check error:", e); }
      }
    } catch (err) {
      console.error("Init error:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchData = async () => {
    try {
      const tgUser = getTelegramUser();
      const uid = tgUser?.id?.toString() || "";
      const [plansRes, subRes, notifRes] = await Promise.all([
        fetch(`${API}/miniapp/plans`),
        uid ? fetch(`${API}/miniapp/status/${uid}`) : null,
        uid ? fetch(`${API}/miniapp/notifications/${uid}`) : null,
      ]);
      const plansData = await plansRes.json();
      setPlans(plansData || []);
      if (subRes) setSubscription(await subRes.json());
      if (notifRes) setNotifications((await notifRes.json()) || []);
    } catch (err) {
      console.error("Fetch error:", err);
    }
  };

  // ---- Phone Login ----
  const handlePhoneLogin = async () => {
    if (phoneLoading || phoneNum.length < 10) return;
    setPhoneLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/phone-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phoneNum,
          telegram_user_id: userId,
          telegram_username: user?.username || "",
        }),
      });
      const data = await res.json();
      if (data.success) {
        setLoginDiscount(data.discount);
        setPhoneScreen(false);
        setDiscountPopup(true);
        setTimeout(() => setDiscountPopup(false), 4000);
      }
    } catch {
      // ignore
    } finally {
      setPhoneLoading(false);
    }
  };

  const handleSkipLogin = () => {
    setPhoneScreen(false);
  };

  // ---- Coupon ----
  const applyCoupon = async () => {
    if (!couponCode.trim() || !selectedPlan) return;
    setCouponLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/apply-coupon`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: couponCode,
          plan_id: selectedPlan.id,
          amount: selectedPlan.price,
        }),
      });
      setCouponResult(await res.json());
    } catch {
      setCouponResult({ valid: false, error: "Network error" });
    } finally {
      setCouponLoading(false);
    }
  };

  const getPayAmount = () => {
    let base = selectedPlan?.price || 0;
    if (couponResult?.valid) base = couponResult.final_amount;
    if (loginDiscount > 0) {
      base = Math.max(1, Math.round(base - (base * loginDiscount) / 100));
    }
    return base;
  };

  // ---- Razorpay ----
  const handleRazorpay = async () => {
    if (!selectedPlan || payProcessing) return;
    setPayProcessing(true);
    try {
      const res = await fetch(`${API}/miniapp/create-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_id: selectedPlan.id,
          telegram_user_id: userId,
          telegram_username: user?.username || "",
          amount: getPayAmount(),
          coupon_code: couponResult?.valid ? couponResult.coupon_code : null,
        }),
      });
      const order = await res.json();
      if (order.order_id) {
        const options = {
          key: order.key_id,
          amount: order.amount * 100,
          currency: order.currency || "INR",
          name: "TGSubsBot",
          description: `${order.plan_name} Subscription`,
          order_id: order.order_id,
          handler: async (response) => {
            try {
              const vRes = await fetch(`${API}/miniapp/verify-payment`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature,
                  telegram_user_id: userId,
                }),
              });
              const result = await vRes.json();
              if (result.success) { setPaySuccess(result); fetchData(); }
              else alert("Payment verification failed");
            } catch { alert("Verification error"); }
            finally { setPayProcessing(false); }
          },
          prefill: { name: user?.first_name || "", contact: phoneNum || "" },
          theme: { color: "#e8365d" },
          modal: { ondismiss: () => setPayProcessing(false) },
        };
        const rzp = new window.Razorpay(options);
        rzp.open();
      } else {
        alert(order.detail || "Failed to create order");
        setPayProcessing(false);
      }
    } catch {
      alert("Payment error. Try again.");
      setPayProcessing(false);
    }
  };

  // ---- Manual Payment (UPI QR + ID) ----
  const handlePayNow = async () => {
    if (!upiDetails) {
      setQrLoading(true);
      try {
        const res = await fetch(`${API}/miniapp/upi-details`);
        const data = await res.json();
        // Construct full QR URL if relative path
        if (data.qr_code_url && !data.qr_code_url.startsWith("http")) {
          const base = process.env.REACT_APP_BACKEND_URL.replace(/\/api\/?$/, "");
          data.qr_code_url = `${base}${data.qr_code_url}`;
        }
        setUpiDetails(data);
      } catch {
        setUpiDetails({ upi_id: "N/A", qr_code_url: "", payment_message: "Contact admin for UPI details." });
      } finally {
        setQrLoading(false);
      }
    }
    setShowManualSheet(true);
  };

  // Copy to clipboard (works in Telegram WebApp too)
  const copyToClipboard = (text) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        if (tg) tg.showAlert("Copied: " + text);
      }).catch(() => fallbackCopy(text));
    } else {
      fallbackCopy(text);
    }
  };
  const fallbackCopy = (text) => {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;top:-9999px;left:-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    if (tg) tg.showAlert("Copied: " + text);
  };

  const confirmManualPay = () => {
    // Instead of closing, show screenshot upload step
    setUploadStep("pick");
    setScreenshotFile(null);
    setScreenshotPreview(null);
    setUploadResult(null);
  };

  const handleScreenshotSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      if (tg) tg.showAlert("Please select an image file");
      return;
    }
    setScreenshotFile(file);
    setScreenshotPreview(URL.createObjectURL(file));
  };

  const uploadScreenshot = async () => {
    if (!screenshotFile || !selectedPlan) return;
    setUploadStep("uploading");
    
    const formData = new FormData();
    formData.append("file", screenshotFile);
    formData.append("telegram_user_id", userId);
    formData.append("plan_id", selectedPlan.id);
    formData.append("plan_name", selectedPlan.name);
    formData.append("amount", getPayAmount());
    
    try {
      const res = await fetch(`${API}/miniapp/upload-screenshot`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setUploadResult(data);
      setUploadStep("result");
    } catch (e) {
      setUploadResult({ success: false, error: "Upload failed. Try again." });
      setUploadStep("result");
    }
  };

  // ---- Support Chat ----
  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", message: msg, created_at: new Date().toISOString() }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/support/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, message: msg, session_id: sessionIdRef.current }),
      });
      const data = await res.json();
      setChatMessages((prev) => [...prev, { role: "assistant", message: data.reply, escalated: data.escalated, created_at: new Date().toISOString() }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", message: "Sorry, couldn't connect. Try again.", created_at: new Date().toISOString() }]);
    } finally {
      setChatLoading(false);
    }
  };

  // ---- Referral ----
  const fetchReferral = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${API}/miniapp/referral/${userId}`);
      const data = await res.json();
      setReferralData(data);
      setReferralCode(data.referral_code || "");
    } catch (e) { console.error(e); }
  };

  const applyReferral = async () => {
    if (!applyRefCode.trim()) return;
    try {
      const res = await fetch(`${API}/miniapp/referral/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: applyRefCode, telegram_user_id: userId }),
      });
      const data = await res.json();
      setReferralMsg(data.valid ? data.message : data.error);
    } catch { setReferralMsg("Network error"); }
  };

  // ---- Payment History ----
  const fetchPayments = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${API}/miniapp/payments/${userId}`);
      setPayments((await res.json()) || []);
    } catch (e) { console.error(e); }
  };

  const switchTab = (tab) => {
    setActiveTab(tab);
    setMoreOpen(false);
    if (tab === "referral") fetchReferral();
    if (tab === "history") fetchPayments();
    if (tab === "admin") fetchAdminData();
    if (tab === "live") fetchPublicLive();
  };

  const fetchPublicLive = async () => {
    try {
      const res = await fetch(`${API}/miniapp/live-sessions/public`);
      setPublicLiveSessions((await res.json()) || []);
    } catch (e) { console.error(e); }
  };

  const handleLiveTicketUpload = async (session) => {
    if (!liveTicketFile || !session) return;
    setLiveTicketUploading(true);
    setLiveTicketResult(null);
    try {
      const formData = new FormData();
      formData.append("file", liveTicketFile);
      formData.append("telegram_user_id", userId);
      formData.append("session_id", session.id);
      const res = await fetch(`${API}/miniapp/live-ticket/upload-screenshot`, { method: "POST", body: formData });
      const data = await res.json();
      setLiveTicketResult(data);
      if (data.ai_verified) fetchPublicLive();
    } catch (e) {
      setLiveTicketResult({ success: false, error: "Upload failed" });
    } finally {
      setLiveTicketUploading(false);
    }
  };

  // ---- Admin Data ----
  const fetchAdminData = async () => {
    if (!userId) return;
    setAdminLoading(true);
    try {
      const [statsRes, paymentsRes, subsRes, liveRes, postsRes] = await Promise.all([
        fetch(`${API}/miniapp/admin/stats/${userId}`),
        adminPerms.includes("verify_payments") ? fetch(`${API}/miniapp/admin/pending-payments/${userId}`) : null,
        fetch(`${API}/miniapp/admin/subscribers/${userId}`),
        fetch(`${API}/miniapp/admin/live-sessions/${userId}`),
        fetch(`${API}/miniapp/admin/paid-posts/${userId}`),
      ]);
      setAdminStats(await statsRes.json());
      if (paymentsRes) setPendingPayments(await paymentsRes.json());
      setAdminSubs(await subsRes.json());
      setLiveSessions(await liveRes.json());
      if (postsRes) setPaidPosts(await postsRes.json());
    } catch (e) { console.error("Admin fetch error:", e); }
    finally { setAdminLoading(false); }
  };

  const handlePaymentAction = async (paymentId, action) => {
    try {
      const res = await fetch(`${API}/miniapp/admin/payment-action`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, payment_id: paymentId, action }),
      });
      const data = await res.json();
      if (data.success) {
        setPendingPayments(prev => prev.filter(p => p.id !== paymentId));
        setAdminStats(prev => prev ? { ...prev, pending_payments: prev.pending_payments - 1 } : prev);
      }
    } catch (e) { console.error(e); }
  };

  const sendBroadcast = async () => {
    if (!broadcastMsg.trim() || broadcastSending) return;
    setBroadcastSending(true);
    try {
      const res = await fetch(`${API}/miniapp/admin/broadcast`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, message: broadcastMsg }),
      });
      const data = await res.json();
      if (data.success) {
        setBroadcastMsg("");
        alert(`Broadcast sent to ${data.total_recipients} users!`);
      }
    } catch (e) { console.error(e); }
    finally { setBroadcastSending(false); }
  };

  const createLiveSession = async () => {
    if (!newLive.title.trim()) return;
    try {
      const res = await fetch(`${API}/miniapp/admin/live-session`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...newLive, telegram_user_id: userId }),
      });
      const data = await res.json();
      if (data.id) {
        setLiveSessions(prev => [data, ...prev]);
        setShowCreateLive(false);
        setNewLive({ title: "", description: "", scheduled_date: "", scheduled_time: "", price: 0, stream_link: "", max_viewers: 100, superchat_enabled: false, superchat_min_amount: 50 });
      }
    } catch (e) { console.error(e); }
  };

  const announceLive = async (sessionId) => {
    try {
      const res = await fetch(`${API}/miniapp/admin/announce-live/${sessionId}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId }),
      });
      const data = await res.json();
      if (data.success) {
        setLiveSessions(prev => prev.map(s => s.id === sessionId ? { ...s, status: "announced" } : s));
        alert(`Announced to ${data.sent_to} users!`);
      }
    } catch (e) { console.error(e); }
  };

  const goLive = async (sessionId) => {
    try {
      const res = await fetch(`${API}/miniapp/admin/live-session/${sessionId}/go-live`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId }),
      });
      const data = await res.json();
      if (data.success) {
        setLiveSessions(prev => prev.map(s => s.id === sessionId ? { ...s, status: "live" } : s));
        alert(`LIVE! Notified ${data.notified} users`);
      }
    } catch (e) { console.error(e); }
  };

  const createPaidPost = async () => {
    if (!newPost.caption.trim()) return;
    try {
      let res;
      if (postMediaFile) {
        // Upload with file
        const formData = new FormData();
        formData.append("file", postMediaFile);
        formData.append("telegram_user_id", userId);
        formData.append("caption", newPost.caption);
        formData.append("price", newPost.price);
        formData.append("blur_level", newPost.blur_level);
        formData.append("channel_id", newPost.channel_id);
        formData.append("content_type", newPost.content_type);
        res = await fetch(`${API}/miniapp/admin/paid-post-with-media`, { method: "POST", body: formData });
      } else {
        res = await fetch(`${API}/miniapp/admin/paid-post`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...newPost, telegram_user_id: userId }),
        });
      }
      const data = await res.json();
      if (data.id) {
        setPaidPosts(prev => [data, ...prev]);
        setShowCreatePost(false);
        setNewPost({ caption: "", price: 0, blur_level: 10, channel_id: "", content_type: "text" });
        setPostMediaFile(null);
        setPostMediaPreview(null);
      }
    } catch (e) { console.error(e); }
  };

  const togglePost = async (postId) => {
    try {
      const res = await fetch(`${API}/miniapp/admin/paid-post/${postId}/toggle`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId }),
      });
      const data = await res.json();
      if (data.success) {
        setPaidPosts(prev => prev.map(p => p.id === postId ? { ...p, is_active: data.is_active } : p));
      }
    } catch (e) { console.error(e); }
  };

  const broadcastPost = async (postId) => {
    try {
      const res = await fetch(`${API}/miniapp/admin/paid-post/${postId}/broadcast`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId }),
      });
      const data = await res.json();
      if (data.success) alert(`Sent to ${data.sent_to} users!`);
    } catch (e) { console.error(e); }
  };

  const updateBlurLevel = async (postId, blurLevel) => {
    try {
      await fetch(`${API}/miniapp/admin/paid-post/${postId}/blur`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_user_id: userId, blur_level: blurLevel }),
      });
      setPaidPosts(prev => prev.map(p => p.id === postId ? { ...p, blur_level: blurLevel } : p));
    } catch (e) { console.error(e); }
  };

  // ===== LOADING SCREEN =====
  if (loading) {
    return (
      <div className="ma-root" data-testid="miniapp-loading">
        <div className="ma-loader"><div className="ma-spinner" /><p>Loading...</p></div>
      </div>
    );
  }

  // ===== PHONE LOGIN SCREEN =====
  if (phoneScreen) {
    return (
      <div className="ma-root" data-testid="miniapp-phone-screen">
        <div className="ma-login-screen">
          <div className="ma-login-glow" />
          <div className="ma-login-card">
            <div className="ma-login-badge">20% OFF</div>
            <h2>Get 20% Discount</h2>
            <p className="ma-login-sub">Enter your phone number to unlock exclusive 20% discount on all plans</p>
            <div className="ma-login-input-wrap">
              <span className="ma-login-prefix">+91</span>
              <input
                className="ma-login-input"
                type="tel"
                maxLength={10}
                placeholder="Phone number"
                value={phoneNum}
                onChange={(e) => setPhoneNum(e.target.value.replace(/\D/g, ""))}
                onKeyDown={(e) => e.key === "Enter" && handlePhoneLogin()}
                data-testid="miniapp-phone-input"
              />
            </div>
            <button
              className="ma-btn-accent"
              onClick={handlePhoneLogin}
              disabled={phoneLoading || phoneNum.length < 10}
              data-testid="miniapp-phone-submit"
            >
              {phoneLoading ? "..." : "Unlock 20% OFF"}
            </button>
            <button
              className="ma-btn-ghost"
              onClick={handleSkipLogin}
              data-testid="miniapp-phone-skip"
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ===== PAYMENT SUCCESS =====
  if (paySuccess) {
    return (
      <div className="ma-root" data-testid="miniapp-pay-success">
        <div className="ma-success-screen">
          <div className="ma-success-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <h2>Payment Successful!</h2>
          <p className="ma-success-plan">{paySuccess.plan_name}</p>
          <p className="ma-success-amt">&#8377;{paySuccess.amount}</p>
          <p className="ma-success-exp">
            Valid till {new Date(paySuccess.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
          </p>
          <button className="ma-btn-accent" data-testid="miniapp-success-done" onClick={() => { setPaySuccess(null); setSelectedPlan(null); setCouponResult(null); setCouponCode(""); setActiveTab("status"); }}>
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ma-root" data-testid="miniapp-container">
      {/* Discount Popup */}
      <AnimatePresence>
        {discountPopup && (
          <motion.div className="ma-discount-popup" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} data-testid="miniapp-discount-popup">
            <div className="ma-discount-popup-inner">
              <div className="ma-dp-badge">20%</div>
              <h3>Discount Unlocked!</h3>
              <p>You get <strong>20% OFF</strong> on all plans</p>
              <button className="ma-btn-accent sm" onClick={() => setDiscountPopup(false)}>Got it!</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* UPI Payment Bottom Sheet */}
      <AnimatePresence>
        {showManualSheet && (
          <motion.div className="ma-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowManualSheet(false)}>
            <motion.div className="ma-sheet" initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={{ type: "spring", damping: 25 }} onClick={(e) => e.stopPropagation()} data-testid="miniapp-manual-sheet">
              <div className="ma-sheet-handle" />
              
              {/* STEP 1: UPI Details + Pay */}
              {!uploadStep && (
                <>
                  <h3>Pay via UPI</h3>
                  <div className="ma-upi-box">
                    <span className="ma-upi-label">UPI ID</span>
                    <div className="ma-upi-id-row">
                      <span className="ma-upi-id">{upiDetails?.upi_id || "Loading..."}</span>
                      <button className="ma-copy-sm" data-testid="miniapp-copy-upi" onClick={() => copyToClipboard(upiDetails?.upi_id || "")}>Copy</button>
                    </div>
                  </div>
                  {upiDetails?.qr_code_url && (
                    <div className="ma-qr-wrap" data-testid="miniapp-qr-wrap">
                      <img src={upiDetails.qr_code_url} alt="Scan QR to Pay" className="ma-qr-img" data-testid="miniapp-qr-img" />
                    </div>
                  )}
                  <div className="ma-upi-box">
                    <span className="ma-upi-label">Amount</span>
                    <span className="ma-upi-amt">&#8377;{getPayAmount()}</span>
                  </div>
                  <div className="ma-upi-box">
                    <span className="ma-upi-label">Plan</span>
                    <span className="ma-upi-plan">{selectedPlan?.name}</span>
                  </div>
                  <div className="ma-sheet-steps">
                    <p>1. Scan the QR or copy UPI ID above</p>
                    <p>2. Pay &#8377;{getPayAmount()} via any UPI app</p>
                    <p>3. Click below to upload payment screenshot</p>
                  </div>
                  <button className="ma-btn-accent" onClick={confirmManualPay} data-testid="miniapp-manual-confirm">
                    I've Paid, Send Screenshot
                  </button>
                  <button className="ma-btn-ghost" onClick={() => setShowManualSheet(false)}>Cancel</button>
                </>
              )}

              {/* STEP 2: Upload Screenshot */}
              {uploadStep === "pick" && (
                <div className="ma-upload-section" data-testid="miniapp-upload-section">
                  <h3>Upload Payment Screenshot</h3>
                  <p className="ma-subtitle">Select the screenshot of your payment</p>
                  
                  <input type="file" accept="image/*" ref={fileInputRef} onChange={handleScreenshotSelect} style={{ display: "none" }} data-testid="miniapp-file-input" />
                  
                  {screenshotPreview ? (
                    <div className="ma-preview-wrap">
                      <img src={screenshotPreview} alt="Preview" className="ma-preview-img" />
                      <button className="ma-btn-ghost" onClick={() => { setScreenshotFile(null); setScreenshotPreview(null); }}>Change Image</button>
                    </div>
                  ) : (
                    <div className="ma-upload-area" onClick={() => fileInputRef.current?.click()} data-testid="miniapp-upload-area">
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                      <p>Tap to select screenshot</p>
                    </div>
                  )}
                  
                  <div className="ma-upi-box" style={{ marginTop: 10 }}>
                    <span className="ma-upi-label">Plan</span>
                    <span className="ma-upi-plan">{selectedPlan?.name} &middot; &#8377;{getPayAmount()}</span>
                  </div>
                  
                  <button className="ma-btn-accent" onClick={uploadScreenshot} disabled={!screenshotFile} data-testid="miniapp-upload-btn">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                    Upload &amp; Verify
                  </button>
                  <button className="ma-btn-ghost" onClick={() => setUploadStep(null)}>Back</button>
                </div>
              )}

              {/* STEP 3: Uploading */}
              {uploadStep === "uploading" && (
                <div className="ma-upload-section" data-testid="miniapp-uploading">
                  <div className="ma-loader"><div className="ma-spinner" /><p>Verifying payment...</p></div>
                  <p className="ma-subtitle" style={{ textAlign: "center", marginTop: 10 }}>AI is analyzing your screenshot</p>
                </div>
              )}

              {/* STEP 4: Result */}
              {uploadStep === "result" && uploadResult && (
                <div className="ma-upload-section" data-testid="miniapp-upload-result">
                  {uploadResult.ai_verified ? (
                    <div className="ma-result-card verified">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#3ecf8e" strokeWidth="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                      <h3>Payment Verified!</h3>
                      <p>Your subscription is now active</p>
                      {uploadResult.ai_result?.confidence > 0 && <p className="ma-confidence">AI Confidence: {uploadResult.ai_result.confidence}%</p>}
                      {uploadResult.ai_result?.extracted?.amount && <p className="ma-subtitle">Detected: ₹{uploadResult.ai_result.extracted.amount}</p>}
                    </div>
                  ) : uploadResult.success ? (
                    <div className="ma-result-card pending">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ff983e" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                      <h3>Under Review</h3>
                      <p>Admin will verify your payment shortly</p>
                      {uploadResult.ai_result?.reason && <p className="ma-subtitle">{uploadResult.ai_result.reason}</p>}
                    </div>
                  ) : (
                    <div className="ma-result-card failed">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                      <h3>Upload Failed</h3>
                      <p>{uploadResult.error || "Please try again"}</p>
                    </div>
                  )}
                  <button className="ma-btn-accent" onClick={() => { setShowManualSheet(false); setUploadStep(null); }} data-testid="miniapp-done-btn">
                    Done
                  </button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="ma-header">
        <div className="ma-header-left">
          <div className="ma-avatar">{user?.first_name?.[0] || "T"}</div>
          <div>
            <h1 className="ma-brand">TGSubsBot</h1>
            <p className="ma-greeting">{user ? `Hi, ${user.first_name}` : "Premium Subscriptions"}</p>
          </div>
        </div>
        <div className="ma-header-right">
          {loginDiscount > 0 && <span className="ma-discount-pill">{loginDiscount}% OFF</span>}
          {notifications.length > 0 && (
            <button className="ma-notif-btn" data-testid="miniapp-notif-btn" onClick={() => switchTab("notifications")}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
              <span className="ma-notif-dot">{notifications.length}</span>
            </button>
          )}
          {subscription?.is_active && <span className="ma-active-pill">Active</span>}
        </div>
      </div>

      {/* Active Sub Banner */}
      {subscription?.is_active && activeTab !== "status" && (
        <div className="ma-sub-banner" onClick={() => switchTab("status")}>
          <span>{subscription.plan_name}</span>
          <span className="ma-sub-days">{subscription.days_remaining}d left</span>
        </div>
      )}

      {/* Tab Content */}
      <div className="ma-content">
        <AnimatePresence mode="wait">
          {/* ===== PLANS TAB ===== */}
          {activeTab === "plans" && (
            <motion.div key="plans" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-plans-tab">
              <h2 className="ma-title">{subscription?.is_active ? "Extend Subscription" : "Choose Your Plan"}</h2>

              {/* Expiry Warning */}
              {subscription?.is_active && subscription.days_remaining <= 3 && (
                <motion.div className="ma-expiry-warn" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} data-testid="miniapp-expiry-warning">
                  <div className="ma-warn-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#facc15" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  </div>
                  <div>
                    <p className="ma-warn-title">Subscription Expiring Soon!</p>
                    <p className="ma-warn-sub">Only <strong>{subscription.days_remaining}</strong> day{subscription.days_remaining !== 1 ? "s" : ""} left. Renew now to keep access.</p>
                  </div>
                </motion.div>
              )}

              {/* Active Subscription Banner */}
              {subscription?.is_active && subscription.days_remaining > 3 && (
                <div className="ma-extend-banner" data-testid="miniapp-extend-banner">
                  <div className="ma-extend-info">
                    <span className="ma-extend-plan">{subscription.plan_name}</span>
                    <span className="ma-extend-days">{subscription.days_remaining}d remaining</span>
                  </div>
                  <p className="ma-extend-hint">Select a plan below to extend your subscription. New days will be added to your current plan.</p>
                </div>
              )}

              <div className="ma-plans">
                {plans.map((plan, i) => (
                  <React.Fragment key={plan.id}>
                    <motion.div
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.06 }}
                      className={`ma-plan-card ${selectedPlan?.id === plan.id ? "selected" : ""} ${subscription?.plan_id === plan.id ? "current" : ""}`}
                      data-testid={`miniapp-plan-${plan.id}`}
                      onClick={() => { setSelectedPlan(selectedPlan?.id === plan.id ? null : plan); setCouponResult(null); setCouponCode(""); }}
                    >
                      {plan.is_popular && <span className="ma-badge-pop">Popular</span>}
                      {subscription?.plan_id === plan.id && <span className="ma-badge-cur">Current</span>}
                      <div className="ma-plan-top">
                        <h3>{plan.name}</h3>
                        <p className="ma-plan-dur">{plan.duration_days} days</p>
                      </div>
                      <div className="ma-plan-price">
                        <span className="ma-rupee">&#8377;</span>
                        <span className="ma-amt">{plan.price}</span>
                        {loginDiscount > 0 && (
                          <span className="ma-plan-disc">&#8377;{Math.round(plan.price - (plan.price * loginDiscount) / 100)}</span>
                        )}
                      </div>
                      {plan.features?.length > 0 && (
                        <ul className="ma-plan-feats">
                          {plan.features.slice(0, 3).map((f, j) => <li key={j}>{f}</li>)}
                        </ul>
                      )}
                    </motion.div>

                    {/* Payment Section - inline below selected plan */}
                    {selectedPlan?.id === plan.id && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="ma-pay-section" data-testid="miniapp-pay-section">
                        {subscription?.is_active && (
                          <div className="ma-extend-note" data-testid="miniapp-extend-note">
                            <p>+{plan.duration_days} days will be added to your current subscription</p>
                          </div>
                        )}
                        {/* Coupon */}
                        <div className="ma-coupon-row">
                          <input className="ma-input" placeholder="Coupon code" value={couponCode} onChange={(e) => setCouponCode(e.target.value.toUpperCase())} data-testid="miniapp-coupon-input" />
                          <button className="ma-btn-sm" onClick={applyCoupon} disabled={couponLoading} data-testid="miniapp-coupon-apply">{couponLoading ? "..." : "Apply"}</button>
                        </div>
                        {couponResult && (
                          <p className={`ma-msg ${couponResult.valid ? "green" : "red"}`}>
                            {couponResult.valid ? `Coupon: -₹${couponResult.discount}` : couponResult.error}
                          </p>
                        )}

                        <div className="ma-pay-total">
                          <span>Total</span>
                          <span className="ma-pay-final">&#8377;{getPayAmount()}</span>
                        </div>

                        <button className="ma-btn-accent" onClick={handleRazorpay} disabled={payProcessing} data-testid="miniapp-razorpay-btn">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                          {payProcessing ? "Processing..." : subscription?.is_active ? `Extend - Pay ₹${getPayAmount()}` : `Pay ₹${getPayAmount()} Instantly`}
                        </button>
                        <button className="ma-btn-outline" onClick={handlePayNow} disabled={qrLoading} data-testid="miniapp-pay-btn">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/></svg>
                          {qrLoading ? "Loading..." : "UPI Manual Payment"}
                        </button>
                        <p className="ma-pay-hint">Razorpay = instant. UPI = admin verification.</p>
                      </motion.div>
                    )}
                  </React.Fragment>
                ))}
              </div>
            </motion.div>
          )}

          {/* ===== STATUS TAB ===== */}
          {activeTab === "status" && (
            <motion.div key="status" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-status-tab">
              <h2 className="ma-title">Subscription Status</h2>
              {subscription?.is_active ? (
                <div className="ma-status-card active">
                  <div className="ma-status-icon green">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  <h3>Active Subscription</h3>
                  <div className="ma-status-grid">
                    <div className="ma-stat-box"><span className="ma-stat-l">Plan</span><span className="ma-stat-v">{subscription.plan_name}</span></div>
                    <div className="ma-stat-box"><span className="ma-stat-l">Expires</span><span className="ma-stat-v">{subscription.end_date ? new Date(subscription.end_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "N/A"}</span></div>
                    <div className="ma-stat-box full"><span className="ma-stat-l">Days Remaining</span><span className="ma-stat-v big">{subscription.days_remaining}</span></div>
                  </div>
                  <div className="ma-progress"><div className="ma-progress-bar" style={{ width: `${Math.min(100, Math.max(5, ((subscription.days_remaining || 0) / (subscription.total_days || 30)) * 100))}%` }} /></div>
                  <button className="ma-btn-outline" onClick={() => switchTab("plans")} data-testid="miniapp-renew-btn">Renew Plan</button>
                </div>
              ) : (
                <div className="ma-status-card">
                  <div className="ma-status-icon yellow">!</div>
                  <h3>No Active Subscription</h3>
                  <p>Subscribe to a plan to get premium access.</p>
                  <button className="ma-btn-accent" onClick={() => switchTab("plans")} data-testid="miniapp-view-plans-btn">View Plans</button>
                </div>
              )}
            </motion.div>
          )}

          {/* ===== SUPPORT CHAT TAB ===== */}
          {activeTab === "support" && (
            <motion.div key="support" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab ma-support-tab" data-testid="miniapp-support-tab">
              <h2 className="ma-title">Support Chat</h2>
              <div className="ma-chat-box">
                <div className="ma-chat-msgs">
                  {chatMessages.length === 0 && <div className="ma-chat-empty"><p>Ask me anything about plans, payments, or your subscription.</p></div>}
                  {chatMessages.map((msg, i) => (
                    <div key={i} className={`ma-bubble ${msg.role}`} data-testid={`chat-msg-${i}`}>
                      <p>{msg.message}</p>
                      {msg.escalated && <span className="ma-escalated">Forwarded to Admin</span>}
                    </div>
                  ))}
                  {chatLoading && <div className="ma-bubble assistant typing"><span className="ma-dot" /><span className="ma-dot" /><span className="ma-dot" /></div>}
                  <div ref={chatEndRef} />
                </div>
                <div className="ma-chat-bar">
                  <input className="ma-chat-input" placeholder="Type your question..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendChatMessage()} data-testid="miniapp-chat-input" />
                  <button className="ma-chat-send" onClick={sendChatMessage} disabled={chatLoading || !chatInput.trim()} data-testid="miniapp-chat-send">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* ===== PAYMENT HISTORY ===== */}
          {activeTab === "history" && (
            <motion.div key="history" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-history-tab">
              <h2 className="ma-title">Payment History</h2>
              {payments.length === 0 ? <div className="ma-empty"><p>No payments yet</p></div> : (
                <div className="ma-list">{payments.map((p, i) => (
                  <div key={p.id || i} className="ma-list-item" data-testid={`payment-${i}`}>
                    <div className="ma-list-left">
                      <span className={`ma-st-dot ${p.status}`}>{p.status === "verified" ? "✓" : p.status === "pending" ? "◷" : "✗"}</span>
                      <div><p className="ma-list-title">{p.plan_name || "Plan"}</p><p className="ma-list-sub">{p.created_at ? new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}{p.payment_method && ` · ${p.payment_method}`}</p></div>
                    </div>
                    <span className="ma-list-amt">&#8377;{p.amount}</span>
                  </div>
                ))}</div>
              )}
            </motion.div>
          )}

          {/* ===== REFERRAL ===== */}
          {activeTab === "referral" && (
            <motion.div key="referral" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-referral-tab">
              <h2 className="ma-title">Referral Program</h2>
              {referralData ? (
                <div className="ma-glass-card">
                  <div className="ma-ref-top">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    <h3>Your Referral Code</h3>
                  </div>
                  <div className="ma-ref-code-box">
                    <span className="ma-ref-code">{referralCode}</span>
                    <button className="ma-copy-sm" onClick={() => { navigator.clipboard?.writeText(referralCode); if (tg) tg.showAlert("Copied!"); }} data-testid="miniapp-ref-copy">Copy</button>
                  </div>
                  <div className="ma-ref-stats">
                    <div><span className="ma-ref-num">{referralData.referred_count}</span><span className="ma-ref-lbl">Referrals</span></div>
                    <div><span className="ma-ref-num">{referralData.referrer_reward}</span><span className="ma-ref-lbl">Your Reward</span></div>
                    <div><span className="ma-ref-num">{referralData.referee_reward}</span><span className="ma-ref-lbl">Friend Gets</span></div>
                  </div>
                  <p className="ma-hint">Share your code. Both of you get a discount!</p>
                </div>
              ) : <div className="ma-loader-small"><div className="ma-spinner" /></div>}
              <div className="ma-ref-apply">
                <h4>Have a referral code?</h4>
                <div className="ma-coupon-row">
                  <input className="ma-input" placeholder="Enter code" value={applyRefCode} onChange={(e) => setApplyRefCode(e.target.value.toUpperCase())} data-testid="miniapp-ref-apply-input" />
                  <button className="ma-btn-sm" onClick={applyReferral} data-testid="miniapp-ref-apply-btn">Apply</button>
                </div>
                {referralMsg && <p className="ma-msg green">{referralMsg}</p>}
              </div>
            </motion.div>
          )}

          {/* ===== NOTIFICATIONS ===== */}
          {activeTab === "notifications" && (
            <motion.div key="notif" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-notif-tab">
              <h2 className="ma-title">Notifications</h2>
              {notifications.length === 0 ? <div className="ma-empty"><p>No notifications</p></div> : (
                <div className="ma-list">{notifications.map((n, i) => (
                  <div key={n.id || i} className={`ma-notif-item ${n.type}`} data-testid={`notif-${i}`}>
                    <div className="ma-notif-icon-wrap">
                      {n.type === "warning" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
                      {n.type === "info" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>}
                      {n.type === "promo" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>}
                    </div>
                    <div><p className="ma-notif-title">{n.title}</p><p className="ma-notif-msg">{n.message}</p></div>
                  </div>
                ))}</div>
              )}
            </motion.div>
          )}

          {/* ===== HELP ===== */}
          {activeTab === "help" && (
            <motion.div key="help" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-help-tab">
              <h2 className="ma-title">How It Works</h2>
              <div className="ma-steps">
                {[
                  { n: "1", t: "Choose a Plan", d: "Browse subscription plans and pick one." },
                  { n: "2", t: "Make Payment", d: "Pay via Razorpay (instant) or UPI screenshot (manual)." },
                  { n: "3", t: "Get Access", d: "Once verified, you're added to the premium channel." },
                  { n: "4", t: "Enjoy & Renew", d: "Access content. Renew before expiry." },
                ].map((s, i) => (
                  <div key={i} className="ma-step">
                    <span className="ma-step-num">{s.n}</span>
                    <div><h4>{s.t}</h4><p>{s.d}</p></div>
                  </div>
                ))}
              </div>
              <h3 className="ma-faq-title">FAQ</h3>
              {[
                { q: "How to subscribe?", a: "Choose a plan, pay via Razorpay (instant) or UPI screenshot (manual), and you're in!" },
                { q: "Payment not verified?", a: "Manual payments need admin review. Wait a bit or contact support." },
                { q: "Can I use a coupon?", a: "Yes! Enter your coupon code on the payment screen." },
                { q: "How does referral work?", a: "Share your code. When your friend subscribes, both get a discount!" },
                { q: "Need more help?", a: "Use Support Chat - our AI assistant is 24/7." },
              ].map((item, i) => (
                <details key={i} className="ma-faq" data-testid={`faq-${i}`}>
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </motion.div>
          )}

          {/* ===== LIVE SESSIONS (User) ===== */}
          {activeTab === "live" && (
            <motion.div key="live" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="ma-tab" data-testid="miniapp-live-tab">
              <h2 className="ma-title">Live Sessions</h2>
              {publicLiveSessions.length === 0 ? <div className="ma-empty"><p>No upcoming live sessions</p></div> : (
                <div className="ma-list">
                  {publicLiveSessions.map((s, i) => (
                    <div key={s.id} className="ma-glass-card" style={{ marginBottom: "12px" }} data-testid={`live-session-${i}`}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div>
                          <p className="ma-list-title" style={{ fontSize: "15px", fontWeight: 600 }}>{s.title || "Live Session"}</p>
                          <p className="ma-list-sub">{s.scheduled_date} {s.scheduled_time && `· ${s.scheduled_time}`}</p>
                        </div>
                        <span className={`ma-badge ${s.status === "live" ? "live" : "scheduled"}`} style={{
                          padding: "3px 10px", borderRadius: "10px", fontSize: "11px", fontWeight: 600,
                          background: s.status === "live" ? "rgba(239,68,68,0.25)" : "rgba(124,58,237,0.2)",
                          color: s.status === "live" ? "#ef4444" : "#a78bfa"
                        }}>{s.status === "live" ? "LIVE" : s.status?.toUpperCase()}</span>
                      </div>
                      {s.description && <p className="ma-list-sub" style={{ marginTop: "6px" }}>{s.description}</p>}
                      <div style={{ marginTop: "10px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ color: "#e0e0e0", fontSize: "14px" }}>{s.price > 0 ? `₹${s.price}` : "FREE"}</span>
                        <span style={{ color: "#aaa", fontSize: "12px" }}>{s.tickets_sold || 0} tickets sold</span>
                      </div>

                      {s.status === "live" && s.stream_link && (
                        <a href={s.stream_link} target="_blank" rel="noopener noreferrer" className="ma-btn-accent" style={{ marginTop: "10px", display: "block", textAlign: "center", textDecoration: "none" }} data-testid={`live-join-${i}`}>Join Stream</a>
                      )}

                      {s.price > 0 && (
                        <div style={{ marginTop: "10px" }}>
                          {selectedLiveSession?.id === s.id ? (
                            <div className="ma-glass-card" style={{ padding: "10px" }}>
                              <p style={{ fontSize: "13px", marginBottom: "8px", color: "#e0e0e0" }}>Upload payment screenshot for ₹{s.price}</p>
                              <input type="file" accept="image/*" ref={liveFileInputRef} style={{ display: "none" }}
                                onChange={(e) => {
                                  const f = e.target.files[0];
                                  if (f) { setLiveTicketFile(f); setLiveTicketPreview(URL.createObjectURL(f)); }
                                }}
                              />
                              {liveTicketPreview && <img src={liveTicketPreview} alt="preview" style={{ width: "100%", maxHeight: "150px", objectFit: "contain", borderRadius: "8px", marginBottom: "8px" }} />}
                              <div style={{ display: "flex", gap: "8px" }}>
                                <button className="ma-btn-ghost" onClick={() => liveFileInputRef.current?.click()} data-testid={`live-pick-file-${i}`}>
                                  {liveTicketFile ? "Change" : "Pick Image"}
                                </button>
                                {liveTicketFile && (
                                  <button className="ma-btn-accent" disabled={liveTicketUploading} onClick={() => handleLiveTicketUpload(s)} data-testid={`live-upload-${i}`}>
                                    {liveTicketUploading ? "Verifying..." : "Upload & Verify"}
                                  </button>
                                )}
                              </div>
                              {liveTicketResult && (
                                <div style={{ marginTop: "10px", padding: "8px", borderRadius: "8px", background: liveTicketResult.ai_verified ? "rgba(34,197,94,0.15)" : "rgba(250,204,21,0.15)" }}>
                                  <p style={{ fontSize: "13px", fontWeight: 600, color: liveTicketResult.ai_verified ? "#22c55e" : "#facc15" }}>
                                    {liveTicketResult.ai_verified ? "Ticket Approved (AI Verified)" : "Submitted for Review"}
                                  </p>
                                  {liveTicketResult.ai_result?.confidence > 0 && <p style={{ fontSize: "11px", color: "#aaa" }}>AI Confidence: {liveTicketResult.ai_result.confidence}%</p>}
                                </div>
                              )}
                            </div>
                          ) : (
                            <button className="ma-btn-ghost" onClick={() => {
                              setSelectedLiveSession(s);
                              setLiveTicketFile(null);
                              setLiveTicketPreview(null);
                              setLiveTicketResult(null);
                            }} data-testid={`live-buy-ticket-${i}`}>
                              Buy Ticket - ₹{s.price}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ===== ADMIN TAB ===== */}
          {activeTab === "admin" && isAdmin && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} data-testid="miniapp-admin-panel">
              <h2 className="ma-title">Admin Panel</h2>
              <p className="ma-subtitle">Welcome, {adminName}</p>

              {/* Admin Sub-Tabs */}
              <div className="ma-admin-tabs" data-testid="admin-sub-tabs">
                {[
                  { id: "stats", label: "Stats", perm: null },
                  ...(adminPerms.includes("broadcast") ? [{ id: "broadcast", label: "Broadcast", perm: "broadcast" }] : []),
                  { id: "live", label: "Live", perm: null },
                  { id: "posts", label: "Paid Posts", perm: null },
                  { id: "subs", label: "Users", perm: null },
                ].map(t => (
                  <button key={t.id} className={`ma-admin-tab ${adminSubTab === t.id ? "active" : ""}`} onClick={() => setAdminSubTab(t.id)} data-testid={`admin-tab-${t.id}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              {adminLoading ? (
                <div className="ma-loader"><div className="ma-spinner" /><p>Loading...</p></div>
              ) : (
                <>
                  {/* STATS */}
                  {adminSubTab === "stats" && adminStats && (
                    <div className="ma-admin-stats" data-testid="admin-stats">
                      <div className="ma-stat-card green">
                        <span className="ma-stat-value">{adminStats.total_revenue?.toLocaleString?.() || 0}</span>
                        <span className="ma-stat-label">Revenue</span>
                      </div>
                      <div className="ma-stat-card blue">
                        <span className="ma-stat-value">{adminStats.active_subscribers}</span>
                        <span className="ma-stat-label">Active Subs</span>
                      </div>
                      <div className="ma-stat-card purple">
                        <span className="ma-stat-value">{adminStats.total_subscribers}</span>
                        <span className="ma-stat-label">Total Users</span>
                      </div>
                      <div className="ma-stat-card orange">
                        <span className="ma-stat-value">{adminStats.pending_payments}</span>
                        <span className="ma-stat-label">Pending</span>
                      </div>
                    </div>
                  )}

                  {/* BROADCAST */}
                  {adminSubTab === "broadcast" && (
                    <div className="ma-admin-broadcast" data-testid="admin-broadcast">
                      <textarea className="ma-input ma-textarea" placeholder="Type your broadcast message..." value={broadcastMsg} onChange={e => setBroadcastMsg(e.target.value)} rows={4} data-testid="broadcast-input" />
                      <button className="ma-btn-accent" onClick={sendBroadcast} disabled={broadcastSending || !broadcastMsg.trim()} data-testid="broadcast-send-btn">
                        {broadcastSending ? "Sending..." : "Send Broadcast"}
                      </button>
                      <p className="ma-pay-hint">Message will be sent to all bot users.</p>
                    </div>
                  )}

                  {/* LIVE SESSIONS */}
                  {adminSubTab === "live" && (
                    <div className="ma-admin-list" data-testid="admin-live-sessions">
                      <button className="ma-btn-accent" onClick={() => setShowCreateLive(!showCreateLive)} data-testid="create-live-btn">
                        {showCreateLive ? "Cancel" : "+ New Live Session"}
                      </button>

                      {showCreateLive && (
                        <div className="ma-admin-create-form" data-testid="create-live-form">
                          <input className="ma-input" placeholder="Session Title *" value={newLive.title} onChange={e => setNewLive(p => ({...p, title: e.target.value}))} data-testid="live-title-input" />
                          <textarea className="ma-input ma-textarea" placeholder="Description (optional)" value={newLive.description} onChange={e => setNewLive(p => ({...p, description: e.target.value}))} rows={2} data-testid="live-desc-input" />
                          <div className="ma-form-row">
                            <input className="ma-input" type="date" value={newLive.scheduled_date} onChange={e => setNewLive(p => ({...p, scheduled_date: e.target.value}))} data-testid="live-date-input" />
                            <input className="ma-input" type="time" value={newLive.scheduled_time} onChange={e => setNewLive(p => ({...p, scheduled_time: e.target.value}))} data-testid="live-time-input" />
                          </div>
                          <div className="ma-form-row">
                            <input className="ma-input" type="number" placeholder="Price (0=free)" value={newLive.price} onChange={e => setNewLive(p => ({...p, price: parseInt(e.target.value) || 0}))} data-testid="live-price-input" />
                            <input className="ma-input" type="number" placeholder="Max Viewers" value={newLive.max_viewers} onChange={e => setNewLive(p => ({...p, max_viewers: parseInt(e.target.value) || 100}))} data-testid="live-viewers-input" />
                          </div>
                          <input className="ma-input" placeholder="Stream Link (YouTube/Twitch etc.)" value={newLive.stream_link} onChange={e => setNewLive(p => ({...p, stream_link: e.target.value}))} data-testid="live-link-input" />
                          <div className="ma-toggle-row">
                            <label className="ma-toggle-label">Super Chat</label>
                            <button className={`ma-toggle-btn ${newLive.superchat_enabled ? "on" : ""}`} onClick={() => setNewLive(p => ({...p, superchat_enabled: !p.superchat_enabled}))} data-testid="superchat-toggle">
                              {newLive.superchat_enabled ? "ON" : "OFF"}
                            </button>
                          </div>
                          {newLive.superchat_enabled && (
                            <input className="ma-input" type="number" placeholder="Min Super Chat ₹" value={newLive.superchat_min_amount} onChange={e => setNewLive(p => ({...p, superchat_min_amount: parseInt(e.target.value) || 10}))} data-testid="live-superchat-min" />
                          )}
                          <button className="ma-btn-accent" onClick={createLiveSession} disabled={!newLive.title.trim()} data-testid="save-live-btn">Create Session</button>
                        </div>
                      )}

                      {liveSessions.length === 0 && !showCreateLive ? (
                        <div className="ma-empty">No live sessions yet. Create your first one!</div>
                      ) : liveSessions.map(s => (
                        <div key={s.id} className={`ma-admin-item ${s.status === "live" ? "ma-live-active" : ""}`} data-testid={`live-${s.id}`}>
                          <div className="ma-admin-item-top">
                            <strong>{s.status === "live" && <span className="ma-live-dot" />}{s.title}</strong>
                            <span className={`ma-status-tag ${s.status}`}>{s.status}</span>
                          </div>
                          <p className="ma-admin-item-sub">
                            {s.scheduled_date || "No date"} {s.scheduled_time || ""} &middot; {s.price > 0 ? `₹${s.price}` : "FREE"} &middot; Max: {s.max_viewers || 100}
                          </p>
                          {s.description && <p className="ma-admin-item-desc">{s.description}</p>}
                          <div className="ma-admin-item-meta">
                            {s.stream_link && <span className="ma-meta-tag"><a href={s.stream_link} target="_blank" rel="noreferrer">Stream Link</a></span>}
                            {s.superchat_enabled && <span className="ma-meta-tag accent">SuperChat ₹{s.superchat_min_amount || 50}+</span>}
                            <span className="ma-meta-tag">{s.tickets_sold || 0} tickets</span>
                            {s.started_at && <span className="ma-meta-tag">Started: {s.started_at.split("T")[0]}</span>}
                          </div>
                          <div className="ma-admin-actions">
                            {s.status === "scheduled" && (
                              <>
                                <button className="ma-btn-approve" onClick={() => announceLive(s.id)} data-testid={`announce-${s.id}`}>Announce</button>
                                <button className="ma-btn-go-live" onClick={() => goLive(s.id)} data-testid={`golive-${s.id}`}>Go Live</button>
                              </>
                            )}
                            {s.status === "announced" && (
                              <button className="ma-btn-go-live" onClick={() => goLive(s.id)} data-testid={`golive-${s.id}`}>Go Live</button>
                            )}
                            {s.status === "live" && (
                              <>
                                <span className="ma-live-badge">LIVE NOW</span>
                                <button className="ma-btn-end" onClick={async () => {
                                  try {
                                    const res = await fetch(`${API}/miniapp/admin/live-session/${s.id}/end`, {
                                      method: "POST", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify({ telegram_user_id: userId }),
                                    });
                                    if (res.ok) setLiveSessions(prev => prev.map(x => x.id === s.id ? { ...x, status: "ended" } : x));
                                  } catch (e) { console.error(e); }
                                }} data-testid={`end-live-${s.id}`}>End Stream</button>
                              </>
                            )}
                            {(s.status === "ended" || s.status === "scheduled" || s.status === "announced") && (
                              <button className="ma-btn-delete" onClick={async () => {
                                if (!window.confirm("Delete this session?")) return;
                                try {
                                  const res = await fetch(`${API}/miniapp/admin/live-session/${s.id}`, {
                                    method: "DELETE", headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ telegram_user_id: userId }),
                                  });
                                  if (res.ok) setLiveSessions(prev => prev.filter(x => x.id !== s.id));
                                } catch (e) { console.error(e); }
                              }} data-testid={`delete-live-${s.id}`}>Delete</button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* PAID POSTS */}
                  {adminSubTab === "posts" && (
                    <div className="ma-admin-list" data-testid="admin-paid-posts">
                      <button className="ma-btn-accent" onClick={() => setShowCreatePost(!showCreatePost)} data-testid="create-post-btn">
                        {showCreatePost ? "Cancel" : "+ New Paid Post"}
                      </button>

                      {showCreatePost && (
                        <div className="ma-admin-create-form" data-testid="create-post-form">
                          <textarea className="ma-input ma-textarea" placeholder="Post content / caption..." value={newPost.caption} onChange={e => setNewPost(p => ({...p, caption: e.target.value}))} rows={3} />
                          <div className="ma-form-row">
                            <input className="ma-input" type="number" placeholder="Price (0 = free)" value={newPost.price} onChange={e => setNewPost(p => ({...p, price: parseInt(e.target.value) || 0}))} data-testid="post-price-input" />
                            <input className="ma-input" placeholder="Channel ID" value={newPost.channel_id} onChange={e => setNewPost(p => ({...p, channel_id: e.target.value}))} />
                          </div>
                          <select className="ma-input" value={newPost.content_type} onChange={e => setNewPost(p => ({...p, content_type: e.target.value}))}>
                            <option value="text">Text</option>
                            <option value="photo">Photo</option>
                            <option value="video">Video</option>
                            <option value="document">Document</option>
                          </select>

                          {/* Image/Video Upload */}
                          {(newPost.content_type === "photo" || newPost.content_type === "video") && (
                            <div className="ma-media-upload" data-testid="post-media-upload">
                              <input type="file" ref={postFileRef} style={{ display: "none" }}
                                accept={newPost.content_type === "photo" ? "image/*" : "video/*"}
                                onChange={(e) => {
                                  const f = e.target.files[0];
                                  if (f) {
                                    setPostMediaFile(f);
                                    if (f.type.startsWith("image/")) {
                                      setPostMediaPreview(URL.createObjectURL(f));
                                    } else {
                                      setPostMediaPreview("video");
                                    }
                                  }
                                }}
                              />
                              {postMediaPreview && postMediaPreview !== "video" ? (
                                <div className="ma-media-preview">
                                  <img src={postMediaPreview} alt="preview" style={{ width: "100%", maxHeight: "180px", objectFit: "contain", borderRadius: "8px" }} />
                                  <button className="ma-media-remove" onClick={() => { setPostMediaFile(null); setPostMediaPreview(null); }}>Remove</button>
                                </div>
                              ) : postMediaPreview === "video" && postMediaFile ? (
                                <div className="ma-media-preview">
                                  <div style={{ padding: "16px", textAlign: "center", background: "rgba(255,255,255,0.04)", borderRadius: "8px" }}>
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ec4899" strokeWidth="1.5"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                                    <p style={{ color: "#ccc", fontSize: "12px", marginTop: "6px" }}>{postMediaFile.name}</p>
                                    <p style={{ color: "#888", fontSize: "11px" }}>{(postMediaFile.size / 1024 / 1024).toFixed(1)} MB</p>
                                  </div>
                                  <button className="ma-media-remove" onClick={() => { setPostMediaFile(null); setPostMediaPreview(null); }}>Remove</button>
                                </div>
                              ) : (
                                <button className="ma-btn-ghost ma-upload-btn" onClick={() => postFileRef.current?.click()} data-testid="post-pick-media">
                                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                                  {newPost.content_type === "photo" ? "Upload Image" : "Upload Video"}
                                </button>
                              )}
                            </div>
                          )}

                          <div className="ma-blur-control">
                            <label>Blur Level: <strong>{newPost.blur_level}</strong></label>
                            <input type="range" min="0" max="50" value={newPost.blur_level} onChange={e => setNewPost(p => ({...p, blur_level: parseInt(e.target.value)}))} className="ma-range" />
                            <div className="ma-blur-labels"><span>None</span><span>Heavy</span></div>
                          </div>
                          <button className="ma-btn-accent" onClick={createPaidPost} disabled={!newPost.caption.trim()} data-testid="save-post-btn">Create Post</button>
                        </div>
                      )}

                      {paidPosts.length === 0 && !showCreatePost ? (
                        <div className="ma-empty">No paid posts yet</div>
                      ) : paidPosts.map(p => (
                        <div key={p.id} className="ma-admin-item" data-testid={`post-${p.id}`}>
                          <div className="ma-admin-item-top">
                            <strong className="ma-post-caption">{p.caption?.substring(0, 60) || "Untitled"}{p.caption?.length > 60 ? "..." : ""}</strong>
                            <span className={`ma-status-tag ${p.is_active ? "active" : "completed"}`}>{p.is_active ? "Active" : "Off"}</span>
                          </div>
                          <p className="ma-admin-item-sub">
                            {p.price > 0 ? `₹${p.price}` : "FREE"} &middot; {p.content_type || "text"} &middot; {p.unlock_count || 0} unlocks
                          </p>
                          <div className="ma-admin-item-meta">
                            <span className="ma-meta-tag">Blur: {p.blur_level ?? 10}</span>
                            {p.channel_id && <span className="ma-meta-tag">Ch: {p.channel_id}</span>}
                            {p.original_file_id && <span className="ma-meta-tag accent">Has Media</span>}
                          </div>
                          <div className="ma-blur-control compact">
                            <input type="range" min="0" max="50" value={p.blur_level ?? 10} onChange={e => updateBlurLevel(p.id, parseInt(e.target.value))} className="ma-range" />
                          </div>
                          <div className="ma-admin-actions">
                            <button className={p.is_active ? "ma-btn-reject" : "ma-btn-approve"} onClick={() => togglePost(p.id)} data-testid={`toggle-${p.id}`}>
                              {p.is_active ? "Deactivate" : "Activate"}
                            </button>
                            {p.is_active && <button className="ma-btn-approve" onClick={() => broadcastPost(p.id)} data-testid={`broadcast-post-${p.id}`}>Broadcast</button>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* SUBSCRIBERS */}
                  {adminSubTab === "subs" && (
                    <div className="ma-admin-list" data-testid="admin-subs-list">
                      <p className="ma-subtitle">{adminSubs.length} subscribers</p>
                      {adminSubs.map((s, i) => (
                        <div key={i} className="ma-admin-item" data-testid={`sub-${i}`}>
                          <div className="ma-admin-item-top">
                            <strong>{s.telegram_username || s.telegram_user_id}</strong>
                            <span className={`ma-status-tag ${s.status}`}>{s.status}</span>
                          </div>
                          <p className="ma-admin-item-sub">{s.plan_name || "Unknown"} &middot; Paid: ₹{s.amount_paid || 0}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom Navigation */}
      <div className="ma-bottom-nav" data-testid="miniapp-bottom-nav">
        {[
          { id: "plans", label: "Plans", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> },
          { id: "status", label: "Status", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> },
          ...(isAdmin ? [{ id: "admin", label: "Admin", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg> }] : []),
          { id: "live", label: "Live", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> },
          { id: "support", label: "Support", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> },
          { id: "more", label: "More", icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg> },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`ma-nav-btn ${(activeTab === tab.id || (tab.id === "more" && ["referral", "help", "notifications", "live"].includes(activeTab))) ? "active" : ""}`}
            data-testid={`miniapp-nav-${tab.id}`}
            onClick={() => tab.id === "more" ? setMoreOpen(!moreOpen) : switchTab(tab.id)}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* More Menu */}
      <AnimatePresence>
        {moreOpen && (
          <motion.div className="ma-more-menu" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }} data-testid="miniapp-more-menu">
            {[
              { id: "referral", label: "Referral Program", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> },
              { id: "notifications", label: "Notifications", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg> },
              { id: "help", label: "Help & FAQ", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> },
            ].map((item) => (
              <button key={item.id} className="ma-more-item" data-testid={`miniapp-more-${item.id}`} onClick={() => switchTab(item.id)}>
                {item.icon}
                <span>{item.label}</span>
                {item.id === "notifications" && notifications.length > 0 && <span className="ma-more-badge">{notifications.length}</span>}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
