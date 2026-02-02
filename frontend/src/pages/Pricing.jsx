import { useState } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { Check, Crown, Zap, Star, Phone, MessageCircle } from "lucide-react";

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
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showPayment, setShowPayment] = useState(false);
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const handleSelectPlan = (planId) => {
    setSelectedPlan(planId);
    setShowPayment(true);
  };

  const handlePaymentDone = async () => {
    if (!selectedPlan) return;
    setLoading(selectedPlan);
    
    try {
      await axios.post(`${API}/dashboard-subscription/request`, {
        plan_id: selectedPlan
      }, getAuthHeaders());
      
      toast.success("Subscription request submitted! We'll verify and activate soon.");
      setShowPayment(false);
    } catch (error) {
      toast.error("Failed to submit request");
    } finally {
      setLoading(null);
    }
  };

  const handleContactUs = () => {
    window.open("https://t.me/your_admin_username", "_blank");
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

        {!showPayment ? (
          <>
            {/* Pricing Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
              {plans.map((plan) => {
                const Icon = plan.icon;
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
                      >
                        Get Started
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
                <Button onClick={handleContactUs} variant="outline" className="gap-2">
                  <MessageCircle className="w-4 h-4" />
                  Contact Us
                </Button>
              </CardContent>
            </Card>
          </>
        ) : (
          /* Payment Section */
          <Card className="max-w-lg mx-auto">
            <CardHeader>
              <CardTitle className="font-heading text-2xl font-bold text-center">
                Complete Payment
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="p-4 bg-muted/50 rounded-lg">
                <div className="flex justify-between items-center">
                  <span className="font-medium">
                    {plans.find(p => p.id === selectedPlan)?.name} Plan
                  </span>
                  <span className="font-heading text-2xl font-bold">
                    ₹{plans.find(p => p.id === selectedPlan)?.price.toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Payment Instructions:</h4>
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm space-y-2">
                  <p>1️⃣ Pay via UPI to: <strong>your-upi@paytm</strong></p>
                  <p>2️⃣ Or scan QR code (available on request)</p>
                  <p>3️⃣ Click "I've Paid" below</p>
                  <p>4️⃣ We'll verify and activate within 30 mins</p>
                </div>

                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">
                    <strong>Your Email:</strong> {user.email}
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <Button 
                  variant="outline" 
                  onClick={() => setShowPayment(false)}
                  className="flex-1"
                >
                  Back
                </Button>
                <Button 
                  onClick={handlePaymentDone}
                  disabled={loading}
                  className="flex-1 btn-hover"
                >
                  {loading ? "Submitting..." : "I've Paid"}
                </Button>
              </div>

              <p className="text-xs text-center text-muted-foreground">
                Having trouble? <button className="text-primary underline" onClick={handleContactUs}>Contact Support</button>
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
