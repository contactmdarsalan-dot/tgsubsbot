import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Play, Zap, Users, TrendingUp, Radio, Gift, Shield, ChevronRight, Star, Check, Wallet, Send, Crown, Loader2 } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import axios from "axios";

const chartData = [
  { v: 2000 }, { v: 3200 }, { v: 2800 }, { v: 5100 }, { v: 4200 },
  { v: 6800 }, { v: 5900 }, { v: 8200 }, { v: 7100 }, { v: 9500 },
  { v: 8800 }, { v: 12000 }, { v: 10500 }, { v: 14200 },
];

const payouts = [
  "Rahul earned Rs.1,20,000", "Priya earned Rs.85,000", "Ankit earned Rs.2,10,000",
  "Neha earned Rs.45,000", "Vikram earned Rs.3,50,000", "Simran earned Rs.67,000",
  "Arjun earned Rs.1,95,000", "Pooja earned Rs.78,000",
];

const testimonials = [
  { name: "Priya Sharma", role: "Fitness Creator", earning: "Rs.1,85,000/mo", quote: "Switched from manual payments to TGSubsBot. My revenue tripled in 2 months.", avatar: "PS" },
  { name: "Rahul Verma", role: "Trading Mentor", earning: "Rs.3,20,000/mo", quote: "The paid live feature alone made me Rs.50K in one weekend. Game changer.", avatar: "RV" },
  { name: "Anita K.", role: "Astrology Channel", earning: "Rs.92,000/mo", quote: "I was losing 30% subscribers to non-payers. Auto-kick fixed that overnight.", avatar: "AK" },
];

const benefits = [
  { icon: Wallet, title: "Earn with Subscriptions", desc: "Set up weekly, monthly, or yearly plans. Auto-collect payments. Auto-grant channel access. Zero manual work.", color: "#BFFF00", span: "md:col-span-2" },
  { icon: Shield, title: "Auto Telegram Access", desc: "Non-payers auto-removed. New subscribers instantly added. Your community stays premium.", color: "#10B981", span: "md:col-span-1" },
  { icon: TrendingUp, title: "Track Your Revenue", desc: "Real-time dashboard. See who paid, who expired, daily/monthly trends. Export anytime.", color: "#F59E0B", span: "md:col-span-1" },
  { icon: Radio, title: "Run Paid Live Sessions", desc: "Go live with ticket-based access. VIP rooms. Real-time super chats. Replays for premium members.", color: "#BFFF00", span: "md:col-span-2" },
];

const steps = [
  { num: "01", title: "Connect Telegram", desc: "Link your bot in 30 seconds. No coding needed." },
  { num: "02", title: "Create Plans", desc: "Set your prices. Weekly, monthly, lifetime. Your rules." },
  { num: "03", title: "Start Earning", desc: "Share your link. Get paid. Grow your empire." },
];

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fallbackPlans = [
  { name: "Starter", price: 0, duration_days: 17, features: ["Up to 100 subscribers", "1 subscription plan", "Basic analytics", "Auto access control"], is_popular: false },
  { name: "Pro", price: 1999, duration_days: 30, features: ["Unlimited subscribers", "Unlimited plans", "AI payment verification", "Paid live streams", "Broadcast messages", "Referral system"], is_popular: true },
];

const fadeUp = { hidden: { opacity: 0, y: 30 }, visible: { opacity: 1, y: 0, transition: { duration: 0.6 } } };
const stagger = { visible: { transition: { staggerChildren: 0.1 } } };

