import { useState, useEffect } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { Clock, AlertTriangle, Crown, Check, MessageCircle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const plans = [
  { id: "1month", name: "1 Month", price: 4999, days: 30 },
  { id: "6month", name: "6 Months", price: 24999, days: 180, popular: true, save: "17%" },
  { id: "12month", name: "12 Months", price: 44999, days: 365, save: "25%" },
];

export default function RenewSubscription() {
  const [loading, setLoading] = useState(null);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showPayment, setShowPayment] = useState(false);
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const subEnd = user.dashboard_subscription_end 
    ? new Date(user.dashboard_subscription_end) 
    : null;
  
  const isExpired = subEnd && new Date() > subEnd;
  const daysLeft = subEnd 
    ? Math.ceil((subEnd - new Date()) / (1000 * 60 * 60 * 24)) 
    : 0;

  const handleSelectPlan = (planId) => {
    setSelectedPlan(planId);
    setShowPayment(true);
  };

  const handlePaymentDone = async () => {
    if (!selectedPlan) return;
    setLoading(selectedPlan);
    
    try {
      await axios.post(`${API}/dashboard-subscription/request`, {
        plan_id: selectedPlan,
        is_renewal: true
      }, getAuthHeaders());
      
      toast.success("Renewal request submitted! We'll verify and activate soon.");
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
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-yellow-100 rounded-full mb-4">
            {isExpired ? (
              <AlertTriangle className="w-8 h-8 text-yellow-600" />
            ) : (
              <Clock className="w-8 h-8 text-yellow-600" />
            )}
          </div>
          
          <h1 className="font-heading text-3xl md:text-4xl font-bold tracking-tight mb-2">
            {isExpired ? "Subscription Expired" : "Subscription Expiring Soon"}
          </h1>
          
          <p className="text-lg text-muted-foreground">
            {isExpired 
              ? "Your SubsBot dashboard access has expired. Renew to continue."
              : `Your subscription expires in ${daysLeft} days. Renew now to avoid interruption.`
            }
          </p>
          
          {user.dashboard_plan && (
            <Badge className="mt-4 bg-muted">
              Current Plan: {user.dashboard_plan}
            </Badge>
          )}
        </div>

        {!showPayment ? (
          <>
            {/* Renewal Plans */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              {plans.map((plan) => (
                <Card 
                  key={plan.id} 
                  className={`relative border-2 cursor-pointer transition-all hover:border-primary/50 ${
                    plan.popular ? "border-primary shadow-lg" : "border-border"
                  }`}
                  onClick={() => handleSelectPlan(plan.id)}
                >
                  {plan.popular && (
                    <Badge className="absolute -top-2 left-1/2 -translate-x-1/2 bg-primary">
                      Best Value
                    </Badge>
                  )}
                  {plan.save && (
                    <Badge className="absolute -top-2 right-2 bg-green-500 text-white">
                      Save {plan.save}
                    </Badge>
                  )}
                  <CardContent className="p-6 text-center">
                    <h3 className="font-heading text-xl font-bold mb-2">{plan.name}</h3>
                    <p className="font-heading text-4xl font-bold mb-4">
                      ₹{plan.price.toLocaleString()}
                    </p>
                    <Button 
                      className={`w-full ${plan.popular ? "btn-hover" : ""}`}
                      variant={plan.popular ? "default" : "outline"}
                    >
                      Renew Now
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Lifetime Option */}
            <Card className="border-dashed border-2 border-primary/30 bg-primary/5">
              <CardContent className="p-6 text-center">
                <Crown className="w-10 h-10 text-primary mx-auto mb-3" />
                <h3 className="font-heading text-xl font-bold mb-2">Lifetime Access</h3>
                <p className="text-muted-foreground mb-4">
                  One-time payment, never renew again!
                </p>
                <Button onClick={handleContactUs} variant="outline" className="gap-2">
                  <MessageCircle className="w-4 h-4" />
                  Contact for Pricing
                </Button>
              </CardContent>
            </Card>
          </>
        ) : (
          /* Payment Section */
          <Card className="max-w-lg mx-auto">
            <CardContent className="p-6 space-y-6">
              <h2 className="font-heading text-2xl font-bold text-center">
                Complete Renewal Payment
              </h2>
              
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

              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm space-y-2">
                <p>1️⃣ Pay via UPI to: <strong>your-upi@paytm</strong></p>
                <p>2️⃣ Click "I've Paid" below</p>
                <p>3️⃣ We'll verify and extend your subscription</p>
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
            </CardContent>
          </Card>
        )}

        {/* What you'll get */}
        <div className="mt-12 text-center">
          <h3 className="font-heading text-lg font-bold mb-4">What's Included</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {["Full Dashboard Access", "Unlimited Subscribers", "Auto Reminders", "Priority Support"].map((feature) => (
              <div key={feature} className="flex items-center gap-2 justify-center">
                <Check className="w-4 h-4 text-green-500" />
                {feature}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
