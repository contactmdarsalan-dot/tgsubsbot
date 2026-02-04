import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Eye, EyeOff, Bot } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const handleGoogleLogin = () => {
  const redirectUrl = window.location.origin + '/';
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
  });
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const payload = isLogin
        ? { email: form.email, password: form.password }
        : form;

      const response = await axios.post(`${API}${endpoint}`, payload);
      const { token, user } = response.data;

      localStorage.setItem("token", token);
      
      // Check if this is the first user (admin)
      try {
        const adminCheck = await axios.get(`${API}/auth/check-admin`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const isAdmin = adminCheck.data.is_admin;
        
        // Store admin status in user object AND localStorage
        user.isAdmin = isAdmin;
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("isFirstUser", isAdmin ? "true" : "false");
        
        toast.success(isLogin ? "Welcome back!" : "Account created successfully!");
        
        // Use window.location for full page reload to ensure state is fresh
        if (isAdmin || user.dashboard_subscription_status === "active") {
          window.location.href = "/";
        } else {
          window.location.href = "/pricing";
        }
      } catch {
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("isFirstUser", "false");
        window.location.href = "/pricing";
      }
    } catch (error) {
      toast.error(
        error.response?.data?.detail || "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Image */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-gradient-to-br from-slate-100 to-slate-200">
        <img
          src="https://images.unsplash.com/photo-1759270463243-414a287681be?crop=entropy&cs=srgb&fm=jpg&q=85"
          alt="Abstract geometric background"
          className="absolute inset-0 w-full h-full object-cover opacity-80"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-transparent" />
        <div className="relative z-10 flex flex-col justify-center px-12">
          <div className="bg-white/90 backdrop-blur-sm rounded-lg p-8 max-w-md">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-primary rounded-lg flex items-center justify-center">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <h1 className="font-heading text-3xl font-bold tracking-tight">SubsBot</h1>
            </div>
            <p className="text-muted-foreground leading-relaxed">
              Automate your Telegram channel subscriptions. Manage payments, send
              reminders, and grow your community effortlessly.
            </p>
            <div className="mt-6 space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                <span>Auto channel add/remove</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                <span>Razorpay & QR payments</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                <span>Smart renewal reminders</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden mb-8 text-center">
            <div className="inline-flex items-center gap-3">
              <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <h1 className="font-heading text-2xl font-bold tracking-tight">SubsBot</h1>
            </div>
          </div>

          <div className="space-y-6">
            <div>
              <h2 className="font-heading text-3xl font-bold tracking-tight">
                {isLogin ? "Welcome Back" : "Create Account"}
              </h2>
              <p className="text-muted-foreground mt-2">
                {isLogin
                  ? "Sign in to manage your subscriptions"
                  : "Start managing your Telegram subscriptions"}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="Your name"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required={!isLogin}
                    data-testid="register-name-input"
                    className="bg-muted/50 border-transparent focus:border-primary focus:bg-background transition-all"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                  data-testid="login-email-input"
                  className="bg-muted/50 border-transparent focus:border-primary focus:bg-background transition-all"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    required
                    data-testid="login-password-input"
                    className="bg-muted/50 border-transparent focus:border-primary focus:bg-background transition-all pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full btn-hover"
                disabled={loading}
                data-testid="login-submit-btn"
              >
                {loading ? "Please wait..." : isLogin ? "Sign In" : "Create Account"}
              </Button>
            </form>

            <div className="text-center">
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-sm text-muted-foreground hover:text-primary transition-colors"
                data-testid="toggle-auth-mode"
              >
                {isLogin
                  ? "Don't have an account? Sign up"
                  : "Already have an account? Sign in"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
