import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import {
  MessageSquare,
  Plus,
  Clock,
  CheckCircle,
  AlertCircle,
  Send,
  User,
  Mail,
  Calendar,
  MessageCircle,
  RefreshCw,
  Shield,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

const SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com";

export default function SupportPage() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ subject: "", message: "" });
  const [filter, setFilter] = useState("all");
  const [expandedTicket, setExpandedTicket] = useState(null);
  const [newMessage, setNewMessage] = useState("");
  const [adminReply, setAdminReply] = useState({ ticketId: null, message: "", status: "in_progress" });
  const messagesEndRef = useRef(null);

  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isSuperAdmin = user.email === SUPER_ADMIN_EMAIL;
  const isAdmin = user.is_admin || isSuperAdmin;

  useEffect(() => {
    fetchTickets();
  }, []);

  const fetchTickets = async () => {
    setLoading(true);
    try {
      const endpoint = isAdmin ? `${API}/admin/support/tickets` : `${API}/support/tickets`;
      const response = await axios.get(endpoint, getAuthHeaders());
      setTickets(response.data);
    } catch (error) {
      console.error("Failed to fetch tickets:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTicket = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/support/tickets`, form, getAuthHeaders());
      toast.success("Support ticket created!");
      setDialogOpen(false);
      setForm({ subject: "", message: "" });
      fetchTickets();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create ticket");
    }
  };

  const handleSendMessage = async (ticketId) => {
    if (!newMessage.trim()) return;
    try {
      await axios.post(
        `${API}/support/tickets/${ticketId}/message`,
        { message: newMessage },
        getAuthHeaders()
      );
      toast.success("Message sent!");
      setNewMessage("");
      fetchTickets();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send message");
    }
  };

  const handleAdminReply = async (ticketId) => {
    if (!adminReply.message.trim()) return;
    try {
      await axios.post(
        `${API}/admin/support/tickets/${ticketId}/reply`,
        { message: adminReply.message, status: adminReply.status },
        getAuthHeaders()
      );
      toast.success("Reply sent!");
      setAdminReply({ ticketId: null, message: "", status: "in_progress" });
      fetchTickets();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send reply");
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatTime = (dateStr) => {
    if (!dateStr) return "";
    return new Date(dateStr).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusBadge = (status) => {
    const styles = {
      open: "bg-yellow-100 text-yellow-700",
      in_progress: "bg-blue-100 text-blue-700",
      resolved: "bg-green-100 text-green-700",
      closed: "bg-gray-100 text-gray-700",
    };
    const icons = {
      open: <Clock className="w-3 h-3" />,
      in_progress: <AlertCircle className="w-3 h-3" />,
      resolved: <CheckCircle className="w-3 h-3" />,
      closed: <CheckCircle className="w-3 h-3" />,
    };
    return (
      <Badge className={`flex items-center gap-1 ${styles[status] || "bg-gray-100"}`}>
        {icons[status]}
        {status.replace("_", " ")}
      </Badge>
    );
  };

  const filteredTickets = tickets.filter((t) => {
    if (filter === "all") return true;
    return t.status === filter;
  });

  // Stats
  const openTickets = tickets.filter((t) => t.status === "open").length;
  const inProgressTickets = tickets.filter((t) => t.status === "in_progress").length;
  const resolvedTickets = tickets.filter((t) => t.status === "resolved").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight">
            {isAdmin ? "Support Tickets" : "Contact Support"}
          </h1>
          <p className="text-muted-foreground mt-1">
            {isAdmin
              ? "Manage and respond to user support requests"
              : "Get help with your account or subscriptions"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchTickets} className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
          {!isAdmin && (
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button className="btn-hover" data-testid="create-ticket-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  New Ticket
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle className="font-heading text-xl font-bold">
                    Create Support Ticket
                  </DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateTicket} className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label htmlFor="subject">Subject</Label>
                    <Input
                      id="subject"
                      value={form.subject}
                      onChange={(e) => setForm({ ...form, subject: e.target.value })}
                      placeholder="Brief description of your issue"
                      required
                      data-testid="ticket-subject-input"
                      className="bg-muted/50 border-transparent focus:border-primary"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="message">Message</Label>
                    <Textarea
                      id="message"
                      value={form.message}
                      onChange={(e) => setForm({ ...form, message: e.target.value })}
                      placeholder="Describe your issue in detail..."
                      rows={5}
                      required
                      data-testid="ticket-message-input"
                      className="bg-muted/50 border-transparent focus:border-primary resize-none"
                    />
                  </div>
                  <Button type="submit" className="w-full btn-hover" data-testid="ticket-submit-btn">
                    <Send className="w-4 h-4 mr-2" />
                    Submit Ticket
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Stats (Admin only) */}
      {isAdmin && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="border card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Open</p>
                  <p className="font-heading text-3xl font-bold mt-1 text-yellow-600">
                    {openTickets}
                  </p>
                </div>
                <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center">
                  <Clock className="w-6 h-6 text-yellow-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">In Progress</p>
                  <p className="font-heading text-3xl font-bold mt-1 text-blue-600">
                    {inProgressTickets}
                  </p>
                </div>
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <AlertCircle className="w-6 h-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Resolved</p>
                  <p className="font-heading text-3xl font-bold mt-1 text-green-600">
                    {resolvedTickets}
                  </p>
                </div>
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total</p>
                  <p className="font-heading text-3xl font-bold mt-1">{tickets.length}</p>
                </div>
                <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                  <MessageSquare className="w-6 h-6 text-primary" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filter */}
      <Card className="border">
        <CardContent className="p-4">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[180px] bg-muted/50 border-transparent">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Tickets</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Tickets List */}
      <div className="space-y-4">
        {filteredTickets.length > 0 ? (
          filteredTickets.map((ticket) => (
            <Card key={ticket.id} className="border hover:shadow-md transition-shadow">
              <CardContent className="p-0">
                {/* Ticket Header - Clickable */}
                <div 
                  className="p-6 cursor-pointer"
                  onClick={() => setExpandedTicket(expandedTicket === ticket.id ? null : ticket.id)}
                >
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-3 flex-wrap">
                        {getStatusBadge(ticket.status)}
                        <span className="text-sm text-muted-foreground flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(ticket.created_at)}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {ticket.messages?.length || 1} messages
                        </span>
                      </div>

                      <h3 className="font-heading text-lg font-bold">{ticket.subject}</h3>

                      {isAdmin && (
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <User className="w-4 h-4" />
                            {ticket.user_name}
                          </span>
                          <span className="flex items-center gap-1">
                            <Mail className="w-4 h-4" />
                            {ticket.user_email}
                          </span>
                        </div>
                      )}
                    </div>

                    <Button variant="ghost" size="sm">
                      {expandedTicket === ticket.id ? (
                        <ChevronUp className="w-5 h-5" />
                      ) : (
                        <ChevronDown className="w-5 h-5" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Expanded Chat View */}
                {expandedTicket === ticket.id && (
                  <div className="border-t">
                    {/* Messages */}
                    <div className="max-h-96 overflow-y-auto p-4 space-y-4 bg-muted/20">
                      {(ticket.messages || []).map((msg, idx) => (
                        <div
                          key={idx}
                          className={`flex ${msg.sender === "admin" ? "justify-start" : "justify-end"}`}
                        >
                          <div
                            className={`max-w-[80%] rounded-lg p-3 ${
                              msg.sender === "admin"
                                ? "bg-blue-100 text-blue-900"
                                : "bg-primary text-primary-foreground"
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              {msg.sender === "admin" ? (
                                <Shield className="w-3 h-3" />
                              ) : (
                                <User className="w-3 h-3" />
                              )}
                              <span className="text-xs font-medium">
                                {msg.sender === "admin" ? "Admin" : msg.sender_name || "You"}
                              </span>
                              <span className="text-xs opacity-70">
                                {formatTime(msg.timestamp)}
                              </span>
                            </div>
                            <p className="text-sm whitespace-pre-wrap">{msg.message}</p>
                          </div>
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>

                    {/* Reply Input */}
                    {ticket.status !== "resolved" && ticket.status !== "closed" && (
                      <div className="p-4 border-t bg-background">
                        {isAdmin ? (
                          <div className="space-y-3">
                            <Textarea
                              value={adminReply.ticketId === ticket.id ? adminReply.message : ""}
                              onChange={(e) =>
                                setAdminReply({ ...adminReply, ticketId: ticket.id, message: e.target.value })
                              }
                              placeholder="Type your reply..."
                              rows={3}
                              className="bg-muted/50 border-transparent focus:border-primary resize-none"
                            />
                            <div className="flex items-center gap-3">
                              <Select
                                value={adminReply.ticketId === ticket.id ? adminReply.status : "in_progress"}
                                onValueChange={(val) =>
                                  setAdminReply({ ...adminReply, ticketId: ticket.id, status: val })
                                }
                              >
                                <SelectTrigger className="w-[150px]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="in_progress">In Progress</SelectItem>
                                  <SelectItem value="resolved">Resolved</SelectItem>
                                  <SelectItem value="closed">Closed</SelectItem>
                                </SelectContent>
                              </Select>
                              <Button
                                onClick={() => handleAdminReply(ticket.id)}
                                disabled={!adminReply.message.trim() || adminReply.ticketId !== ticket.id}
                                className="flex-1"
                              >
                                <Send className="w-4 h-4 mr-2" />
                                Send Reply
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <Input
                              value={newMessage}
                              onChange={(e) => setNewMessage(e.target.value)}
                              placeholder="Type your message..."
                              className="flex-1 bg-muted/50 border-transparent focus:border-primary"
                              onKeyPress={(e) => e.key === "Enter" && handleSendMessage(ticket.id)}
                            />
                            <Button onClick={() => handleSendMessage(ticket.id)} disabled={!newMessage.trim()}>
                              <Send className="w-4 h-4" />
                            </Button>
                          </div>
                        )}
                      </div>
                    )}

                    {(ticket.status === "resolved" || ticket.status === "closed") && (
                      <div className="p-4 border-t bg-green-50 text-center text-green-700">
                        <CheckCircle className="w-5 h-5 inline-block mr-2" />
                        This ticket has been {ticket.status}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        ) : (
          <Card className="border">
            <CardContent className="p-16 text-center">
              <MessageSquare className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-heading text-xl font-bold mb-2">No Tickets Found</h3>
              <p className="text-muted-foreground">
                {isAdmin
                  ? "No support tickets to review"
                  : "You haven't created any support tickets yet"}
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
