import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const fadeUp = { initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0, transition: { duration: 0.5 } } };
const stagger = { animate: { transition: { staggerChildren: 0.1 } } };

const API = process.env.REACT_APP_BACKEND_URL;

const FEATURES = [
  { title: "AI Payment Verification", desc: "GPT-5.2 Vision instantly verifies payment screenshots. Zero manual effort.", icon: "brain" },
  { title: "Auto UPI QR Codes", desc: "Dynamic QR codes generated for every plan and transaction automatically.", icon: "qr" },
  { title: "Paid Posts with Blur", desc: "Lock your best content behind a paywall with adjustable blur levels.", icon: "lock" },
  { title: "Live Stream Tickets", desc: "Sell tickets to live sessions. AI verifies payments, auto-grants access.", icon: "video" },
  { title: "Multi-Tenant SaaS", desc: "Fully isolated workspace for each creator. Your data, your control.", icon: "shield" },
  { title: "Telegram Mini App", desc: "Full admin panel inside Telegram. Manage everything from your phone.", icon: "phone" },
];

const STEPS = [
  { num: "01", title: "Connect Your Bot", desc: "Enter your bot token from @BotFather. Validated instantly." },
  { num: "02", title: "Set Your Pricing", desc: "Add UPI ID, create plans, set prices. Optional Razorpay support." },
  { num: "03", title: "Share & Earn", desc: "Get your Mini App link. Start accepting subscriptions immediately." },
];

const FeatureIcon = ({ type }) => {
  const icons = {
    brain: <path d="M12 2a4 4 0 0 0-4 4v1a3 3 0 0 0-3 3v1a3 3 0 0 0 3 3h1v4a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-4h1a3 3 0 0 0 3-3v-1a3 3 0 0 0-3-3V6a4 4 0 0 0-4-4z"/>,
    lock: <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>,
    qr: <><rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/><rect x="14" y="14" width="4" height="4"/></>,
    video: <><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>,
    phone: <><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></>,
  };
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">{icons[type]}</svg>;
};

