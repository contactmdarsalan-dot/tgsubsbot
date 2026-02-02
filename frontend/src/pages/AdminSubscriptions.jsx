import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { toast } from "sonner";
import { Users, CheckCircle, Clock, Crown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function AdminSubscriptions() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    checkAdmin();
    fetchRequests();
  }, []);

  const checkAdmin = async () => {
    try {
      const response = await axios.get(`${API}/auth/check-admin`, getAuthHeaders());
      setIsAdmin(response.data.is_admin);
    } catch {
      setIsAdmin(false);
    }
  };

  const fetchRequests = async () => {
    try {
      const response = await axios.get(`${API}/dashboard-subscription/requests`, getAuthHeaders());
      setRequests(response.data);
    } catch (error) {
      console.error("Failed to fetch requests:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (requestId) => {
    try {
      await axios.put(`${API}/dashboard-subscription/approve/${requestId}`, {}, getAuthHeaders());
      toast.success("Subscription approved!");
      fetchRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to approve");
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: "bg-yellow-100 text-yellow-700",
      approved: "bg-green-100 text-green-700",
      rejected: "bg-red-100 text-red-700",
    };
    return <Badge className={styles[status] || ""}>{status}</Badge>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <Crown className="w-12 h-12 text-muted-foreground mb-4" />
        <h2 className="font-heading text-xl font-bold">Admin Access Required</h2>
        <p className="text-muted-foreground">Only the first registered user can access this page.</p>
      </div>
    );
  }

  const pendingCount = requests.filter(r => r.status === "pending").length;
  const approvedCount = requests.filter(r => r.status === "approved").length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-heading text-4xl font-bold tracking-tight">
          Dashboard Subscriptions
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage SubsBot dashboard subscription requests
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Requests</p>
                <p className="font-heading text-3xl font-bold mt-1">{requests.length}</p>
              </div>
              <Users className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card className="border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="font-heading text-3xl font-bold mt-1 text-yellow-600">{pendingCount}</p>
              </div>
              <Clock className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Approved</p>
                <p className="font-heading text-3xl font-bold mt-1 text-green-600">{approvedCount}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Requests Table */}
      <Card className="border">
        <CardHeader>
          <CardTitle className="font-heading text-lg font-bold">
            Subscription Requests
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {requests.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/50">
                    <TableHead className="font-heading font-bold">User</TableHead>
                    <TableHead className="font-heading font-bold">Plan</TableHead>
                    <TableHead className="font-heading font-bold">Amount</TableHead>
                    <TableHead className="font-heading font-bold">Status</TableHead>
                    <TableHead className="font-heading font-bold">Date</TableHead>
                    <TableHead className="font-heading font-bold text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests.map((request) => (
                    <TableRow key={request.id} className="hover:bg-muted/30">
                      <TableCell>
                        <div>
                          <p className="font-medium">{request.user_name}</p>
                          <p className="text-xs text-muted-foreground">{request.user_email}</p>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{request.plan_name}</TableCell>
                      <TableCell className="font-mono">₹{request.amount?.toLocaleString()}</TableCell>
                      <TableCell>{getStatusBadge(request.status)}</TableCell>
                      <TableCell className="text-sm">{formatDate(request.created_at)}</TableCell>
                      <TableCell className="text-right">
                        {request.status === "pending" && (
                          <Button
                            size="sm"
                            onClick={() => handleApprove(request.id)}
                            className="btn-hover"
                          >
                            <CheckCircle className="w-4 h-4 mr-1" />
                            Approve
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16">
              <Users className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="font-heading text-xl font-bold mb-2">No Requests Yet</h3>
              <p className="text-muted-foreground">
                Subscription requests will appear here
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
