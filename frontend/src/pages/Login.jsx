import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Eye, EyeOff, Heart, Phone, Mail, ArrowLeft, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const handleGoogleLogin = () => {
  const redirectUrl = window.location.origin + '/';
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [loginMethod, setLoginMethod] = useState("email");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [forgotPassword, setForgotPassword] = useState(false);
  const [resetStep, setResetStep] = useState(1); // 1=email, 2=otp+newpw
  const [resetForm, setResetForm] = useState({ email: "", otp: "", new_password: "" });
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
      
      try {
        const adminCheck = await axios.get(`${API}/auth/check-admin`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const isAdmin = adminCheck.data.is_admin;
        
        user.isAdmin = isAdmin;
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("isFirstUser", isAdmin ? "true" : "false");
        
        toast.success(isLogin ? "Welcome back!" : "Account created successfully!");
        
        const isSuperAdmin = user.role === "super_admin";
        if (isAdmin || isSuperAdmin || user.dashboard_subscription_status === "active") {
          window.location.href = "/dashboard";
        } else {
          window.location.href = "/pricing";
        }
      } catch (adminError) {
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("isFirstUser", "false");
        toast.success(isLogin ? "Welcome back!" : "Account created successfully!");
        
        const isSuperAdmin = user.role === "super_admin";
        if (isSuperAdmin || user.dashboard_subscription_status === "active") {
          window.location.href = "/dashboard";
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

  const handleSendResetOTP = async () => {
    if (!resetForm.email) {
      toast.error("Please enter your email");
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/forgot-password`, { email: resetForm.email });
      toast.success("Reset code sent to your email!");
      if (response.data.test_otp) {
        toast.info(`Reset Code: ${response.data.test_otp}`, { duration: 15000 });
      }
      setResetStep(2);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send reset code");
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!resetForm.otp || !resetForm.new_password) {
      toast.error("Please enter the code and new password");
      return;
    }
    if (resetForm.new_password.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    setLoading(true);
    try {
      await axios.post(`${API}/auth/reset-password`, resetForm);
      toast.success("Password reset successful! Please login.");
      setForgotPassword(false);
      setResetStep(1);
      setResetForm({ email: "", otp: "", new_password: "" });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to reset password");
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
        window.location.href = "/dashboard";
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
    <div className="min-h-screen flex bg-background">
      {/* Left Panel - Romance Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        {/* Background Image with Overlay */}
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: "url('https://images.pexels.com/photos/4722583/pexels-photo-4722583.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940')"
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-lime-950/95 via-lime-900/90 to-red-950/95" />
        
        {/* Content */}
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center backdrop-blur-sm border border-white/10">
                <Heart className="w-6 h-6 text-lime-300" fill="currentColor" />
              </div>
              <span className="font-serif text-2xl font-semibold text-white">TGSubsBot</span>
            </div>
          </div>

          <div className="space-y-8">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-lime-300">
                <Sparkles className="w-5 h-5" />
                <span className="text-sm font-medium tracking-wider uppercase">Premium Experience</span>
              </div>
              <h1 className="font-serif text-5xl font-semibold text-white leading-tight">
                Exclusive Content,
                <br />
                <span className="text-gradient-romance">Intimate Connections</span>
              </h1>
            </div>
            <p className="text-lime-200/80 text-lg max-w-md leading-relaxed">
              Manage your premium subscribers, live sessions, and exclusive content with our elegant dashboard designed for creators.
            </p>
            
            {/* Stats */}
            <div className="flex gap-8 pt-4">
              <div>
                <p className="font-serif text-3xl font-semibold text-white">5000+</p>
                <p className="text-lime-300/70 text-sm">Happy Subscribers</p>
              </div>
              <div>
                <p className="font-serif text-3xl font-semibold text-white">99%</p>
                <p className="text-lime-300/70 text-sm">Satisfaction Rate</p>
              </div>
            </div>
          </div>

          <div className="text-lime-300/50 text-sm">
            © 2025 TGSubsBot. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 justify-center mb-8">
            <div className="w-12 h-12 bg-gradient-to-br from-lime-600 to-red-700 rounded-2xl flex items-center justify-center shadow-lg glow-rose">
              <Heart className="w-6 h-6 text-white" fill="currentColor" />
            </div>
            <span className="font-serif text-2xl font-semibold">TGSubsBot</span>
          </div>

          {/* Login Method Toggle */}
          {!forgotPassword ? (
            <>
            <div className="flex gap-2 p-1.5 bg-white/5 rounded-2xl border border-white/10">
            <Button
              type="button"
              variant={loginMethod === "email" ? "default" : "ghost"}
              className={`flex-1 gap-2 rounded-xl transition-all duration-300 ${loginMethod === "email" ? "btn-romance shadow-lg" : "hover:bg-muted"}`}
              onClick={() => { setLoginMethod("email"); setOtpSent(false); }}
            >
              <Mail className="w-4 h-4" strokeWidth={1.5} />
              Email
            </Button>
            <Button
              type="button"
              variant={loginMethod === "phone" ? "default" : "ghost"}
              className={`flex-1 gap-2 rounded-xl transition-all duration-300 ${loginMethod === "phone" ? "btn-romance shadow-lg" : "hover:bg-muted"}`}
              onClick={() => { setLoginMethod("phone"); setOtpSent(false); }}
            >
              <Phone className="w-4 h-4" strokeWidth={1.5} />
              Phone OTP
            </Button>
          </div>

          {/* Title */}
          <div className="text-center space-y-2">
            <h2 className="font-serif text-3xl font-semibold tracking-tight">
              {loginMethod === "phone" 
                ? "Login with Phone" 
                : isLogin ? "Welcome Back" : "Join Us"}
            </h2>
            <p className="text-muted-foreground">
              {loginMethod === "phone"
                ? "Enter your phone number to receive OTP"
                : isLogin
                  ? "Sign in to access your exclusive dashboard"
                  : "Create your account to get started"}
            </p>
          </div>

          {/* Phone OTP Form */}
          {loginMethod === "phone" ? (
            <form onSubmit={handleVerifyOTP} className="space-y-5">
              {!otpSent ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="phone" className="text-sm font-medium">Phone Number</Label>
                    <div className="flex gap-2">
                      <div className="flex items-center px-4 bg-white/5 rounded-xl text-sm text-white/60 border border-white/10">
                        +91
                      </div>
                      <Input
                        id="phone"
                        type="tel"
                        placeholder="9876543210"
                        value={form.phone}
                        onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/\D/g, '').slice(0, 10) })}
                    className="bg-muted/30 border-border/50 rounded-xl h-12 focus:border-primary/50 focus:ring-primary/20 text-white placeholder:text-white/30"
                    data-testid="phone-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="name" className="text-sm font-medium">Name (Optional)</Label>
                    <Input
                      id="name"
                      type="text"
                      placeholder="Your name"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="bg-white/5 border-white/10 rounded-xl h-12 text-white placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                    />
                  </div>

                  <Button
                    type="button"
                    onClick={handleSendOTP}
                    className="w-full btn-romance h-12 text-base font-medium"
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
                    className="gap-2 text-muted-foreground hover:text-foreground"
                    onClick={() => setOtpSent(false)}
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Change Number
                  </Button>

                  <div className="p-4 bg-white/5 rounded-2xl text-center border border-white/10">
                    <p className="text-sm text-muted-foreground">OTP sent to</p>
                    <p className="font-medium text-foreground">+91 {form.phone}</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="otp" className="text-sm font-medium">Enter OTP</Label>
                    <Input
                      id="otp"
                      type="text"
                      placeholder="123456"
                      value={form.otp}
                      onChange={(e) => setForm({ ...form, otp: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                      className="bg-white/5 border-white/10 rounded-xl h-14 text-center text-2xl text-white tracking-[0.5em] font-mono placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                      maxLength={6}
                      data-testid="otp-input"
                    />
                  </div>

                  <Button
                    type="submit"
                    className="w-full btn-romance h-12 text-base font-medium"
                    disabled={loading || form.otp.length !== 6}
                    data-testid="verify-otp-btn"
                  >
                    {loading ? "Verifying..." : "Verify & Login"}
                  </Button>

                  <Button
                    type="button"
                    variant="ghost"
                    className="w-full text-muted-foreground hover:text-primary"
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
            <form onSubmit={handleSubmit} className="space-y-5">
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-sm font-medium">Full Name</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="John Doe"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required={!isLogin}
                    className="bg-white/5 border-white/10 rounded-xl h-12 text-white placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                    data-testid="name-input"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                  className="bg-white/5 border-white/10 rounded-xl h-12 text-white placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                  data-testid="email-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    required
                    className="bg-white/5 border-white/10 rounded-xl h-12 pr-12 text-white placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                    data-testid="password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" strokeWidth={1.5} /> : <Eye className="w-5 h-5" strokeWidth={1.5} />}
                  </button>
                </div>
              </div>

              {isLogin && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => { setForgotPassword(true); setResetForm({ ...resetForm, email: form.email }); }}
                    className="text-xs text-primary hover:text-primary/80 transition-colors"
                    data-testid="forgot-password-btn"
                  >
                    Forgot Password?
                  </button>
                </div>
              )}

              <Button
                type="submit"
                className="w-full btn-romance h-12 text-base font-medium"
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
              <span className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="px-4 text-white/40" style={{ background: "hsl(0, 0%, 2%)" }}>
                Or continue with
              </span>
            </div>
          </div>

          {/* Google Login Button */}
          <Button
            type="button"
            variant="outline"
            className="w-full gap-3 h-12 rounded-xl border-white/10 bg-white/5 text-white hover:bg-white/10 hover:border-primary/30 transition-all duration-300"
            onClick={handleGoogleLogin}
            data-testid="google-login-btn"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#EA4335"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#4285F4"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </Button>

          {/* Toggle Login/Register */}
          {loginMethod === "email" && (
            <p className="text-center text-sm text-muted-foreground">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-primary hover:text-primary/80 font-medium transition-colors"
                data-testid="toggle-auth-btn"
              >
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </p>
          )}
          </>
          ) : (
            /* Forgot Password Flow */
            <>
              <div className="text-center space-y-2">
                <h2 className="font-serif text-3xl font-semibold tracking-tight">Reset Password</h2>
                <p className="text-muted-foreground">
                  {resetStep === 1 ? "Enter your email to receive a reset code" : "Enter the code and your new password"}
                </p>
              </div>

              {resetStep === 1 ? (
                <div className="space-y-5">
                  <div className="space-y-2">
                    <Label htmlFor="reset-email" className="text-sm font-medium">Email Address</Label>
                    <Input
                      id="reset-email"
                      type="email"
                      placeholder="you@example.com"
                      value={resetForm.email}
                      onChange={(e) => setResetForm({ ...resetForm, email: e.target.value })}
                      className="bg-white/5 border-white/10 rounded-xl h-12 text-white placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                      data-testid="reset-email-input"
                    />
                  </div>
                  <Button
                    type="button"
                    onClick={handleSendResetOTP}
                    className="w-full btn-romance h-12 text-base font-medium"
                    disabled={loading || !resetForm.email}
                    data-testid="send-reset-code-btn"
                  >
                    {loading ? "Sending..." : "Send Reset Code"}
                  </Button>
                </div>
              ) : (
                <form onSubmit={handleResetPassword} className="space-y-5">
                  <div className="p-4 bg-white/5 rounded-2xl text-center border border-white/10">
                    <p className="text-sm text-muted-foreground">Reset code sent to</p>
                    <p className="font-medium text-foreground">{resetForm.email}</p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reset-otp" className="text-sm font-medium">Reset Code</Label>
                    <Input
                      id="reset-otp"
                      type="text"
                      placeholder="123456"
                      value={resetForm.otp}
                      onChange={(e) => setResetForm({ ...resetForm, otp: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                      className="bg-white/5 border-white/10 rounded-xl h-14 text-center text-2xl text-white tracking-[0.5em] font-mono placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                      maxLength={6}
                      data-testid="reset-otp-input"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reset-new-password" className="text-sm font-medium">New Password</Label>
                    <Input
                      id="reset-new-password"
                      type="password"
                      placeholder="Enter new password (min 6 chars)"
                      value={resetForm.new_password}
                      onChange={(e) => setResetForm({ ...resetForm, new_password: e.target.value })}
                      className="bg-white/5 border-white/10 rounded-xl h-12 text-white placeholder:text-white/30 focus:border-primary/50 focus:ring-primary/20"
                      data-testid="reset-new-password-input"
                    />
                  </div>

                  <Button
                    type="submit"
                    className="w-full btn-romance h-12 text-base font-medium"
                    disabled={loading || resetForm.otp.length !== 6 || !resetForm.new_password}
                    data-testid="reset-password-btn"
                  >
                    {loading ? "Resetting..." : "Reset Password"}
                  </Button>
                </form>
              )}

              <p className="text-center text-sm text-muted-foreground">
                <button
                  type="button"
                  onClick={() => { setForgotPassword(false); setResetStep(1); }}
                  className="text-primary hover:text-primary/80 font-medium transition-colors"
                >
                  Back to Login
                </button>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
