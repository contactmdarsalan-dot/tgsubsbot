import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import axios from "axios";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BotCheckout() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState("loading"); // loading, ready, success, error
  const [orderDetails, setOrderDetails] = useState(null);
  const [razorpayLoaded, setRazorpayLoaded] = useState(false);

  const orderId = searchParams.get("order_id");
  const planId = searchParams.get("plan_id");
  const userId = searchParams.get("user_id");

  // Load Razorpay script
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => setRazorpayLoaded(true);
    document.body.appendChild(script);
    return () => document.body.removeChild(script);
  }, []);

  // Fetch order details
  useEffect(() => {
    const fetchOrder = async () => {
      if (!orderId || !planId) {
        setStatus("error");
        setLoading(false);
        return;
      }

      try {
        const response = await axios.get(`${API}/bot-checkout/${orderId}`);
        setOrderDetails(response.data);
        setStatus("ready");
      } catch (error) {
        console.error("Error fetching order:", error);
        setStatus("error");
      } finally {
        setLoading(false);
      }
    };

    fetchOrder();
  }, [orderId, planId]);

  const handlePayment = async () => {
    if (!razorpayLoaded || !orderDetails) {
      toast.error("Payment gateway not ready");
      return;
    }

    setProcessing(true);

    const options = {
      key: orderDetails.key_id,
      amount: orderDetails.amount * 100,
      currency: "INR",
      name: "TG Subs Bot",
      description: orderDetails.plan_name,
      order_id: orderId,
      handler: async function (response) {
        // Verify payment
        try {
          const verifyResponse = await axios.post(`${API}/bot-checkout/verify`, {
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
            telegram_user_id: userId
          });

          if (verifyResponse.data.success) {
            setStatus("success");
            toast.success("Payment successful! Check Telegram for channel link.");
          } else {
            setStatus("error");
            toast.error("Payment verification failed");
          }
        } catch (error) {
          setStatus("error");
          toast.error("Payment verification failed");
        }
      },
      prefill: {
        name: "",
        email: "",
        contact: ""
      },
      theme: {
        color: "#BFFF00"
      },
      modal: {
        ondismiss: function () {
          setProcessing(false);
        }
      }
    };

    const razorpay = new window.Razorpay(options);
    razorpay.open();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-purple-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-purple-900 flex items-center justify-center p-4">
        <Card className="bg-slate-800/50 border-red-500/30 max-w-md w-full">
          <CardContent className="p-8 text-center">
            <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-white mb-2">Payment Error</h1>
            <p className="text-slate-300">Invalid or expired payment link.</p>
            <p className="text-slate-400 mt-4 text-sm">Please go back to Telegram and try again.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-purple-900 flex items-center justify-center p-4">
        <Card className="bg-slate-800/50 border-green-500/30 max-w-md w-full">
          <CardContent className="p-8 text-center">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-white mb-2">Payment Successful!</h1>
            <p className="text-slate-300">Your subscription has been activated.</p>
            <p className="text-green-400 mt-4">✅ Check Telegram for your channel invite link!</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-purple-900 flex items-center justify-center p-4">
      <Card className="bg-slate-800/50 border-purple-500/30 max-w-md w-full">
        <CardContent className="p-8">
          <h1 className="text-2xl font-bold text-white text-center mb-6">Complete Payment</h1>
          
          {orderDetails && (
            <div className="space-y-4 mb-6">
              <div className="bg-slate-700/50 rounded-lg p-4">
                <p className="text-slate-400 text-sm">Plan</p>
                <p className="text-white font-bold text-lg">{orderDetails.plan_name}</p>
              </div>
              
              <div className="bg-slate-700/50 rounded-lg p-4">
                <p className="text-slate-400 text-sm">Amount</p>
                <p className="text-white font-bold text-2xl">₹{orderDetails.amount}</p>
              </div>
              
              <div className="bg-slate-700/50 rounded-lg p-4">
                <p className="text-slate-400 text-sm">Telegram User ID</p>
                <p className="text-white font-mono">{userId}</p>
              </div>
            </div>
          )}
          
          <Button 
            onClick={handlePayment} 
            disabled={processing || !razorpayLoaded}
            className="w-full bg-purple-600 hover:bg-purple-700 text-white py-6 text-lg"
          >
            {processing ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              "💳 Pay Now"
            )}
          </Button>
          
          <p className="text-slate-400 text-center text-sm mt-4">
            Secure payment via Razorpay
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