export default function LandingPage() {
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const isLoggedIn = !!localStorage.getItem("token");

  useEffect(() => {
    axios.get(`${API}/api/dashboard-plans`).then(r => setPlans(r.data.plans || [])).catch(() => {});
  }, []);

  const goOnboard = () => navigate("/creator-onboard");

  return (
    <div className="lp" data-testid="landing-page">
      {/* NAV */}
      <nav className="lp-nav" data-testid="landing-nav">
        <div className="lp-nav-inner">
          <span className="lp-logo" data-testid="landing-logo">TgSubsBot</span>
          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="#how">How It Works</a>
          </div>
          <div className="lp-nav-actions">
            {isLoggedIn ? (
              <button className="lp-btn-primary lp-btn-sm" onClick={() => navigate("/dashboard")} data-testid="nav-dashboard">Dashboard</button>
            ) : (
              <>
                <button className="lp-btn-ghost" onClick={() => navigate("/login")} data-testid="nav-login">Login</button>
                <button className="lp-btn-primary lp-btn-sm" onClick={goOnboard} data-testid="nav-cta">Launch Bot</button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="lp-hero">
        <div className="lp-hero-bg" />
        <motion.div className="lp-hero-content" variants={stagger} initial="initial" animate="animate">
          <motion.span className="lp-label" variants={fadeUp}>TELEGRAM SUBSCRIPTION PLATFORM</motion.span>
          <motion.h1 className="lp-h1" variants={fadeUp} data-testid="hero-heading">
            Launch your Telegram<br />subscription bot<br /><span className="lp-accent">in 2 minutes</span>
          </motion.h1>
          <motion.p className="lp-hero-sub" variants={fadeUp}>
            Monetize your audience with AI-powered payments, auto QR codes, live stream tickets, and exclusive content gates.
          </motion.p>
          <motion.div className="lp-hero-btns" variants={fadeUp}>
            <button className="lp-btn-primary" onClick={goOnboard} data-testid="hero-cta-button">
              Get Started Free
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
            <button className="lp-btn-glass" onClick={() => window.open("/miniapp?tg_id=demo", "_blank")} data-testid="hero-demo-btn">
              View Demo
            </button>
          </motion.div>
          <motion.div className="lp-stats" variants={fadeUp}>
            <div className="lp-stat"><strong>10K+</strong><span>Creators</span></div>
            <div className="lp-stat-line" />
            <div className="lp-stat"><strong>50K+</strong><span>Subscribers</span></div>
            <div className="lp-stat-line" />
            <div className="lp-stat"><strong>2Cr+</strong><span>Processed</span></div>
          </motion.div>
        </motion.div>
      </section>

      {/* FEATURES */}
      <section className="lp-section" id="features">
        <motion.div className="lp-container" initial="initial" whileInView="animate" viewport={{ once: true, margin: "-80px" }} variants={stagger}>
          <motion.span className="lp-label" variants={fadeUp}>FEATURES</motion.span>
          <motion.h2 className="lp-h2" variants={fadeUp}>Everything you need to monetize</motion.h2>
          <div className="lp-feat-grid" data-testid="features-grid">
            {FEATURES.map((f, i) => (
              <motion.div key={i} className="lp-feat-card" variants={fadeUp} data-testid={`feature-card-${i}`}>
                <div className="lp-feat-glow" />
                <div className="lp-feat-icon"><FeatureIcon type={f.icon} /></div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* PRICING */}
      <section className="lp-section lp-pricing-bg" id="pricing">
        <motion.div className="lp-container" initial="initial" whileInView="animate" viewport={{ once: true, margin: "-80px" }} variants={stagger}>
          <motion.span className="lp-label" variants={fadeUp}>PRICING</motion.span>
          <motion.h2 className="lp-h2" variants={fadeUp}>Simple, transparent pricing</motion.h2>
          <motion.p className="lp-pricing-sub" variants={fadeUp}>Choose the plan that fits your growth. Cancel anytime.</motion.p>
          <div className="lp-price-grid" data-testid="pricing-grid">
            {plans.map((plan, i) => (
              <motion.div key={plan.id} className={`lp-price-card ${plan.popular ? "lp-popular" : ""}`} variants={fadeUp} data-testid={`pricing-card-${plan.id}`}>
                {plan.popular && <span className="lp-popular-badge">Most Popular</span>}
                {plan.save && <span className="lp-save-badge">Save {plan.save}</span>}
                <h3 className="lp-price-name">{plan.name}</h3>
                <div className="lp-price-amount">
                  {plan.contact ? (
                    <span className="lp-price-contact">Contact Us</span>
                  ) : (
                    <>
                      <span className="lp-rupee">&#8377;</span>
                      <span className="lp-price-num">{plan.price.toLocaleString("en-IN")}</span>
                    </>
                  )}
                </div>
                <span className="lp-price-dur">{plan.duration}</span>
                <ul className="lp-price-feats">
                  <li>AI Payment Verification</li>
                  <li>Unlimited Subscribers</li>
                  <li>Live Stream Tickets</li>
                  <li>Paid Posts & Content</li>
                  <li>Broadcast Messages</li>
                  {(plan.id === "6month" || plan.id === "12month" || plan.id === "lifetime") && <li>Priority Support</li>}
                  {(plan.id === "12month" || plan.id === "lifetime") && <li>Custom Branding</li>}
                  {plan.id === "lifetime" && <li>White-label Option</li>}
                </ul>
                <button
                  className={plan.popular ? "lp-btn-primary lp-btn-full" : "lp-btn-glass lp-btn-full"}
                  onClick={() => navigate("/login")}
                  data-testid={`pricing-cta-${plan.id}`}
                >
                  {plan.contact ? "Contact Sales" : "Get Started"}
                </button>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* HOW IT WORKS */}
      <section className="lp-section" id="how">
        <motion.div className="lp-container" initial="initial" whileInView="animate" viewport={{ once: true, margin: "-80px" }} variants={stagger}>
          <motion.span className="lp-label" variants={fadeUp}>HOW IT WORKS</motion.span>
          <motion.h2 className="lp-h2" variants={fadeUp}>Three steps to go live</motion.h2>
          <div className="lp-steps" data-testid="steps-section">
            {STEPS.map((s, i) => (
              <motion.div key={i} className="lp-step-card" variants={fadeUp} data-testid={`step-${i}`}>
                <span className="lp-step-num">{s.num}</span>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <div className="lp-cta-glow" />
        <motion.div className="lp-container lp-cta-inner" initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h2 className="lp-h2" data-testid="bottom-cta-heading">Ready to own your audience?</h2>
          <p className="lp-cta-sub">Join thousands of creators monetizing their Telegram channels.</p>
          <button className="lp-btn-primary lp-btn-lg" onClick={goOnboard} data-testid="bottom-cta-button">
            Launch Your Bot Now
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </button>
        </motion.div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer" data-testid="landing-footer">
        <div className="lp-footer-inner">
          <span className="lp-logo">TgSubsBot</span>
          <span className="lp-footer-copy">Built for creators, by creators.</span>
        </div>
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;700;900&family=Manrope:wght@400;500;600;700&display=swap');

        /* === BASE === */
        .lp { --rose: hsl(346, 80%, 50%); --rose-light: hsl(346, 80%, 60%); --rose-glow: hsl(346, 80%, 50%); --bg: hsl(340, 50%, 4%); --card: hsl(340, 40%, 7%); --border: hsl(340, 40%, 15%); --text: #fff; --text-dim: rgba(255,255,255,0.55); --text-muted: rgba(255,255,255,0.35); background: var(--bg); color: var(--text); font-family: 'Manrope', sans-serif; overflow-x: hidden; }

        /* === NAV === */
        .lp-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 100; background: hsla(340,50%,4%,0.85); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); }
        .lp-nav-inner { max-width: 1120px; margin: 0 auto; padding: 12px 24px; display: flex; align-items: center; gap: 12px; }
        .lp-logo { font-family: 'Unbounded', sans-serif; font-weight: 900; font-size: 18px; color: var(--rose); flex-shrink: 0; }
        .lp-nav-links { display: flex; gap: 28px; margin-left: auto; }
        .lp-nav-links a { color: var(--text-muted); text-decoration: none; font-size: 13px; font-weight: 600; transition: color 0.2s; }
        .lp-nav-links a:hover { color: var(--text); }
        .lp-nav-actions { display: flex; gap: 10px; margin-left: 28px; }
        .lp-btn-ghost { background: none; border: none; color: var(--text-dim); font-size: 13px; font-weight: 600; cursor: pointer; padding: 8px 16px; border-radius: 50px; transition: color 0.2s; font-family: inherit; }
        .lp-btn-ghost:hover { color: var(--text); }

        /* === BUTTONS === */
        .lp-btn-primary { background: var(--rose); color: #fff; border: none; border-radius: 50px; padding: 14px 32px; font-size: 15px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: all 0.25s; font-family: 'Manrope', sans-serif; }
        .lp-btn-primary:hover { background: var(--rose-light); box-shadow: 0 0 28px hsla(346,80%,50%,0.3); transform: translateY(-1px); }
        .lp-btn-sm { padding: 9px 20px; font-size: 13px; }
        .lp-btn-lg { padding: 18px 40px; font-size: 16px; }
        .lp-btn-glass { background: rgba(255,255,255,0.04); backdrop-filter: blur(12px); border: 1px solid var(--border); color: var(--text); border-radius: 50px; padding: 14px 32px; font-size: 15px; font-weight: 700; cursor: pointer; transition: all 0.2s; font-family: 'Manrope', sans-serif; }
        .lp-btn-glass:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.2); }
        .lp-btn-full { width: 100%; justify-content: center; }

        /* === HERO === */
        .lp-hero { position: relative; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 120px 24px 80px; text-align: center; }
        .lp-hero-bg { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 30%, hsla(346,80%,50%,0.08) 0%, transparent 55%); }
        .lp-hero-content { position: relative; max-width: 760px; }
        .lp-label { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 0.2em; color: var(--text-muted); text-transform: uppercase; margin-bottom: 20px; }
        .lp-h1 { font-family: 'Unbounded', sans-serif; font-size: clamp(30px, 5.5vw, 58px); font-weight: 900; line-height: 1.08; letter-spacing: -2px; margin: 0 0 24px; }
        .lp-accent { color: var(--rose); }
        .lp-hero-sub { font-size: clamp(15px, 2.2vw, 18px); color: var(--text-dim); line-height: 1.65; margin-bottom: 36px; max-width: 540px; margin-left: auto; margin-right: auto; }
        .lp-hero-btns { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 48px; }
        .lp-stats { display: flex; align-items: center; justify-content: center; gap: 20px; }
        .lp-stat { text-align: center; }
        .lp-stat strong { display: block; font-size: 22px; font-weight: 800; }
        .lp-stat span { font-size: 12px; color: var(--text-muted); }
        .lp-stat-line { width: 1px; height: 30px; background: var(--border); }

        /* === SECTIONS === */
        .lp-section { padding: 100px 24px; }
        .lp-container { max-width: 1120px; margin: 0 auto; }
        .lp-h2 { font-family: 'Unbounded', sans-serif; font-size: clamp(22px, 3.8vw, 38px); font-weight: 700; letter-spacing: -1px; margin: 0 0 48px; }

        /* === FEATURES GRID === */
        .lp-feat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .lp-feat-card { position: relative; background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 28px 24px; overflow: hidden; transition: all 0.3s; }
        .lp-feat-card:hover { border-color: hsla(346,80%,50%,0.25); transform: translateY(-3px); }
        .lp-feat-glow { position: absolute; inset: 0; background: radial-gradient(circle at 30% 30%, hsla(346,80%,50%,0.06), transparent 60%); opacity: 0; transition: opacity 0.4s; pointer-events: none; }
        .lp-feat-card:hover .lp-feat-glow { opacity: 1; }
        .lp-feat-icon { width: 44px; height: 44px; border-radius: 12px; background: hsla(346,80%,50%,0.12); display: flex; align-items: center; justify-content: center; margin-bottom: 16px; color: var(--rose); }
        .lp-feat-card h3 { font-family: 'Unbounded', sans-serif; font-size: 16px; font-weight: 700; margin: 0 0 8px; letter-spacing: -0.3px; }
        .lp-feat-card p { font-size: 13px; color: var(--text-dim); line-height: 1.6; margin: 0; }

        /* === PRICING === */
        .lp-pricing-bg { background: radial-gradient(ellipse at 50% 0%, hsla(346,80%,50%,0.04) 0%, transparent 50%); }
        .lp-pricing-sub { font-size: 16px; color: var(--text-dim); margin: -32px 0 48px; }
        .lp-price-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; align-items: start; }
        .lp-price-card { position: relative; background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 28px 22px; text-align: center; transition: all 0.3s; }
        .lp-price-card:hover { border-color: hsla(346,80%,50%,0.2); }
        .lp-popular { border-color: var(--rose); box-shadow: 0 0 40px hsla(346,80%,50%,0.1); }
        .lp-popular-badge { position: absolute; top: -1px; left: 50%; transform: translateX(-50%); background: var(--rose); color: #fff; font-size: 10px; font-weight: 700; padding: 4px 14px; border-radius: 0 0 10px 10px; letter-spacing: 0.05em; text-transform: uppercase; }
        .lp-save-badge { display: inline-block; background: hsla(142,50%,40%,0.15); color: hsl(142,50%,55%); font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 50px; margin-bottom: 8px; }
        .lp-price-name { font-family: 'Unbounded', sans-serif; font-size: 15px; font-weight: 700; margin: 12px 0 16px; }
        .lp-price-amount { display: flex; align-items: baseline; justify-content: center; gap: 2px; margin-bottom: 4px; }
        .lp-rupee { font-size: 20px; font-weight: 700; color: var(--text-dim); }
        .lp-price-num { font-family: 'Unbounded', sans-serif; font-size: 34px; font-weight: 900; letter-spacing: -1px; }
        .lp-price-contact { font-family: 'Unbounded', sans-serif; font-size: 22px; font-weight: 700; color: var(--rose); }
        .lp-price-dur { font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 20px; }
        .lp-price-feats { list-style: none; padding: 0; margin: 0 0 24px; text-align: left; }
        .lp-price-feats li { font-size: 13px; color: var(--text-dim); padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); display: flex; align-items: center; gap: 8px; }
        .lp-price-feats li::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--rose); flex-shrink: 0; }

        /* === STEPS === */
        .lp-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .lp-step-card { background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 32px 24px; text-align: center; }
        .lp-step-num { font-family: 'Unbounded', sans-serif; font-size: 38px; font-weight: 900; color: var(--rose); display: block; margin-bottom: 14px; opacity: 0.8; }
        .lp-step-card h3 { font-family: 'Unbounded', sans-serif; font-size: 15px; font-weight: 700; margin: 0 0 8px; }
        .lp-step-card p { font-size: 13px; color: var(--text-dim); line-height: 1.6; margin: 0; }

        /* === CTA === */
        .lp-cta { position: relative; padding: 100px 24px; text-align: center; overflow: hidden; }
        .lp-cta-glow { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 50%, hsla(346,80%,50%,0.07) 0%, transparent 55%); }
        .lp-cta-inner { position: relative; }
        .lp-cta-sub { font-size: 16px; color: var(--text-dim); margin: 12px auto 32px; max-width: 460px; }

        /* === FOOTER === */
        .lp-footer { border-top: 1px solid var(--border); padding: 28px 24px; }
        .lp-footer-inner { max-width: 1120px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .lp-footer-copy { font-size: 13px; color: var(--text-muted); }

        /* === RESPONSIVE === */
        @media (max-width: 1024px) {
          .lp-price-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 768px) {
          .lp-feat-grid { grid-template-columns: 1fr; }
          .lp-price-grid { grid-template-columns: 1fr; max-width: 380px; margin: 0 auto; }
          .lp-steps { grid-template-columns: 1fr; }
          .lp-nav-links { display: none; }
          .lp-stats { flex-wrap: wrap; }
          .lp-nav-actions { margin-left: auto; }
        }
      `}</style>
    </div>
  );
}