export default function LandingPage() {
  const navigate = useNavigate();
  const [marqueeIdx, setMarqueeIdx] = useState(0);
  const isLoggedIn = !!localStorage.getItem("token");
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);

  useEffect(() => {
    const t = setInterval(() => setMarqueeIdx(i => (i + 1) % payouts.length), 2500);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    axios.get(`${API}/public/subscription-plans`)
      .then(res => {
        setPlans(res.data?.length > 0 ? res.data : fallbackPlans);
      })
      .catch(() => setPlans(fallbackPlans))
      .finally(() => setPlansLoading(false));
  }, []);

  return (
    <div className="min-h-screen text-white overflow-x-hidden" style={{ background: "hsl(0, 0%, 2%)", fontFamily: "Manrope, sans-serif" }}>

      {/* NAV */}
      <nav className="fixed top-0 w-full z-50" style={{ background: "hsla(340,50%,4%,0.9)", backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="max-w-7xl mx-auto px-6 md:px-12 flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#BFFF00] flex items-center justify-center shadow-[0_0_20px_rgba(225,29,72,0.4)]">
              <Send className="w-5 h-5 text-white" />
            </div>
            <span style={{ fontFamily: "Unbounded" }} className="text-lg font-bold">TGSubsBot</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-white/60">
            <a href="#benefits" className="hover:text-white transition-colors">Features</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <a href="#how" className="hover:text-white transition-colors">How It Works</a>
          </div>
          <div className="flex items-center gap-3">
            {isLoggedIn ? (
              <button onClick={() => navigate("/dashboard")} className="text-sm bg-[#BFFF00] hover:bg-[#84CC16] text-white font-semibold rounded-full px-5 py-2 shadow-[0_0_15px_rgba(225,29,72,0.3)] transition-all hover:scale-105 flex items-center gap-2" data-testid="nav-dashboard">
                Dashboard <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <>
                <button onClick={() => navigate("/login")} className="text-sm text-white/70 hover:text-white transition-colors px-4 py-2" data-testid="nav-login">Login</button>
                <button onClick={() => navigate("/login")} className="text-sm bg-[#BFFF00] hover:bg-[#84CC16] text-white font-semibold rounded-full px-5 py-2 shadow-[0_0_15px_rgba(225,29,72,0.3)] transition-all hover:scale-105" data-testid="nav-signup">Start Free</button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="pt-32 pb-20 md:pt-40 md:pb-28">
        <div className="max-w-7xl mx-auto px-6 md:px-12 grid md:grid-cols-2 gap-12 md:gap-16 items-center">
          <motion.div initial="hidden" animate="visible" variants={stagger}>
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 bg-[#BFFF00]/15 border border-[#BFFF00]/30 rounded-full px-4 py-1.5 mb-6">
              <Zap className="w-4 h-4 text-[#BFFF00]" />
              <span className="text-xs font-bold uppercase tracking-widest text-[#BFFF00]">#1 Telegram Monetization Platform</span>
            </motion.div>
            <motion.h1 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-[1.1] mb-6">
              Turn Your Telegram Audience Into{" "}
              <span className="bg-gradient-to-r from-[#BFFF00] via-[#A3E635] to-[#BEF264] bg-clip-text text-transparent">Income</span>
            </motion.h1>
            <motion.p variants={fadeUp} className="text-lg text-white/60 leading-relaxed mb-8 max-w-lg">
              Sell subscriptions, run paid lives, and monetize your community — all automated. No coding. No manual work.
            </motion.p>
            <motion.div variants={fadeUp} className="flex flex-wrap gap-4">
              <button onClick={() => navigate("/login")} className="flex items-center gap-2 bg-[#BFFF00] hover:bg-[#84CC16] text-white font-bold rounded-full px-8 py-4 text-lg shadow-[0_0_30px_rgba(225,29,72,0.4)] transition-all hover:scale-105 hover:shadow-[0_0_40px_rgba(225,29,72,0.6)]" data-testid="hero-cta-start">
                Start Free <ArrowRight className="w-5 h-5" />
              </button>
              <button className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white font-bold rounded-full px-8 py-4 text-lg backdrop-blur-md transition-all" data-testid="hero-cta-demo">
                <Play className="w-5 h-5" /> Watch Demo
              </button>
            </motion.div>
            <motion.div variants={fadeUp} className="flex items-center gap-6 mt-8 text-sm text-white/50">
              <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-[#10B981]" /> Free forever plan</span>
              <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-[#10B981]" /> No credit card</span>
              <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-[#10B981]" /> Setup in 2 min</span>
            </motion.div>
          </motion.div>

          {/* CSS DASHBOARD MOCKUP */}
          <motion.div initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.8, delay: 0.3 }} className="relative">
            <div className="absolute -inset-4 bg-[#BFFF00]/10 rounded-3xl blur-3xl" />
            <div className="relative bg-[#0A0305] border border-white/10 rounded-2xl p-6 shadow-[0_20px_60px_rgba(225,29,72,0.15)]">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <p className="text-xs text-white/40 uppercase tracking-wider">Total Revenue</p>
                  <p style={{ fontFamily: "Unbounded" }} className="text-3xl font-black text-white mt-1">Rs.4,50,000</p>
                </div>
                <div className="bg-[#10B981]/15 text-[#10B981] text-sm font-bold px-3 py-1 rounded-full flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5" /> +24% this week
                </div>
              </div>
              <div className="h-32 mb-6">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="heroGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#BFFF00" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#BFFF00" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="v" stroke="#BFFF00" fill="url(#heroGrad)" strokeWidth={2.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Active Subs", val: "2,847", color: "#BFFF00" },
                  { label: "Today's Earning", val: "Rs.12,500", color: "#10B981" },
                  { label: "Conversion", val: "34%", color: "#F59E0B" },
                ].map(s => (
                  <div key={s.label} className="bg-white/5 rounded-xl p-3 border border-white/5">
                    <p className="text-[10px] text-white/40 uppercase">{s.label}</p>
                    <p className="text-lg font-bold mt-0.5" style={{ color: s.color }}>{s.val}</p>
                  </div>
                ))}
              </div>
              {/* Floating notification */}
              <motion.div animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }} className="absolute -right-4 top-12 bg-[#10B981]/20 border border-[#10B981]/30 text-[#10B981] text-xs font-bold px-3 py-2 rounded-xl backdrop-blur-md shadow-lg">
                + New Subscriber: Rs.999
              </motion.div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* SOCIAL PROOF MARQUEE */}
      <section className="py-6 border-y border-white/5 overflow-hidden">
        <div className="flex animate-marquee whitespace-nowrap">
          {[...payouts, ...payouts].map((p, i) => (
            <div key={i} className="inline-flex items-center gap-2 mx-8 text-sm">
              <div className="w-6 h-6 rounded-full bg-[#10B981]/20 flex items-center justify-center">
                <Check className="w-3 h-3 text-[#10B981]" />
              </div>
              <span className="text-white/50">{p}</span>
            </div>
          ))}
        </div>
      </section>

      {/* STATS */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { val: "5,000+", label: "Active Creators" },
              { val: "Rs.2.5Cr+", label: "Revenue Generated" },
              { val: "50,000+", label: "Subscribers Managed" },
              { val: "99.9%", label: "Uptime" },
            ].map((s, i) => (
              <motion.div key={i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} className="text-center">
                <p style={{ fontFamily: "Unbounded" }} className="text-3xl md:text-4xl font-black bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">{s.val}</p>
                <p className="text-sm text-white/40 mt-1">{s.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* BENEFITS BENTO */}
      <section id="benefits" className="py-24 md:py-32">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger} className="text-center mb-16">
            <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] font-bold text-[#BFFF00] mb-3">Why Creators Love Us</motion.p>
            <motion.h2 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-3xl md:text-5xl font-bold tracking-tight">
              Everything You Need to<br /><span className="bg-gradient-to-r from-[#BFFF00] to-[#BEF264] bg-clip-text text-transparent">Monetize Your Audience</span>
            </motion.h2>
          </motion.div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {benefits.map((b, i) => {
              const Icon = b.icon;
              return (
                <motion.div key={i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} className={`${b.span} group bg-[#0A0305] border border-white/10 rounded-2xl p-8 hover:border-[${b.color}]/50 transition-all duration-300 hover:-translate-y-1`}>
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5" style={{ background: `${b.color}20` }}>
                    <Icon className="w-6 h-6" style={{ color: b.color }} />
                  </div>
                  <h3 style={{ fontFamily: "Unbounded" }} className="text-xl font-bold mb-3">{b.title}</h3>
                  <p className="text-white/50 leading-relaxed">{b.desc}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* LIVE STREAMING SHOWCASE */}
      <section className="py-24 md:py-32 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[#BFFF00]/5 via-transparent to-transparent" />
        <div className="max-w-7xl mx-auto px-6 md:px-12 relative">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger} className="text-center mb-16">
            <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] font-bold text-[#BFFF00] mb-3">Killer Feature</motion.p>
            <motion.h2 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-3xl md:text-5xl font-bold tracking-tight mb-4">
              Go Live & Earn<br /><span className="bg-gradient-to-r from-[#BFFF00] to-[#BEF264] bg-clip-text text-transparent">Instantly</span>
            </motion.h2>
            <motion.p variants={fadeUp} className="text-lg text-white/50 max-w-xl mx-auto">Run paid live sessions. Sell tickets. Get super chats. Your audience pays, you perform. Simple.</motion.p>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="flex justify-center">
            {/* Phone Mockup */}
            <div className="relative w-72 rounded-[2.5rem] border-[6px] border-zinc-800 overflow-hidden shadow-[0_0_60px_rgba(225,29,72,0.2)]" style={{ background: "#0A0305" }}>
              <div className="h-[520px] relative">
                {/* Live Header */}
                <div className="absolute top-0 left-0 right-0 p-4 z-10" style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.8), transparent)" }}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="bg-red-600 text-white text-[10px] font-black px-2 py-0.5 rounded-md animate-pulse flex items-center gap-1">
                        <Radio className="w-3 h-3" /> LIVE
                      </span>
                      <span className="text-white/60 text-xs flex items-center gap-1">
                        <Users className="w-3 h-3" /> 1.2k watching
                      </span>
                    </div>
                    <span className="text-[#10B981] text-xs font-bold">Rs.15,200 earned</span>
                  </div>
                </div>
                {/* Live Content Area */}
                <div className="h-full bg-gradient-to-br from-[#1a0510] via-[#0A0305] to-[#150308] flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-r from-[#BFFF00] to-[#BEF264] flex items-center justify-center mx-auto mb-3 shadow-[0_0_40px_rgba(225,29,72,0.5)]">
                      <Radio className="w-8 h-8 text-white" />
                    </div>
                    <p className="text-white/40 text-sm">Premium Session</p>
                  </div>
                </div>
                {/* Floating Chats */}
                <div className="absolute bottom-16 left-3 right-3 space-y-2">
                  {[
                    { name: "Ankit", msg: "Sent Rs.500", color: "#10B981" },
                    { name: "Riya", msg: "Sent Rs.1,000", color: "#F59E0B" },
                    { name: "Mohit", msg: "Amazing session!", color: "#fff" },
                  ].map((c, i) => (
                    <motion.div key={i} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.3 }} className="flex items-center gap-2 bg-white/10 backdrop-blur-md rounded-full px-3 py-1.5">
                      <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-[10px] font-bold">{c.name[0]}</div>
                      <span className="text-xs"><span className="font-bold text-white/80">{c.name}</span> <span style={{ color: c.color }}>{c.msg}</span></span>
                    </motion.div>
                  ))}
                </div>
                {/* Bottom Bar */}
                <div className="absolute bottom-0 left-0 right-0 p-3 bg-black/60 backdrop-blur-md border-t border-white/10">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-white/10 rounded-full px-3 py-2 text-xs text-white/30">Send a message...</div>
                    <div className="w-8 h-8 rounded-full bg-[#BFFF00] flex items-center justify-center">
                      <Gift className="w-4 h-4 text-white" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-12 max-w-3xl mx-auto">
            {["Ticket-based access", "VIP rooms", "Real-time super chats", "Replay for premium"].map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-white/60">
                <Check className="w-4 h-4 text-[#BFFF00] flex-shrink-0" /> {f}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section className="py-24 md:py-32">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger} className="text-center mb-16">
            <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] font-bold text-[#BFFF00] mb-3">Real Results</motion.p>
            <motion.h2 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-3xl md:text-5xl font-bold tracking-tight">
              Creators Are <span className="bg-gradient-to-r from-[#10B981] to-[#34D399] bg-clip-text text-transparent">Earning Big</span>
            </motion.h2>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-6">
            {testimonials.map((t, i) => (
              <motion.div key={i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} className="bg-[#0A0305] border border-white/10 rounded-2xl p-6 hover:border-[#BFFF00]/30 transition-all" data-testid={`testimonial-${i}`}>
                <div className="flex items-center gap-1 mb-4">
                  {[...Array(5)].map((_, j) => <Star key={j} className="w-4 h-4 fill-[#F59E0B] text-[#F59E0B]" />)}
                </div>
                <p className="text-white/70 mb-6 leading-relaxed">"{t.quote}"</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-r from-[#BFFF00] to-[#BEF264] flex items-center justify-center text-sm font-bold">{t.avatar}</div>
                    <div>
                      <p className="text-sm font-semibold">{t.name}</p>
                      <p className="text-xs text-white/40">{t.role}</p>
                    </div>
                  </div>
                  <span className="text-sm font-bold text-[#10B981]">{t.earning}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="py-24 md:py-32">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger} className="text-center mb-20">
            <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] font-bold text-[#BFFF00] mb-3">Simple Setup</motion.p>
            <motion.h2 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-3xl md:text-5xl font-bold tracking-tight">
              Start in <span className="bg-gradient-to-r from-[#BFFF00] to-[#BEF264] bg-clip-text text-transparent">3 Steps</span>
            </motion.h2>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-8">
            {steps.map((s, i) => (
              <motion.div key={i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} className="relative text-center group">
                <span style={{ fontFamily: "Unbounded" }} className="text-[120px] font-black text-white/[0.03] absolute top-[-40px] left-1/2 -translate-x-1/2 select-none">{s.num}</span>
                <div className="relative pt-12">
                  <div className="w-16 h-16 rounded-2xl bg-[#BFFF00]/15 border border-[#BFFF00]/30 flex items-center justify-center mx-auto mb-6 group-hover:bg-[#BFFF00]/25 transition-all">
                    {i === 0 && <Send className="w-7 h-7 text-[#BFFF00]" />}
                    {i === 1 && <Crown className="w-7 h-7 text-[#BFFF00]" />}
                    {i === 2 && <Wallet className="w-7 h-7 text-[#BFFF00]" />}
                  </div>
                  <h3 style={{ fontFamily: "Unbounded" }} className="text-xl font-bold mb-3">{s.title}</h3>
                  <p className="text-white/50">{s.desc}</p>
                </div>
                {i < 2 && <ChevronRight className="hidden md:block absolute right-[-20px] top-1/2 w-6 h-6 text-white/10" />}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" className="py-24 md:py-32">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger} className="text-center mb-16">
            <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] font-bold text-[#BFFF00] mb-3">Pricing</motion.p>
            <motion.h2 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-3xl md:text-5xl font-bold tracking-tight">
              Invest in Your <span className="bg-gradient-to-r from-[#BFFF00] to-[#BEF264] bg-clip-text text-transparent">Growth</span>
            </motion.h2>
            <motion.p variants={fadeUp} className="text-white/50 mt-3">The tool pays for itself. One subscriber covers your monthly cost.</motion.p>
          </motion.div>

          {plansLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-[#BFFF00] animate-spin" />
            </div>
          ) : (
            <div className={`grid gap-6 items-stretch ${plans.length === 1 ? "max-w-md mx-auto" : plans.length === 2 ? "md:grid-cols-2 max-w-3xl mx-auto" : "md:grid-cols-3"}`}>
              {plans.map((p, i) => {
                const isFree = !p.price || p.price === 0;
                const isPopular = p.is_popular || false;
                const durationLabel = p.duration_days >= 365 ? `${Math.floor(p.duration_days / 365)} yr` : p.duration_days >= 30 ? `${Math.floor(p.duration_days / 30)} mo` : `${p.duration_days}d`;

                // Build feature badges
                const badges = [];
                if (p.ai_verify_enabled) badges.push("AI Verify");
                if (p.live_stream_enabled) badges.push("Live");
                if (p.paid_posts_enabled) badges.push("Paid Posts");

                return (
                  <motion.div key={p.id || i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}
                    className={`relative rounded-2xl p-8 border transition-all ${isPopular ? "bg-[#0A0305] border-[#BFFF00] scale-105 shadow-[0_0_40px_rgba(225,29,72,0.2)]" : "bg-[#0A0305] border-white/10 hover:border-white/20"}`}
                    data-testid={`pricing-${p.name.toLowerCase().replace(/\s+/g, "-")}`}
                  >
                    {isPopular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#BFFF00] text-white text-xs font-bold px-4 py-1 rounded-full">Most Popular</div>
                    )}
                    <div className="flex items-center gap-2 mb-2">
                      <Crown className="w-4 h-4 text-[#BFFF00]" />
                      <p className="text-sm text-white/40 uppercase tracking-wider font-bold">{p.name}</p>
                    </div>
                    <div className="mb-4">
                      <span style={{ fontFamily: "Unbounded" }} className="text-4xl font-black">{isFree ? "Free" : `Rs.${p.price.toLocaleString()}`}</span>
                      <span className="text-white/40 ml-1">/ {durationLabel}</span>
                    </div>

                    {/* Limits */}
                    <div className="flex gap-4 mb-4 text-xs text-white/50">
                      {p.max_subscribers && <span>Max Subscribers: {p.max_subscribers.toLocaleString()}</span>}
                      {p.max_broadcasts && <span>Max Broadcasts: {p.max_broadcasts}/day</span>}
                    </div>

                    {/* Feature badges */}
                    {badges.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-5">
                        {badges.map((b, bi) => (
                          <span key={bi} className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-white/8 text-white/60 border border-white/10">{b}</span>
                        ))}
                      </div>
                    )}

                    {/* Features list */}
                    {p.features?.length > 0 && (
                      <>
                        <div className="border-t border-white/6 my-4" />
                        <p className="text-xs font-bold text-white/50 uppercase tracking-wider mb-3">Features</p>
                        <ul className="space-y-2.5 mb-8">
                          {p.features.map((f, j) => (
                            <li key={j} className="flex items-center gap-2 text-sm text-white/70">
                              <Check className="w-4 h-4 text-[#BFFF00] flex-shrink-0" /> {f}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}

                    <button onClick={() => navigate("/login")}
                      className={`w-full py-3 rounded-full font-bold text-sm transition-all mt-auto ${isPopular ? "bg-[#BFFF00] hover:bg-[#84CC16] text-white shadow-[0_0_20px_rgba(225,29,72,0.4)] hover:scale-105" : "bg-white/10 hover:bg-white/20 text-white"}`}
                      data-testid={`pricing-cta-${p.name.toLowerCase().replace(/\s+/g, "-")}`}
                    >
                      {isFree ? "Start Free" : "Get Started"} <ArrowRight className="inline w-4 h-4 ml-1" />
                    </button>
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* REFERRAL */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <div className="bg-gradient-to-r from-[#BFFF00]/10 to-transparent border border-[#BFFF00]/20 rounded-2xl p-8 md:p-12 flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Gift className="w-5 h-5 text-[#BFFF00]" />
                <span className="text-sm font-bold text-[#BFFF00] uppercase tracking-wider">Referral Program</span>
              </div>
              <h3 style={{ fontFamily: "Unbounded" }} className="text-2xl font-bold mb-2">Earn 20% on Every Referral</h3>
              <p className="text-white/50">Invite creators. Earn commission on their subscription. Passive income, forever.</p>
            </div>
            <button onClick={() => navigate("/login")} className="bg-[#BFFF00] hover:bg-[#84CC16] text-white font-bold rounded-full px-8 py-3 shadow-[0_0_20px_rgba(225,29,72,0.3)] transition-all hover:scale-105 flex-shrink-0" data-testid="referral-cta">
              Join Program <ArrowRight className="inline w-4 h-4 ml-1" />
            </button>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="py-24 md:py-32 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-[#BFFF00]/10 via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto px-6 md:px-12 text-center relative">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger}>
            <motion.h2 variants={fadeUp} style={{ fontFamily: "Unbounded" }} className="text-4xl md:text-6xl font-black tracking-tight mb-6">
              Start Monetizing<br /><span className="bg-gradient-to-r from-[#BFFF00] via-[#A3E635] to-[#BEF264] bg-clip-text text-transparent">Today</span>
            </motion.h2>
            <motion.p variants={fadeUp} className="text-lg text-white/50 mb-10 max-w-xl mx-auto">
              Join 5,000+ creators who are turning their Telegram communities into revenue machines.
            </motion.p>
            <motion.div variants={fadeUp}>
              <button onClick={() => navigate("/login")} className="relative bg-[#BFFF00] hover:bg-[#84CC16] text-white font-bold rounded-full px-12 py-5 text-xl shadow-[0_0_40px_rgba(225,29,72,0.5)] transition-all hover:scale-105 hover:shadow-[0_0_60px_rgba(225,29,72,0.7)]" data-testid="final-cta">
                <span className="absolute inset-0 rounded-full animate-ping bg-[#BFFF00]/30" style={{ animationDuration: "2s" }} />
                <span className="relative flex items-center gap-2">Create Your First Paid Community <ArrowRight className="w-5 h-5" /></span>
              </button>
            </motion.div>
            <motion.p variants={fadeUp} className="text-sm text-white/30 mt-6">Free forever plan available. No credit card required.</motion.p>
          </motion.div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/5 py-12">
        <div className="max-w-7xl mx-auto px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#BFFF00] flex items-center justify-center">
              <Send className="w-4 h-4 text-white" />
            </div>
            <span style={{ fontFamily: "Unbounded" }} className="font-bold">TGSubsBot</span>
          </div>
          <p className="text-sm text-white/30">&copy; 2025 TGSubsBot. All rights reserved.</p>
          <div className="flex gap-6 text-sm text-white/40">
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Terms</a>
            <a href="#" className="hover:text-white transition-colors">Contact</a>
          </div>
        </div>
      </footer>

      {/* CSS Marquee Animation */}
      <style>{`
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-marquee {
          animation: marquee 30s linear infinite;
        }
      `}</style>
    </div>
  );
}
