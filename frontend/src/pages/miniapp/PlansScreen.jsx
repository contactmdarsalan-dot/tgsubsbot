import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useMiniApp, API, copyToClipboard, tg } from "./context";
import { Shield, Check, X, ChevronDown, Upload, Loader2, Sparkles, Camera } from "lucide-react";

export default function PlansScreen() {
  const { plans, selectedPlan, setSelectedPlan, subscription, loginDiscount, userId, user, activeTab, setActiveTab, couponCode, setCouponCode, couponResult, setCouponResult, couponLoading, setCouponLoading, getPayAmount, handleRazorpay, payProcessing, showManualSheet, setShowManualSheet, handlePayNow, upiDetails, setUpiDetails, qrLoading, setQrLoading, uploadStep, setUploadStep, screenshotFile, setScreenshotFile, screenshotPreview, setScreenshotPreview, uploadResult, setUploadResult, paySuccess, setPaySuccess, fetchData } = useMiniApp();
  const fileInputRef = useRef(null);

  const applyCoupon = async () => {
    if (!couponCode.trim() || !selectedPlan) return;
    setCouponLoading(true);
    try {
      const res = await fetch(`${API}/miniapp/apply-coupon`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: couponCode, plan_id: selectedPlan.id, amount: selectedPlan.price }),
      });
      setCouponResult(await res.json());
    } catch { setCouponResult({ valid: false, error: "Network error" }); }
    finally { setCouponLoading(false); }
  };

  const openManualPay = async () => {
    if (!upiDetails) {
      setQrLoading(true);
      try {
        const res = await fetch(`${API}/miniapp/upi-details`);
        const data = await res.json();
        if (data.qr_code_url && !data.qr_code_url.startsWith("http")) {
          data.qr_code_url = `${process.env.REACT_APP_BACKEND_URL.replace(/\/api\/?$/, "")}${data.qr_code_url}`;
        }
        setUpiDetails(data);
      } catch { setUpiDetails({ upi_id: "N/A", qr_code_url: "", payment_message: "Contact admin" }); }
      finally { setQrLoading(false); }
    }
    setShowManualSheet(true);
  };

  const handleScreenshotSelect = (e) => {
    const file = e.target.files[0];
    if (!file || !file.type.startsWith("image/")) return;
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
      const res = await fetch(`${API}/miniapp/upload-screenshot`, { method: "POST", body: formData });
      setUploadResult(await res.json());
      setUploadStep("result");
    } catch { setUploadResult({ success: false, error: "Upload failed" }); setUploadStep("result"); }
  };

  // Payment Success Screen
  if (paySuccess) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center justify-center min-h-[70vh] text-center px-6">
        <div className="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center mb-6">
          <Check className="w-10 h-10 text-emerald-400" />
        </div>
        <h2 className="font-heading text-2xl font-bold text-white mb-2">Access Unlocked!</h2>
        <p className="text-zinc-400 text-sm mb-4">Your {paySuccess.plan_name} subscription is now active</p>
        <div className="glass-card rounded-2xl p-4 w-full max-w-xs mb-6">
          <div className="flex justify-between text-sm mb-2"><span className="text-zinc-500">Plan</span><span className="text-white font-semibold">{paySuccess.plan_name}</span></div>
          <div className="flex justify-between text-sm mb-2"><span className="text-zinc-500">Amount</span><span className="text-white font-semibold">Rs.{paySuccess.amount}</span></div>
          <div className="flex justify-between text-sm"><span className="text-zinc-500">Valid till</span><span className="text-emerald-400 font-semibold">{paySuccess.end_date ? new Date(paySuccess.end_date).toLocaleDateString("en-IN") : "N/A"}</span></div>
        </div>
        <button onClick={() => { setPaySuccess(null); setSelectedPlan(null); fetchData(); setActiveTab("status"); }} className="gradient-cta text-white font-bold rounded-2xl px-8 py-3 text-base active:scale-95 transition-transform" data-testid="success-continue-btn">
          View Subscription
        </button>
      </motion.div>
    );
  }

  // Payment detail screen for selected plan
  if (selectedPlan) {
    return (
      <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="pb-24">
        <button onClick={() => { setSelectedPlan(null); setCouponResult(null); setCouponCode(""); setShowManualSheet(false); setUploadStep(null); }} className="text-zinc-400 text-sm mb-4 flex items-center gap-1 hover:text-white transition-colors" data-testid="back-to-plans-btn">
          <ChevronDown className="w-4 h-4 rotate-90" /> Back to Plans
        </button>

        <div className="glass-card rounded-2xl p-5 mb-4">
          <h3 className="font-heading text-xl font-bold text-white mb-1">{selectedPlan.name}</h3>
          <p className="text-zinc-500 text-sm mb-3">{selectedPlan.duration_days} days access</p>
          <div className="flex items-end gap-2 mb-4">
            <span className="font-mono text-3xl font-bold text-white">Rs.{getPayAmount()}</span>
            {getPayAmount() < selectedPlan.price && <span className="text-sm text-zinc-500 line-through">Rs.{selectedPlan.price}</span>}
          </div>
          {selectedPlan.features?.length > 0 && (
            <div className="space-y-2">
              {selectedPlan.features.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-zinc-300"><Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />{f}</div>
              ))}
            </div>
          )}
        </div>

        {/* Coupon */}
        <div className="glass-card rounded-2xl p-4 mb-4">
          <p className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">Have a coupon?</p>
          <div className="flex gap-2">
            <input type="text" value={couponCode} onChange={e => setCouponCode(e.target.value.toUpperCase())} placeholder="COUPON CODE" className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-rose-500/50" data-testid="coupon-input" />
            <button onClick={applyCoupon} disabled={couponLoading} className="px-4 py-2 bg-white/10 text-white text-sm font-semibold rounded-xl hover:bg-white/20 transition-all disabled:opacity-50" data-testid="apply-coupon-btn">
              {couponLoading ? "..." : "Apply"}
            </button>
          </div>
          {couponResult && (
            <p className={`text-xs mt-2 ${couponResult.valid ? "text-emerald-400" : "text-rose-400"}`}>
              {couponResult.valid ? `Discount applied! Save Rs.${couponResult.discount}` : couponResult.error}
            </p>
          )}
          {loginDiscount > 0 && <p className="text-xs text-purple-400 mt-1">Phone login {loginDiscount}% discount active</p>}
        </div>

        {/* Trust badges */}
        <div className="flex items-center justify-center gap-4 text-xs text-zinc-500 mb-4">
          <div className="flex items-center gap-1"><Shield className="w-3.5 h-3.5" /> Secure Payment</div>
          <div className="flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Instant Access</div>
        </div>

        {/* Payment buttons */}
        <button onClick={handleRazorpay} disabled={payProcessing} className="gradient-cta text-white font-bold rounded-2xl px-6 py-4 w-full text-lg mb-3 active:scale-95 transition-transform disabled:opacity-50 flex items-center justify-center gap-2" data-testid="pay-razorpay-btn">
          {payProcessing ? <><Loader2 className="w-5 h-5 animate-spin" /> Processing...</> : <><Sparkles className="w-5 h-5" /> Pay Rs.{getPayAmount()} - Instant</>}
        </button>
        <button onClick={openManualPay} className="w-full py-3 text-sm font-semibold text-zinc-400 bg-white/5 border border-white/10 rounded-2xl hover:bg-white/10 transition-all" data-testid="pay-upi-btn">
          Pay via UPI (Manual)
        </button>

        {/* Manual Payment Sheet */}
        <AnimatePresence>
          {showManualSheet && (
            <motion.div initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 50 }} className="fixed inset-0 z-50 flex items-end" onClick={e => e.target === e.currentTarget && setShowManualSheet(false)}>
              <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowManualSheet(false)} />
              <motion.div className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl p-5 pb-8" style={{ background: "hsl(340,40%,7%)", border: "1px solid hsl(340,40%,15%)" }}>
                <div className="w-12 h-1 bg-white/20 rounded-full mx-auto mb-5" />
                {uploadStep === "result" ? (
                  <div className="text-center py-6">
                    {uploadResult?.ai_verified ? (
                      <>
                        <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4"><Check className="w-8 h-8 text-emerald-400" /></div>
                        <h3 className="font-heading text-xl font-bold text-white mb-2">Payment Verified!</h3>
                        <p className="text-zinc-400 text-sm mb-4">AI verified your payment. Subscription activated!</p>
                        <button onClick={() => { setShowManualSheet(false); setSelectedPlan(null); fetchData(); setActiveTab("status"); }} className="gradient-cta text-white font-bold rounded-2xl px-6 py-3 active:scale-95 transition-transform" data-testid="verified-continue-btn">View Subscription</button>
                      </>
                    ) : (
                      <>
                        <div className="w-16 h-16 rounded-full bg-amber-500/20 flex items-center justify-center mx-auto mb-4"><Loader2 className="w-8 h-8 text-amber-400" /></div>
                        <h3 className="font-heading text-xl font-bold text-white mb-2">Under Review</h3>
                        <p className="text-zinc-400 text-sm mb-4">Admin will verify your payment shortly</p>
                        <button onClick={() => { setShowManualSheet(false); setSelectedPlan(null); }} className="bg-white/10 text-white font-semibold rounded-2xl px-6 py-3">OK</button>
                      </>
                    )}
                  </div>
                ) : uploadStep === "uploading" ? (
                  <div className="text-center py-10">
                    <Loader2 className="w-10 h-10 animate-spin text-rose-400 mx-auto mb-4" />
                    <p className="text-white font-semibold">Analyzing with AI...</p>
                    <p className="text-xs text-zinc-500 mt-1">Verifying payment screenshot</p>
                  </div>
                ) : uploadStep === "pick" ? (
                  <div className="text-center">
                    <h3 className="font-heading text-lg font-bold text-white mb-4">Upload Payment Screenshot</h3>
                    <input type="file" accept="image/*" ref={fileInputRef} onChange={handleScreenshotSelect} className="hidden" />
                    {screenshotPreview ? (
                      <div className="mb-4"><img src={screenshotPreview} alt="Screenshot" className="max-h-48 mx-auto rounded-xl border border-white/10" /></div>
                    ) : (
                      <button onClick={() => fileInputRef.current?.click()} className="w-full py-10 border-2 border-dashed border-white/10 rounded-2xl text-zinc-500 hover:border-rose-500/30 hover:text-zinc-300 transition-all mb-4" data-testid="select-screenshot-btn">
                        <Camera className="w-8 h-8 mx-auto mb-2" /><span className="text-sm">Tap to select screenshot</span>
                      </button>
                    )}
                    <div className="flex gap-3">
                      {screenshotPreview && (
                        <button onClick={() => fileInputRef.current?.click()} className="flex-1 py-3 bg-white/5 text-zinc-400 rounded-2xl text-sm">Change</button>
                      )}
                      <button onClick={uploadScreenshot} disabled={!screenshotFile} className="flex-1 gradient-cta text-white font-bold rounded-2xl py-3 disabled:opacity-30 active:scale-95 transition-transform" data-testid="upload-screenshot-btn">
                        <Upload className="w-4 h-4 inline mr-2" />Upload & Verify
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <h3 className="font-heading text-lg font-bold text-white mb-3">Pay via UPI</h3>
                    <div className="glass-card rounded-2xl p-4 mb-4 text-center">
                      <p className="font-mono text-2xl font-bold text-white mb-3">Rs.{getPayAmount()}</p>
                      {qrLoading ? (
                        <div className="py-8"><Loader2 className="w-8 h-8 animate-spin text-rose-400 mx-auto" /></div>
                      ) : upiDetails?.qr_code_url ? (
                        <img src={upiDetails.qr_code_url} alt="QR" className="w-48 h-48 mx-auto rounded-xl bg-white p-2 mb-3" />
                      ) : null}
                      {upiDetails?.upi_id && (
                        <button onClick={() => copyToClipboard(upiDetails.upi_id)} className="flex items-center gap-2 mx-auto px-4 py-2 bg-white/5 rounded-xl text-sm text-zinc-300 hover:bg-white/10 transition-colors" data-testid="copy-upi-btn">
                          UPI: <span className="font-mono text-white">{upiDetails.upi_id}</span>
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-zinc-500 text-center mb-4">{upiDetails?.payment_message || "Pay and upload screenshot"}</p>
                    <button onClick={() => { setUploadStep("pick"); setScreenshotFile(null); setScreenshotPreview(null); setUploadResult(null); }} className="gradient-cta text-white font-bold rounded-2xl py-3 w-full active:scale-95 transition-transform" data-testid="paid-upload-btn">
                      I've Paid - Upload Screenshot
                    </button>
                  </>
                )}
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  }

  // Plans list
  return (
    <div className="pb-24">
      <div className="text-center mb-6">
        <h2 className="font-heading text-2xl font-bold text-white mb-1">Choose Your Plan</h2>
        <p className="text-sm text-zinc-500">Unlock exclusive access</p>
      </div>

      {subscription?.is_active && (
        <div className="glass-card rounded-2xl p-4 mb-4 border-emerald-500/20">
          <div className="flex items-center gap-2 mb-1"><Check className="w-4 h-4 text-emerald-400" /><span className="text-sm font-semibold text-emerald-400">Active: {subscription.plan_name}</span></div>
          <p className="text-xs text-zinc-500 ml-6">{subscription.days_remaining} days remaining</p>
        </div>
      )}

      <div className="space-y-3">
        {plans.map((plan, i) => {
          const isPopular = i === 1 || plan.name?.toLowerCase().includes("premium");
          return (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              onClick={() => setSelectedPlan(plan)}
              className={`glass-card rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-all relative ${isPopular ? "border-rose-500/30 ring-1 ring-rose-500/20" : ""}`}
              data-testid={`plan-card-${plan.id}`}
            >
              {isPopular && (
                <div className="absolute -top-2.5 left-4 px-3 py-0.5 bg-gradient-to-r from-rose-500 to-red-600 rounded-full text-[10px] font-bold text-white uppercase tracking-wider">
                  Most Popular
                </div>
              )}
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-heading text-lg font-bold text-white">{plan.name}</h3>
                  <p className="text-xs text-zinc-500 mt-0.5">{plan.duration_days} days</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-2xl font-bold text-white">Rs.{plan.price}</p>
                  {plan.discount_percentage > 0 && <span className="text-xs text-emerald-400 font-semibold">{plan.discount_percentage}% OFF</span>}
                </div>
              </div>
              {plan.features?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {plan.features.slice(0, 3).map((f, j) => (
                    <span key={j} className="text-[11px] px-2 py-0.5 bg-white/5 rounded-full text-zinc-400">{f}</span>
                  ))}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Social proof */}
      <div className="mt-6 text-center">
        <p className="text-xs text-zinc-600">Trusted by <span className="text-rose-400 font-semibold">1000+</span> members</p>
      </div>
    </div>
  );
}
