import React from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

const fadeUp = { initial: { opacity: 0, y: 30 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.12 } } };

const FEATURES = [
  { title: "AI Payment Verification", desc: "GPT-5.2 Vision instantly verifies payment screenshots. No more manual checking.", icon: "brain", span: "wide" },
  { title: "Paid Posts with Blur", desc: "Lock your best content behind a paywall with adjustable blur levels.", icon: "lock", span: "tall" },
  { title: "Auto UPI QR Codes", desc: "Dynamic QR codes generated automatically for every plan and transaction.", icon: "qr", span: "normal" },
  { title: "Live Stream Tickets", desc: "Sell tickets to live sessions. AI verifies payments, auto-grants access.", icon: "video", span: "normal" },
  { title: "Multi-Tenant SaaS", desc: "Your data is fully isolated. Each creator gets their own private workspace.", icon: "shield", span: "normal" },
  { title: "Admin Mini App", desc: "Full admin panel inside Telegram. Manage everything from your phone.", icon: "phone", span: "normal" },
];

const STEPS = [
  { num: "01", title: "Connect Your Bot", desc: "Enter your Telegram bot token from @BotFather. We validate it instantly." },
  { num: "02", title: "Set Your Pricing", desc: "Add your UPI ID, create plans, set prices. Optional Razorpay for instant payments." },
  { num: "03", title: "Share & Earn", desc: "Get your unique Mini App link. Share it. Start accepting subscriptions immediately." },
];

const ICONS = {
  brain: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 2a4 4 0 0 0-4 4v1a3 3 0 0 0-3 3v1a3 3 0 0 0 3 3h1v4a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-4h1a3 3 0 0 0 3-3v-1a3 3 0 0 0-3-3V6a4 4 0 0 0-4-4z"/></svg>,
  lock: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
  qr: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/><rect x="14" y="14" width="4" height="4"/><rect x="20" y="14" width="2" height="2"/><rect x="14" y="20" width="2" height="2"/><rect x="20" y="20" width="2" height="2"/></svg>,
  video: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>,
  shield: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  phone: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></svg>,
};

