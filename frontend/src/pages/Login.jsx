import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Eye, EyeOff, Bot, Phone, Mail, ArrowLeft } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
const handleGoogleLogin = () => {
  const redirectUrl = window.location.origin + '/';
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [loginMethod, setLoginMethod] = useState("email"); // "email" or "phone"
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    phone: "",
    otp: "",
  });
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const payload = isLogin
        ? { email: form.email, password: form.password }
        : { email: form.email, password: form.password, name: form.name, phone: form.phone };

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
      } catch (adminError) {
        // If admin check fails, just proceed
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("isFirstUser", "false");
        toast.success(isLogin ? "Welcome back!" : "Account created successfully!");
        
        if (user.dashboard_subscription_status === "active") {
          window.location.href = "/";
        } else {
          window.location.href = "/pricing";
        }
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSendOTP = async () => {
    if (!form.phone) {
      toast.error("Please enter phone number");
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/otp/send`, { phone: form.phone });
      toast.success("OTP sent to your phone!");
      setOtpSent(true);
      // For testing - show OTP if in test mode
      if (response.data.test_otp) {
        toast.info(`Test OTP: ${response.data.test_otp}`, { duration: 10000 });
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    if (!form.phone || !form.otp) {
      toast.error("Please enter phone and OTP");
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/otp/verify`, {
        phone: form.phone,
        otp: form.otp,
        name: form.name,
      });
      const { token, user } = response.data;

      localStorage.setItem("token", token);
      localStorage.setItem("user", JSON.stringify(user));
      
      // Check admin status
      try {
        const adminCheck = await axios.get(`${API}/auth/check-admin`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        localStorage.setItem("isFirstUser", adminCheck.data.is_admin ? "true" : "false");
      } catch {
        localStorage.setItem("isFirstUser", "false");
      }

      toast.success("Login successful!");
      
      if (user.dashboard_subscription_status === "active") {
        window.location.href = "/";
      } else {
        window.location.href = "/pricing";
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "OTP verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary via-primary/90 to-primary/80 p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <span className="font-heading text-2xl font-bold text-white">SubsBot</span>
          </div>
        </div>

        <div className="space-y-6">
          <h1 className="font-heading text-4xl font-bold text-white leading-tight">
            Manage Your Telegram
            <br />
            Subscriptions with Ease
          </h1>
          <p className="text-white/80 text-lg max-w-md">
            Automate subscriber management, payments, and channel access all in one powerful dashboard.
          </p>
        </div>

        <div className="text-white/60 text-sm">
          © 2025 SubsBot. All rights reserved.
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 justify-center mb-8">
            <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="font-heading text-xl font-bold">SubsBot</span>
          </div>

          {/* Login Method Toggle */}
          <div className="flex gap-2 p-1 bg-muted rounded-lg">
            <Button
              type="button"
              variant={loginMethod === "email" ? "default" : "ghost"}
              className="flex-1 gap-2"
              onClick={() => { setLoginMethod("email"); setOtpSent(false); }}
            >
              <Mail className="w-4 h-4" />
              Email
            </Button>
            <Button
              type="button"
              variant={loginMethod === "phone" ? "default" : "ghost"}
              className="flex-1 gap-2"
              onClick={() => { setLoginMethod("phone"); setOtpSent(false); }}
            >
              <Phone className="w-4 h-4" />
              Phone OTP
            </Button>
          </div>

          {/* Title */}
          <div className="text-center">
            <h2 className="font-heading text-3xl font-bold tracking-tight">
              {loginMethod === "phone" 
                ? "Login with Phone" 
                : isLogin ? "Welcome Back" : "Create Account"}
            </h2>
            <p className="text-muted-foreground mt-2">
              {loginMethod === "phone"
                ? "Enter your phone number to receive OTP"
                : isLogin
                  ? "Enter your credentials to access your dashboard"
                  : "Fill in your details to get started"}
            </p>
          </div>

          {/* Phone OTP Form */}
          {loginMethod === "phone" ? (
            <form onSubmit={handleVerifyOTP} className="space-y-4">
              {!otpSent ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone Number</Label>
                    <div className="flex gap-2">
                      <div className="flex items-center px-3 bg-muted rounded-md text-sm text-muted-foreground">
                        +91
                      </div>
                      <Input
                        id="phone"
                        type="tel"
                        placeholder="9876543210"
                        value={form.phone}
                        onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/\D/g, '').slice(0, 10) })}
                        className="flex-1 bg-muted/50 border-transparent focus:border-primary"
                        data-testid="phone-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="name">Name (Optional)</Label>
                    <Input
                      id="name"
                      type="text"
                      placeholder="Your name"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="bg-muted/50 border-transparent focus:border-primary"
                    />
                  </div>

                  <Button
                    type="button"
                    onClick={handleSendOTP}
                    className="w-full btn-hover"
                    disabled={loading || !form.phone || form.phone.length < 10}
                    data-testid="send-otp-btn"
                  >
                    {loading ? "Sending..." : "Send OTP"}
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    type="button"
                    variant="ghost"
                    className="gap-2 text-muted-foreground"
                    onClick={() => setOtpSent(false)}
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Change Number
                  </Button>

                  <div className="p-4 bg-muted/50 rounded-lg text-center">
                    <p className="text-sm text-muted-foreground">OTP sent to</p>
                    <p className="font-medium">+91 {form.phone}</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="otp">Enter OTP</Label>
                    <Input
                      id="otp"
                      type="text"
                      placeholder="123456"
                      value={form.otp}
                      onChange={(e) => setForm({ ...form, otp: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                      className="bg-muted/50 border-transparent focus:border-primary text-center text-2xl tracking-widest"
                      maxLength={6}
                      data-testid="otp-input"
                    />
                  </div>

                  <Button
                    type="submit"
                    className="w-full btn-hover"
                    disabled={loading || form.otp.length !== 6}
                    data-testid="verify-otp-btn"
                  >
                    {loading ? "Verifying..." : "Verify & Login"}
                  </Button>

                  <Button
                    type="button"
                    variant="ghost"
                    className="w-full"
                    onClick={handleSendOTP}
                    disabled={loading}
                  >
                    Resend OTP
                  </Button>
                </>
              )}
            </form>
          ) : (
            /* Email/Password Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="John Doe"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required={!isLogin}
                    className="bg-muted/50 border-transparent focus:border-primary"
                    data-testid="name-input"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                  className="bg-muted/50 border-transparent focus:border-primary"
                  data-testid="email-input"
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
                    className="bg-muted/50 border-transparent focus:border-primary pr-10"
                    data-testid="password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
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
          )}

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Or continue with
              </span>
            </div>
          </div>

          {/* Google Login Button */}
          <Button
            type="button"
            variant="outline"
            className="w-full gap-2"
            onClick={handleGoogleLogin}
            data-testid="google-login-btn"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </Button>

          {/* Toggle Login/Register (only for email method) */}
          {loginMethod === "email" && (
            <p className="text-center text-sm text-muted-foreground">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-primary hover:underline font-medium"
                data-testid="toggle-auth-btn"
              >
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
