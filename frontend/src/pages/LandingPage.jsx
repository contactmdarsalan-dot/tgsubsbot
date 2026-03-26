import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { 
  Heart, 
  Sparkles, 
  Shield, 
  Zap, 
  Video, 
  Radio, 
  Lock, 
  CreditCard,
  ArrowRight,
  Check,
  Star,
  Users,
  Play,
  ChevronDown,
  MessageCircle,
  Crown
} from "lucide-react";

export default function LandingPage() {
  const [scrollY, setScrollY] = useState(0);
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const features = [
    {
      icon: Lock,
      title: "Paid Posts",
      description: "Monetize exclusive content with blurred previews that unlock after payment"
    },
    {
      icon: Radio,
      title: "Live Streams",
      description: "Host premium live sessions with ticketed access and real-time engagement"
    },
    {
      icon: Video,
      title: "Video Calls",
      description: "Offer private 1-on-1 video call bookings with automated scheduling"
    },
    {
      icon: CreditCard,
      title: "Instant Payments",
      description: "UPI & QR code payments with AI-powered screenshot verification"
    },
    {
      icon: Users,
      title: "Subscription Plans",
      description: "Create multiple tiers with custom pricing, duration, and benefits"
    },
    {
      icon: MessageCircle,
      title: "Telegram Bot",
      description: "Fully automated bot handles subscriptions, payments, and access"
    }
  ];

  const testimonials = [
    {
      name: "Priya S.",
      role: "Content Creator",
      content: "TGSubsBot tripled my monthly earnings. The automated payment verification is a lifesaver!",
      rating: 5
    },
    {
      name: "Rahul M.",
      role: "Influencer",
      content: "Finally a solution that handles everything. My subscribers love the seamless experience.",
      rating: 5
    },
    {
      name: "Ananya K.",
      role: "Model",
      content: "The live stream feature is incredible. I made ₹50,000 in my first live session!",
      rating: 5
    }
  ];

  const stats = [
    { value: "5000+", label: "Happy Subscribers" },
    { value: "₹10L+", label: "Processed Monthly" },
    { value: "99.9%", label: "Uptime" },
    { value: "24/7", label: "Support" }
  ];

  return (
    <div className="min-h-screen bg-background overflow-hidden">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-border/30">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-rose-600 to-red-700 flex items-center justify-center shadow-lg glow-rose">
                <Heart className="w-5 h-5 text-white" fill="currentColor" />
              </div>
              <span className="font-serif text-xl font-semibold">TGSubsBot</span>
            </div>
            
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Features</a>
              <a href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Pricing</a>
              <a href="#testimonials" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Reviews</a>
            </div>

            <div className="flex items-center gap-3">
              {token ? (
                <Button onClick={() => navigate("/dashboard")} className="btn-romance gap-2">
                  Dashboard <ArrowRight className="w-4 h-4" />
                </Button>
              ) : (
                <>
                  <Button variant="ghost" onClick={() => navigate("/login")} className="hidden sm:flex">
                    Sign In
                  </Button>
                  <Button onClick={() => navigate("/login")} className="btn-romance gap-2">
                    Get Started <ArrowRight className="w-4 h-4" />
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center pt-20">
        {/* Background Image */}
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: "url('https://images.pexels.com/photos/5086779/pexels-photo-5086779.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940')",
            transform: `translateY(${scrollY * 0.3}px)`
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/95 to-background/80" />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-background/50" />
        
        <div className="relative z-10 max-w-7xl mx-auto px-6 py-20">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8 animate-fade-in-up">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20">
                <Sparkles className="w-4 h-4 text-primary" />
                <span className="text-sm text-primary font-medium">Premium Subscription Platform</span>
              </div>

              {/* Heading */}
              <h1 className="font-serif text-5xl md:text-6xl lg:text-7xl font-semibold leading-tight">
                Monetize Your
                <span className="block text-gradient-romance">Exclusive Content</span>
              </h1>

              {/* Subheading */}
              <p className="text-xl text-muted-foreground max-w-lg leading-relaxed">
                The ultimate Telegram subscription bot for creators. Paid posts, live streams, video calls, and automated payments - all in one elegant platform.
              </p>

              {/* CTA Buttons */}
              <div className="flex flex-wrap gap-4">
                <Button 
                  size="lg" 
                  onClick={() => navigate("/login")} 
                  className="btn-romance h-14 px-8 text-lg gap-2"
                >
                  Start Free Trial <ArrowRight className="w-5 h-5" />
                </Button>
                <Button 
                  size="lg" 
                  variant="outline" 
                  className="h-14 px-8 text-lg gap-2 border-border/50 hover:bg-muted/50"
                >
                  <Play className="w-5 h-5" /> Watch Demo
                </Button>
              </div>

              {/* Social Proof */}
              <div className="flex items-center gap-6 pt-4">
                <div className="flex -space-x-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div 
                      key={i} 
                      className="w-10 h-10 rounded-full bg-gradient-to-br from-rose-400 to-red-600 border-2 border-background flex items-center justify-center text-xs font-semibold text-white"
                    >
                      {String.fromCharCode(65 + i)}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="flex items-center gap-1">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Star key={i} className="w-4 h-4 text-amber-500 fill-amber-500" />
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground">5000+ creators trust us</p>
                </div>
              </div>
            </div>

            {/* Hero Visual */}
            <div className="hidden lg:block relative">
              <div className="relative">
                {/* Floating Cards */}
                <div className="absolute -top-10 -left-10 glass-card p-4 rounded-2xl animate-float" style={{ animationDelay: '0s' }}>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                      <CreditCard className="w-6 h-6 text-emerald-500" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Payment Received</p>
                      <p className="font-serif font-semibold text-emerald-500">+₹2,499</p>
                    </div>
                  </div>
                </div>

                <div className="absolute -bottom-10 -right-10 glass-card p-4 rounded-2xl animate-float" style={{ animationDelay: '0.5s' }}>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                      <Users className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">New Subscriber</p>
                      <p className="font-serif font-semibold">VIP Gold Monthly</p>
                    </div>
                  </div>
                </div>

                <div className="absolute top-1/2 -right-20 glass-card p-4 rounded-2xl animate-float" style={{ animationDelay: '1s' }}>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-rose-500/20 flex items-center justify-center animate-pulse">
                      <Radio className="w-6 h-6 text-rose-500" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Live Now</p>
                      <p className="font-serif font-semibold text-rose-500">47 Viewers</p>
                    </div>
                  </div>
                </div>

                {/* Main Image */}
                <div className="romance-card p-3 rounded-3xl glow-rose">
                  <img 
                    src="https://images.unsplash.com/photo-1671691302268-e316f81c7b3e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NTJ8MHwxfHNlYXJjaHwyfHxyb21hbnRpYyUyMGNvdXBsZSUyMGludGltYXRlJTIwcHJlbWl1bSUyMGx1eHVyeXxlbnwwfHx8fDE3NzQ1NjU5OTB8MA&ixlib=rb-4.1.0&q=85"
                    alt="Premium Experience"
                    className="rounded-2xl w-full h-80 object-cover"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Scroll Indicator */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 animate-bounce">
          <ChevronDown className="w-8 h-8 text-muted-foreground" />
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 border-y border-border/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, index) => (
              <div key={index} className="text-center">
                <p className="font-serif text-4xl md:text-5xl font-semibold text-gradient-romance">
                  {stat.value}
                </p>
                <p className="text-muted-foreground mt-2">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
              <Zap className="w-4 h-4 text-primary" />
              <span className="text-sm text-primary font-medium">Powerful Features</span>
            </div>
            <h2 className="font-serif text-4xl md:text-5xl font-semibold mb-4">
              Everything You Need to
              <span className="text-gradient-romance"> Succeed</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              From content monetization to automated payments, we've got you covered
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <div 
                key={index} 
                className="romance-card p-8 group hover:glow-rose transition-all duration-300"
              >
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-6 group-hover:bg-primary/20 transition-colors">
                  <feature.icon className="w-7 h-7 text-primary" strokeWidth={1.5} />
                </div>
                <h3 className="font-serif text-xl font-semibold mb-3">{feature.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 bg-muted/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
              <Crown className="w-4 h-4 text-primary" />
              <span className="text-sm text-primary font-medium">Simple Pricing</span>
            </div>
            <h2 className="font-serif text-4xl md:text-5xl font-semibold mb-4">
              Start Growing
              <span className="text-gradient-romance"> Today</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Choose the plan that fits your needs
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {/* Starter */}
            <div className="romance-card p-8">
              <h3 className="font-serif text-xl font-semibold mb-2">Starter</h3>
              <p className="text-muted-foreground mb-6">Perfect for beginners</p>
              <div className="mb-6">
                <span className="font-serif text-4xl font-semibold">₹999</span>
                <span className="text-muted-foreground">/month</span>
              </div>
              <ul className="space-y-3 mb-8">
                {["Up to 100 subscribers", "Basic analytics", "UPI payments", "Email support"].map((item, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-emerald-500" />
                    {item}
                  </li>
                ))}
              </ul>
              <Button variant="outline" className="w-full rounded-xl h-12">
                Get Started
              </Button>
            </div>

            {/* Pro - Featured */}
            <div className="romance-card p-8 border-primary/50 glow-rose relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary rounded-full text-xs font-medium text-white">
                Most Popular
              </div>
              <h3 className="font-serif text-xl font-semibold mb-2">Pro</h3>
              <p className="text-muted-foreground mb-6">For growing creators</p>
              <div className="mb-6">
                <span className="font-serif text-4xl font-semibold">₹2,499</span>
                <span className="text-muted-foreground">/month</span>
              </div>
              <ul className="space-y-3 mb-8">
                {["Unlimited subscribers", "Advanced analytics", "All payment methods", "Live streaming", "Priority support"].map((item, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-emerald-500" />
                    {item}
                  </li>
                ))}
              </ul>
              <Button className="w-full btn-romance h-12">
                Get Started
              </Button>
            </div>

            {/* Enterprise */}
            <div className="romance-card p-8">
              <h3 className="font-serif text-xl font-semibold mb-2">Enterprise</h3>
              <p className="text-muted-foreground mb-6">For large teams</p>
              <div className="mb-6">
                <span className="font-serif text-4xl font-semibold">Custom</span>
              </div>
              <ul className="space-y-3 mb-8">
                {["Everything in Pro", "Custom integrations", "Dedicated manager", "SLA guarantee", "White-label option"].map((item, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-emerald-500" />
                    {item}
                  </li>
                ))}
              </ul>
              <Button variant="outline" className="w-full rounded-xl h-12">
                Contact Sales
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="font-serif text-4xl md:text-5xl font-semibold mb-4">
              Loved by
              <span className="text-gradient-romance"> Creators</span>
            </h2>
            <p className="text-xl text-muted-foreground">
              See what our users have to say
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, index) => (
              <div key={index} className="romance-card p-8">
                <div className="flex items-center gap-1 mb-4">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <Star key={i} className="w-5 h-5 text-amber-500 fill-amber-500" />
                  ))}
                </div>
                <p className="text-lg mb-6 leading-relaxed">"{testimonial.content}"</p>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-rose-500 to-red-600 flex items-center justify-center text-white font-semibold">
                    {testimonial.name.charAt(0)}
                  </div>
                  <div>
                    <p className="font-semibold">{testimonial.name}</p>
                    <p className="text-sm text-muted-foreground">{testimonial.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="romance-card p-12 md:p-16 glow-rose">
            <h2 className="font-serif text-4xl md:text-5xl font-semibold mb-6">
              Ready to Start
              <span className="text-gradient-romance"> Earning?</span>
            </h2>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              Join thousands of creators who are already monetizing their content with TGSubsBot
            </p>
            <Button 
              size="lg" 
              onClick={() => navigate("/login")} 
              className="btn-romance h-14 px-10 text-lg gap-2"
            >
              Get Started Free <ArrowRight className="w-5 h-5" />
            </Button>
            <p className="text-sm text-muted-foreground mt-4">
              No credit card required • 7-day free trial
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-border/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-rose-600 to-red-700 flex items-center justify-center">
                <Heart className="w-5 h-5 text-white" fill="currentColor" />
              </div>
              <span className="font-serif text-xl font-semibold">TGSubsBot</span>
            </div>
            
            <div className="flex items-center gap-8 text-sm text-muted-foreground">
              <a href="#" className="hover:text-foreground transition-colors">Privacy</a>
              <a href="#" className="hover:text-foreground transition-colors">Terms</a>
              <a href="#" className="hover:text-foreground transition-colors">Support</a>
            </div>

            <p className="text-sm text-muted-foreground">
              © 2025 TGSubsBot. All rights reserved.
            </p>
          </div>
        </div>
      </footer>

      {/* Floating Animation Keyframes */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
        }
        .animate-float {
          animation: float 6s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