export default function LandingPage() {
  const navigate = useNavigate();
  const goOnboard = () => navigate("/creator-onboard");

  return (
    <div className="lp">
      {/* NAV */}
      <nav className="lp-nav" data-testid="landing-nav">
        <div className="lp-nav-inner">
          <span className="lp-logo" data-testid="landing-logo">TgSubsBot</span>
          <div className="lp-nav-links">
            <a href="#features">Features</a>
            <a href="#how">How It Works</a>
          </div>
          <button className="lp-btn-primary lp-btn-sm" onClick={goOnboard} data-testid="nav-cta">Launch Bot</button>
          <button className="lp-btn-glass lp-btn-sm" onClick={() => navigate("/login")} data-testid="nav-login">Login</button>
        </div>
      </nav>

      {/* HERO */}
      <section className="lp-hero">
        <div className="lp-hero-bg" />
        <motion.div className="lp-hero-content" variants={stagger} initial="initial" animate="animate">
          <motion.span className="lp-label" variants={fadeUp}>THE ULTIMATE CREATOR TOOL</motion.span>
          <motion.h1 className="lp-h1" variants={fadeUp} data-testid="hero-heading">
            Launch your Telegram<br />subscription bot<br /><span className="lp-gradient-text">in 2 minutes</span>
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
          <motion.div className="lp-hero-stat-row" variants={fadeUp}>
            <div className="lp-hero-stat"><strong>10K+</strong><span>Creators</span></div>
            <div className="lp-hero-stat-divider" />
            <div className="lp-hero-stat"><strong>50K+</strong><span>Subscribers</span></div>
            <div className="lp-hero-stat-divider" />
            <div className="lp-hero-stat"><strong>2Cr+</strong><span>Processed</span></div>
          </motion.div>
        </motion.div>
      </section>

      {/* FEATURES */}
      <section className="lp-section" id="features">
        <motion.div className="lp-section-inner" initial="initial" whileInView="animate" viewport={{ once: true }} variants={stagger}>
          <motion.span className="lp-label" variants={fadeUp}>FEATURES</motion.span>
          <motion.h2 className="lp-h2" variants={fadeUp}>Everything you need to monetize</motion.h2>
          <div className="lp-features-grid" data-testid="features-grid">
            {FEATURES.map((f, i) => (
              <motion.div key={i} className={`lp-feature-card ${f.span}`} variants={fadeUp} data-testid={`feature-card-${i}`}>
                <div className="lp-feature-glow" />
                <div className="lp-feature-icon">{ICONS[f.icon]}</div>
                <h3 className="lp-feature-title">{f.title}</h3>
                <p className="lp-feature-desc">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* HOW IT WORKS */}
      <section className="lp-section lp-how" id="how">
        <motion.div className="lp-section-inner" initial="initial" whileInView="animate" viewport={{ once: true }} variants={stagger}>
          <motion.span className="lp-label" variants={fadeUp}>HOW IT WORKS</motion.span>
          <motion.h2 className="lp-h2" variants={fadeUp}>Three steps to go live</motion.h2>
          <div className="lp-steps" data-testid="steps-section">
            {STEPS.map((s, i) => (
              <motion.div key={i} className="lp-step-card" variants={fadeUp} data-testid={`step-${i}`}>
                <span className="lp-step-num">{s.num}</span>
                <h3 className="lp-step-title">{s.title}</h3>
                <p className="lp-step-desc">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* BOTTOM CTA */}
      <section className="lp-cta-section">
        <div className="lp-cta-glow" />
        <motion.div className="lp-cta-inner" initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
          <h2 className="lp-h2" data-testid="bottom-cta-heading">Ready to own your audience?</h2>
          <p className="lp-cta-sub">Join thousands of creators who monetize their Telegram channels effortlessly.</p>
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

        .lp { background: #05050A; color: #fff; font-family: 'Manrope', sans-serif; overflow-x: hidden; }

        .lp-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 100; background: rgba(5,5,10,0.8); backdrop-filter: blur(16px); border-bottom: 1px solid rgba(255,255,255,0.06); }
        .lp-nav-inner { max-width: 1200px; margin: 0 auto; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
        .lp-logo { font-family: 'Unbounded', sans-serif; font-weight: 900; font-size: 20px; background: linear-gradient(135deg, #FF007F, #7000FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .lp-nav-links { display: flex; gap: 28px; }
        .lp-nav-links a { color: rgba(255,255,255,0.5); text-decoration: none; font-size: 14px; font-weight: 500; transition: color 0.2s; }
        .lp-nav-links a:hover { color: #fff; }

        .lp-btn-primary { background: #FF007F; color: #fff; border: none; border-radius: 50px; padding: 14px 32px; font-size: 15px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: all 0.25s; font-family: 'Manrope', sans-serif; }
        .lp-btn-primary:hover { background: #FF3399; box-shadow: 0 0 30px rgba(255,0,127,0.35); transform: scale(1.03); }
        .lp-btn-sm { padding: 10px 22px; font-size: 13px; }
        .lp-btn-lg { padding: 18px 40px; font-size: 17px; }
        .lp-btn-glass { background: rgba(255,255,255,0.05); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 50px; padding: 14px 32px; font-size: 15px; font-weight: 700; cursor: pointer; transition: all 0.2s; font-family: 'Manrope', sans-serif; }
        .lp-btn-glass:hover { background: rgba(255,255,255,0.1); }

        .lp-hero { position: relative; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 120px 24px 80px; text-align: center; }
        .lp-hero-bg { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 20%, rgba(255,0,127,0.12) 0%, transparent 50%), radial-gradient(ellipse at 30% 80%, rgba(112,0,255,0.08) 0%, transparent 50%); }
        .lp-hero-content { position: relative; max-width: 800px; }
        .lp-label { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 0.2em; color: rgba(255,255,255,0.4); text-transform: uppercase; margin-bottom: 20px; }
        .lp-h1 { font-family: 'Unbounded', sans-serif; font-size: clamp(32px, 6vw, 64px); font-weight: 900; line-height: 1.05; letter-spacing: -2px; margin: 0 0 24px; }
        .lp-gradient-text { background: linear-gradient(135deg, #FF007F, #7000FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .lp-hero-sub { font-size: clamp(16px, 2.5vw, 20px); color: rgba(255,255,255,0.6); line-height: 1.6; margin-bottom: 36px; max-width: 580px; margin-left: auto; margin-right: auto; }
        .lp-hero-btns { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; margin-bottom: 48px; }
        .lp-hero-stat-row { display: flex; align-items: center; justify-content: center; gap: 20px; }
        .lp-hero-stat { text-align: center; }
        .lp-hero-stat strong { display: block; font-size: 22px; font-weight: 800; color: #fff; }
        .lp-hero-stat span { font-size: 12px; color: rgba(255,255,255,0.4); }
        .lp-hero-stat-divider { width: 1px; height: 32px; background: rgba(255,255,255,0.1); }

        .lp-section { padding: 100px 24px; }
        .lp-section-inner { max-width: 1100px; margin: 0 auto; }
        .lp-h2 { font-family: 'Unbounded', sans-serif; font-size: clamp(24px, 4vw, 42px); font-weight: 700; letter-spacing: -1px; margin: 0 0 48px; }

        .lp-features-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .lp-feature-card { position: relative; background: rgba(255,255,255,0.03); backdrop-filter: blur(24px); border: 1px solid rgba(255,255,255,0.07); border-radius: 20px; padding: 32px 28px; overflow: hidden; transition: all 0.3s; }
        .lp-feature-card:hover { border-color: rgba(255,255,255,0.15); transform: translateY(-4px); }
        .lp-feature-card.wide { grid-column: span 2; }
        .lp-feature-card.tall { grid-row: span 2; display: flex; flex-direction: column; justify-content: center; }
        .lp-feature-glow { position: absolute; inset: 0; background: linear-gradient(135deg, rgba(255,0,127,0.06), rgba(112,0,255,0.06)); opacity: 0; transition: opacity 0.5s; pointer-events: none; }
        .lp-feature-card:hover .lp-feature-glow { opacity: 1; }
        .lp-feature-icon { width: 48px; height: 48px; border-radius: 14px; background: rgba(255,0,127,0.1); display: flex; align-items: center; justify-content: center; margin-bottom: 18px; color: #FF007F; }
        .lp-feature-title { font-family: 'Unbounded', sans-serif; font-size: 18px; font-weight: 700; margin: 0 0 10px; letter-spacing: -0.5px; }
        .lp-feature-desc { font-size: 14px; color: rgba(255,255,255,0.5); line-height: 1.6; margin: 0; }

        .lp-how { background: radial-gradient(ellipse at 50% 50%, rgba(112,0,255,0.05) 0%, transparent 60%); }
        .lp-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
        .lp-step-card { position: relative; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 20px; padding: 32px 24px; text-align: center; }
        .lp-step-num { font-family: 'Unbounded', sans-serif; font-size: 42px; font-weight: 900; background: linear-gradient(135deg, #FF007F, #7000FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: block; margin-bottom: 16px; }
        .lp-step-title { font-family: 'Unbounded', sans-serif; font-size: 16px; font-weight: 700; margin: 0 0 10px; }
        .lp-step-desc { font-size: 14px; color: rgba(255,255,255,0.5); line-height: 1.6; margin: 0; }

        .lp-cta-section { position: relative; padding: 120px 24px; text-align: center; overflow: hidden; }
        .lp-cta-glow { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 50%, rgba(255,0,127,0.1) 0%, transparent 60%); }
        .lp-cta-inner { position: relative; }
        .lp-cta-sub { font-size: 18px; color: rgba(255,255,255,0.5); margin: 16px auto 36px; max-width: 500px; }

        .lp-footer { border-top: 1px solid rgba(255,255,255,0.06); padding: 32px 24px; }
        .lp-footer-inner { max-width: 1100px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .lp-footer-copy { font-size: 13px; color: rgba(255,255,255,0.3); }

        @media (max-width: 768px) {
          .lp-features-grid { grid-template-columns: 1fr; }
          .lp-feature-card.wide, .lp-feature-card.tall { grid-column: span 1; grid-row: span 1; }
          .lp-steps { grid-template-columns: 1fr; }
          .lp-nav-links { display: none; }
          .lp-hero-stat-row { flex-wrap: wrap; }
        }
      `}</style>
    </div>
  );
}
