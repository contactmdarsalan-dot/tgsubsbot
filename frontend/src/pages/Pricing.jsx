import { useState, useEffect } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { Check, Crown, Zap, Star, MessageCircle, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const plans = [
  {
    id: "1month",
    name: "1 Month",
    price: 4999,
    duration: "30 days",
    features: [
      "Full Dashboard Access",
      "Unlimited Subscribers",
      "Telegram Bot Integration",
      "Payment Management",
      "Auto Reminders",
      "Email Support"
    ],
    icon: Zap
  },
  {
    id: "6month",
    name: "6 Months",
    price: 24999,
    duration: "180 days",
    popular: true,
    save: "17%",
    features: [
      "Everything in 1 Month",
      "Priority Support",
      "Advanced Analytics",
      "Multiple Bots",
      "Custom Branding",
      "API Access"
    ],
    icon: Star
  },
  {
    id: "12month",
    name: "12 Months",
    price: 44999,
    duration: "365 days",
    save: "25%",
    features: [
      "Everything in 6 Months",
      "Dedicated Support",
      "White Label Option",
      "Custom Integrations",
      "Training Session",
      "SLA Guarantee"
    ],
    icon: Crown
  }
];

export default function Pricing({ onSubscribed }) {
  const [loading, setLoading] = useState(null);
  const [razorpayLoaded, setRazorpayLoaded] = useState(false);
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  // Load Razorpay script
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => setRazorpayLoaded(true);
    document.body.appendChild(script);
    
    return () => {
      document.body.removeChild(script);
    };
  }, []);

  const handleSelectPlan = async (planId) => {
    if (!razorpayLoaded) {
      toast.error("Payment gateway loading... Please try again.");
      return;
    }
    
    setLoading(planId);
    
    try {
      // Create Razorpay order
      const response = await axios.post(
        `${API}/dashboard-subscription/create-order`,
        { plan_id: planId },
        getAuthHeaders()
      );
      
      const { order_id, amount, key_id } = response.data;
      const plan = plans.find(p => p.id === planId);
      
      // Open Razorpay checkout
      const options = {
        key: key_id,
        amount: amount * 100,
        currency: "INR",
        name: "SubsBot Pro",
        description: `${plan.name} Subscription`,
        order_id: order_id,
        handler: async function (response) {
          // Verify payment
          try {
            const verifyResponse = await axios.post(
              `${API}/dashboard-subscription/verify-payment`,
              {
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature
              },
              getAuthHeaders()
            );
            
            toast.success("Payment successful! Subscription activated.");
            
            // Update local user data
            const updatedUser = {
              ...user,
              dashboard_subscription_status: "active",
              dashboard_plan: planId
            };
            localStorage.setItem("user", JSON.stringify(updatedUser));
            
            // Redirect to dashboard
            if (onSubscribed) {
              onSubscribed();
            }
            navigate("/");
            window.location.reload();
          } catch (error) {
            toast.error("Payment verification failed. Please contact support.");
          }
        },
        prefill: {
          name: user.name || "",
          email: user.email || "",
          contact: user.phone || ""
        },
        theme: {
          color: "#3b82f6"
        },
        modal: {
          ondismiss: function() {
            setLoading(null);
          }
        }
      };
      
      const razorpay = new window.Razorpay(options);
      razorpay.open();
      
    } catch (error) {
      console.error("Payment error:", error);
      toast.error(error.response?.data?.detail || "Failed to initiate payment");
    } finally {
      setLoading(null);
    }
  };

  const handleContactUs = () => {
    window.location.href = "mailto:nikhil@onlyforyou.club?subject=Lifetime%20Access%20Inquiry&body=Hi,%20I%20am%20interested%20in%20the%20Lifetime%20Access%20plan.";
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/30 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <Badge className="mb-4 bg-primary/10 text-primary border-primary/20">
            SubsBot Pro
          </Badge>
          <h1 className="font-heading text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Choose Your Plan
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Get full access to SubsBot Dashboard and start managing your Telegram subscriptions like a pro
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {plans.map((plan) => {
            const Icon = plan.icon;
            const isLoading = loading === plan.id;
            return (
              <Card 
                key={plan.id} 
                className={`relative border-2 transition-all duration-300 hover:border-primary/50 ${
                  plan.popular ? "border-primary shadow-lg scale-105" : "border-border"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-primary text-primary-foreground">
                      Most Popular
                    </Badge>
                  </div>
                )}
                {plan.save && (
                  <div className="absolute -top-3 right-4">
                    <Badge className="bg-green-500 text-white">
                      Save {plan.save}
                    </Badge>
                  </div>
                )}
                <CardHeader className="text-center pb-4">
                  <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Icon className="w-6 h-6 text-primary" />
                  </div>
                  <CardTitle className="font-heading text-2xl font-bold">
                    {plan.name}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">{plan.duration}</p>
                </CardHeader>
                <CardContent className="text-center">
                  <div className="mb-6">
                    <span className="font-heading text-5xl font-bold">₹{plan.price.toLocaleString()}</span>
                  </div>
                  
                  <ul className="space-y-3 mb-6 text-left">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  
                  <Button 
                    className={`w-full ${plan.popular ? "btn-hover" : ""}`}
                    variant={plan.popular ? "default" : "outline"}
                    onClick={() => handleSelectPlan(plan.id)}
                    disabled={isLoading || loading !== null}
                    data-testid={`plan-${plan.id}-btn`}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      "Get Started"
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Lifetime Plan */}
        <Card className="max-w-2xl mx-auto border-2 border-dashed border-primary/30 bg-primary/5">
          <CardContent className="p-8 text-center">
            <Crown className="w-12 h-12 text-primary mx-auto mb-4" />
            <h3 className="font-heading text-2xl font-bold mb-2">Lifetime Access</h3>
            <p className="text-muted-foreground mb-6">
              One-time payment for forever access. Contact us for custom pricing.
            </p>
            <Button onClick={handleContactUs} variant="outline" className="gap-2" data-testid="contact-us-btn">
              <MessageCircle className="w-4 h-4" />
              Contact Us
            </Button>
          </CardContent>
        </Card>

        {/* Support Link */}
        <p className="text-center text-sm text-muted-foreground mt-8">
          Having trouble? <button className="text-primary underline" onClick={handleContactUs}>Contact Support</button>
        </p>
      </div>
    </div>
  );
}
