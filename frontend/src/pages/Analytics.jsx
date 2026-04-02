import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  TrendingUp,
  Users,
  IndianRupee,
  Download,
  RefreshCw,
  Calendar,
  BarChart3,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function Analytics() {
  const [revenueData, setRevenueData] = useState(null);
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [revenueRes, userRes] = await Promise.all([
        axios.get(`${API}/analytics/revenue`, getAuthHeaders()),
        axios.get(`${API}/analytics/users`, getAuthHeaders()),
      ]);
      setRevenueData(revenueRes.data);
      setUserData(userRes.data);
    } catch (error) {
      toast.error("Failed to fetch analytics");
    } finally {
      setLoading(false);
    }
  };

  const exportData = async (type) => {
    setExporting(type);
    try {
      const response = await axios.get(`${API}/export/${type}`, getAuthHeaders());
      const { csv_data, count } = response.data;
      
      // Create blob and download
      const blob = new Blob([csv_data], { type: "text/csv" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${type}_export_${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success(`Exported ${count} ${type}`);
    } catch (error) {
      toast.error(`Failed to export ${type}`);
    } finally {
      setExporting(null);
    }
  };

  // Simple bar chart renderer
  const renderBarChart = (data, valueKey, maxValue) => {
    if (!data || data.length === 0) return null;
    const max = maxValue || Math.max(...data.map(d => d[valueKey])) || 1;
    
    return (
      <div className="flex items-end gap-1 h-32">
        {data.slice(-14).map((item, i) => {
          const height = (item[valueKey] / max) * 100;
          return (
            <div key={i} className="flex-1 flex flex-col items-center group relative">
              <div
                className="w-full bg-primary/80 hover:bg-primary rounded-t transition-all"
                style={{ height: `${Math.max(height, 2)}%` }}
              />
              <div className="absolute bottom-full mb-2 hidden group-hover:block bg-popover text-popover-foreground text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap z-10">
                {item.date?.slice(5)}: {valueKey === 'revenue' ? `₹${item[valueKey]}` : item[valueKey]}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-8" data-testid="analytics-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Analytics & Reports</h1>
          <p className="text-muted-foreground mt-1">
            Track your revenue and user growth
          </p>
        </div>
        <Button variant="outline" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg">
              <IndianRupee className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">₹{revenueData?.total_revenue || 0}</p>
              <p className="text-sm text-muted-foreground">Total Revenue</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-lg">
              <TrendingUp className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{revenueData?.total_payments || 0}</p>
              <p className="text-sm text-muted-foreground">Verified Payments</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-purple-100 rounded-lg">
              <Users className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{userData?.total_users || 0}</p>
              <p className="text-sm text-muted-foreground">Total Users</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-orange-100 rounded-lg">
              <Calendar className="w-6 h-6 text-orange-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">30</p>
              <p className="text-sm text-muted-foreground">Days Tracked</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Revenue (Last 14 Days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-32 flex items-center justify-center text-muted-foreground">
                Loading...
              </div>
            ) : (
              <>
                {renderBarChart(revenueData?.chart_data, 'revenue')}
                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                  <span>{revenueData?.chart_data?.[revenueData.chart_data.length - 14]?.date?.slice(5)}</span>
                  <span>Today</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* User Growth Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              New Users (Last 14 Days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-32 flex items-center justify-center text-muted-foreground">
                Loading...
              </div>
            ) : (
              <>
                {renderBarChart(userData?.chart_data, 'new_users')}
                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                  <span>{userData?.chart_data?.[userData.chart_data.length - 14]?.date?.slice(5)}</span>
                  <span>Today</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Export Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="w-5 h-5" />
            Export Data
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border rounded-lg">
              <h3 className="font-medium mb-2">Subscribers Export</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Download all subscriber data including plan details, start/end dates, and status.
              </p>
              <Button 
                onClick={() => exportData('subscribers')} 
                disabled={exporting === 'subscribers'}
                data-testid="export-subscribers-btn"
              >
                <Download className="w-4 h-4 mr-2" />
                {exporting === 'subscribers' ? 'Exporting...' : 'Export Subscribers CSV'}
              </Button>
            </div>
            
            <div className="p-4 border rounded-lg">
              <h3 className="font-medium mb-2">Payments Export</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Download all payment records including amounts, status, and verification details.
              </p>
              <Button 
                onClick={() => exportData('payments')} 
                disabled={exporting === 'payments'}
                data-testid="export-payments-btn"
              >
                <Download className="w-4 h-4 mr-2" />
                {exporting === 'payments' ? 'Exporting...' : 'Export Payments CSV'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
