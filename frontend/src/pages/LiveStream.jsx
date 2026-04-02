import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import { 
  Radio, 
  Calendar, 
  Clock, 
  User, 
  Link, 
  Check, 
  X, 
  Trash2, 
  RefreshCw,
  Plus,
  MessageSquare,
  IndianRupee,
  Users,
  Play,
  Square,
  Ticket,
  Sparkles
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
});

export default function LiveStream() {
  const [activeTab, setActiveTab] = useState('sessions'); // sessions, tickets, superchats
  const [liveSessions, setLiveSessions] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [superChats, setSuperChats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newSession, setNewSession] = useState({
    title: '',
    description: '',
    scheduled_date: '',
    scheduled_time: '',
    price: '',
    max_viewers: '',
    stream_link: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };
      
      const [sessionsRes, ticketsRes, superChatsRes] = await Promise.all([
        fetch(`${API}/live/sessions`, { headers }),
        fetch(`${API}/live/tickets`, { headers }),
        fetch(`${API}/live/superchats`, { headers })
      ]);
      
      if (sessionsRes.ok) setLiveSessions(await sessionsRes.json());
      if (ticketsRes.ok) setTickets(await ticketsRes.json());
      if (superChatsRes.ok) setSuperChats(await superChatsRes.json());
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const createSession = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API}/live/sessions`, {
        method: 'POST',
        ...getAuthHeaders(),
        headers: {
          ...getAuthHeaders().headers,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...newSession,
          price: parseFloat(newSession.price) || 0,
          max_viewers: parseInt(newSession.max_viewers) || 100,
        })
      });
      
      if (response.ok) {
        toast.success('Live session created!');
        setShowCreateForm(false);
        setNewSession({
          title: '',
          description: '',
          scheduled_date: '',
          scheduled_time: '',
          price: '',
          max_viewers: '',
          stream_link: '',
        });
        fetchData();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to create session');
      }
    } catch (error) {
      toast.error('Error creating session');
    }
  };

  const updateSession = async (sessionId, data) => {
    try {
      const response = await fetch(`${API}/live/sessions/${sessionId}`, {
        method: 'PUT',
        ...getAuthHeaders(),
        headers: {
          ...getAuthHeaders().headers,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });
      
      if (response.ok) {
        toast.success('Session updated');
        fetchData();
      } else {
        toast.error('Failed to update session');
      }
    } catch (error) {
      toast.error('Error updating session');
    }
  };

  const deleteSession = async (sessionId) => {
    if (!window.confirm('Are you sure you want to delete this session?')) return;
    
    try {
      const response = await fetch(`${API}/live/sessions/${sessionId}`, {
        method: 'DELETE',
        ...getAuthHeaders()
      });
      
      if (response.ok) {
        toast.success('Session deleted');
        fetchData();
      }
    } catch (error) {
      toast.error('Error deleting session');
    }
  };

  const approveTicket = async (ticketId) => {
    try {
      const response = await fetch(`${API}/live/tickets/${ticketId}/approve`, {
        method: 'POST',
        ...getAuthHeaders()
      });
      
      if (response.ok) {
        toast.success('Ticket approved! User will receive stream link.');
        fetchData();
      }
    } catch (error) {
      toast.error('Error approving ticket');
    }
  };

  const rejectTicket = async (ticketId) => {
    try {
      const response = await fetch(`${API}/live/tickets/${ticketId}/reject`, {
        method: 'POST',
        ...getAuthHeaders()
      });
      
      if (response.ok) {
        toast.success('Ticket rejected');
        fetchData();
      }
    } catch (error) {
      toast.error('Error rejecting ticket');
    }
  };

  const getStatusBadge = (status) => {
    const colors = {
      scheduled: 'bg-blue-500/20 text-blue-400',
      live: 'bg-red-500/20 text-red-400 animate-pulse',
      ended: 'bg-gray-500/20 text-gray-400',
      pending: 'bg-yellow-500/20 text-yellow-400',
      approved: 'bg-green-500/20 text-green-400',
      rejected: 'bg-red-500/20 text-red-400',
    };
    return (
      <Badge className={colors[status] || 'bg-gray-500/20'}>
        {status === 'live' && <span className="w-2 h-2 bg-red-500 rounded-full mr-1 animate-pulse"></span>}
        {status?.toUpperCase()}
      </Badge>
    );
  };

  const pendingTickets = tickets.filter(t => t.status === 'pending');
  const pendingSuperChats = superChats.filter(s => s.status === 'pending');

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="live-stream-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
            <Radio className="w-7 h-7 text-red-500" />
            Live Streams
          </h1>
          <p className="text-muted-foreground mt-1">Manage live sessions, tickets & super chats</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={fetchData} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus className="w-4 h-4 mr-2" />
            New Live Session
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
                <Radio className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{liveSessions.filter(s => s.status === 'live').length}</p>
                <p className="text-sm text-muted-foreground">Live Now</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-yellow-100 flex items-center justify-center">
                <Ticket className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendingTickets.length}</p>
                <p className="text-sm text-muted-foreground">Pending Tickets</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendingSuperChats.length}</p>
                <p className="text-sm text-muted-foreground">Pending Super Chats</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                <IndianRupee className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  ₹{superChats.filter(s => s.status === 'approved').reduce((sum, s) => sum + s.amount, 0)}
                </p>
                <p className="text-sm text-muted-foreground">Super Chat Earnings</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {[
          { id: 'sessions', label: 'Live Sessions', icon: Radio },
          { id: 'tickets', label: `Tickets ${pendingTickets.length > 0 ? `(${pendingTickets.length})` : ''}`, icon: Ticket },
          { id: 'superchats', label: `Super Chats ${pendingSuperChats.length > 0 ? `(${pendingSuperChats.length})` : ''}`, icon: Sparkles },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
              activeTab === tab.id 
                ? 'border-primary text-primary' 
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Create Session Form */}
      {showCreateForm && (
        <Card className="border border-primary">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="w-5 h-5" />
              Create New Live Session
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={createSession} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Title</Label>
                  <Input
                    value={newSession.title}
                    onChange={(e) => setNewSession({...newSession, title: e.target.value})}
                    placeholder="Live Q&A Session"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Price (₹)</Label>
                  <Input
                    type="number"
                    value={newSession.price}
                    onChange={(e) => setNewSession({...newSession, price: e.target.value})}
                    placeholder="99"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Date</Label>
                  <Input
                    type="date"
                    value={newSession.scheduled_date}
                    onChange={(e) => setNewSession({...newSession, scheduled_date: e.target.value})}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Time</Label>
                  <Input
                    type="time"
                    value={newSession.scheduled_time}
                    onChange={(e) => setNewSession({...newSession, scheduled_time: e.target.value})}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Max Viewers</Label>
                  <Input
                    type="number"
                    value={newSession.max_viewers}
                    onChange={(e) => setNewSession({...newSession, max_viewers: e.target.value})}
                    placeholder="100"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Stream Link (optional - add later)</Label>
                  <Input
                    value={newSession.stream_link}
                    onChange={(e) => setNewSession({...newSession, stream_link: e.target.value})}
                    placeholder="https://youtube.com/live/..."
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <textarea
                  value={newSession.description}
                  onChange={(e) => setNewSession({...newSession, description: e.target.value})}
                  placeholder="What's this live session about?"
                  rows={3}
                  className="w-full px-3 py-2 bg-muted/50 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                  Cancel
                </Button>
                <Button type="submit">Create Session</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Sessions Tab */}
      {activeTab === 'sessions' && (
        <div className="grid gap-4">
          {liveSessions.length === 0 ? (
            <Card className="border">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Radio className="w-16 h-16 text-muted-foreground mb-4" />
                <h3 className="text-xl">No Live Sessions</h3>
                <p className="text-muted-foreground mt-2">Create your first live session</p>
              </CardContent>
            </Card>
          ) : (
            liveSessions.map((session) => (
              <Card key={session.id} className="border">
                <CardContent className="p-4">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-lg">{session.title}</h3>
                        {getStatusBadge(session.status)}
                      </div>
                      
                      <p className="text-sm text-muted-foreground mb-3">{session.description}</p>
                      
                      <div className="flex flex-wrap gap-4 text-sm">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Calendar className="w-4 h-4" />
                          {session.scheduled_date}
                        </div>
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Clock className="w-4 h-4" />
                          {session.scheduled_time}
                        </div>
                        <div className="flex items-center gap-2 text-green-500">
                          <IndianRupee className="w-4 h-4" />
                          {session.price}
                        </div>
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Users className="w-4 h-4" />
                          {session.tickets_sold || 0}/{session.max_viewers} viewers
                        </div>
                      </div>
                      
                      {session.stream_link && (
                        <div className="mt-2 flex items-center gap-2 text-blue-500">
                          <Link className="w-4 h-4" />
                          <a href={session.stream_link} target="_blank" rel="noreferrer" className="hover:underline text-sm">
                            {session.stream_link}
                          </a>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {session.status === 'scheduled' && (
                        <>
                          <Button 
                            onClick={() => updateSession(session.id, { status: 'live' })}
                            className="bg-red-600 hover:bg-red-700"
                          >
                            <Play className="w-4 h-4 mr-1" />
                            Go Live
                          </Button>
                          <Button 
                            variant="outline"
                            onClick={() => {
                              const link = prompt('Enter stream link:', session.stream_link || '');
                              if (link) updateSession(session.id, { stream_link: link });
                            }}
                          >
                            <Link className="w-4 h-4 mr-1" />
                            Add Link
                          </Button>
                        </>
                      )}
                      
                      {session.status === 'live' && (
                        <Button 
                          onClick={() => updateSession(session.id, { status: 'ended' })}
                          variant="outline"
                          className="border-red-500 text-red-500"
                        >
                          <Square className="w-4 h-4 mr-1" />
                          End Live
                        </Button>
                      )}
                      
                      <Button 
                        onClick={() => deleteSession(session.id)}
                        variant="outline"
                        size="icon"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Tickets Tab */}
      {activeTab === 'tickets' && (
        <div className="grid gap-4">
          {tickets.length === 0 ? (
            <Card className="border">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Ticket className="w-16 h-16 text-muted-foreground mb-4" />
                <h3 className="text-xl">No Tickets Yet</h3>
                <p className="text-muted-foreground mt-2">Ticket requests will appear here</p>
              </CardContent>
            </Card>
          ) : (
            tickets.map((ticket) => (
              <Card key={ticket.id} className="border">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <User className="w-5 h-5 text-primary" />
                        <span className="font-medium">@{ticket.telegram_username || ticket.telegram_user_id}</span>
                        {getStatusBadge(ticket.status)}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Session: <span className="text-white">{ticket.session_title}</span>
                      </p>
                      <p className="text-sm text-green-500">Amount: Rs.{ticket.amount}</p>
                      {ticket.screenshot_file_id && (
                        <div className="mt-2">
                          <img
                            src={`${API}/telegram/file/${ticket.screenshot_file_id}`}
                            alt="Payment Screenshot"
                            className="w-48 h-auto max-h-48 rounded-lg border border-border/50 object-contain cursor-pointer hover:opacity-80 transition-opacity"
                            onClick={() => window.open(`${API}/telegram/file/${ticket.screenshot_file_id}`, '_blank')}
                            onError={(e) => {
                              e.target.style.display = 'none';
                              e.target.insertAdjacentHTML('afterend', '<p class="text-xs text-blue-500 mt-1">📷 Payment screenshot attached (click to view)</p>');
                            }}
                            data-testid={`ticket-screenshot-${ticket.id}`}
                          />
                        </div>
                      )}
                    </div>
                    
                    {ticket.status === 'pending' && (
                      <div className="flex gap-2">
                        <Button onClick={() => approveTicket(ticket.id)} size="sm" className="bg-green-600">
                          <Check className="w-4 h-4 mr-1" />
                          Approve
                        </Button>
                        <Button onClick={() => rejectTicket(ticket.id)} size="sm" variant="outline" className="text-red-500">
                          <X className="w-4 h-4 mr-1" />
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Super Chats Tab */}
      {activeTab === 'superchats' && (
        <div className="grid gap-4">
          {superChats.length === 0 ? (
            <Card className="border">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Sparkles className="w-16 h-16 text-muted-foreground mb-4" />
                <h3 className="text-xl">No Super Chats Yet</h3>
                <p className="text-muted-foreground mt-2">Super chat messages will appear here</p>
              </CardContent>
            </Card>
          ) : (
            superChats.map((chat) => (
              <Card key={chat.id} className={`border ${chat.status === 'pending' ? 'border-yellow-500/50' : ''}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                          <Sparkles className="w-4 h-4 text-white" />
                        </div>
                        <span className="font-medium">@{chat.telegram_username || chat.telegram_user_id}</span>
                        <Badge className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white">
                          ₹{chat.amount}
                        </Badge>
                        {getStatusBadge(chat.status)}
                      </div>
                      <div className="bg-muted/50 rounded-lg p-3 mt-2">
                        <p className="text-sm">{chat.message}</p>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        Session: {chat.session_title} • {new Date(chat.created_at).toLocaleString()}
                      </p>
                    </div>
                    
                    {chat.status === 'pending' && (
                      <div className="flex gap-2">
                        <Button 
                          onClick={async () => {
                            await fetch(`${API}/live/superchats/${chat.id}/approve`, {
                              method: 'POST',
                              ...getAuthHeaders()
                            });
                            toast.success('Super chat approved!');
                            fetchData();
                          }} 
                          size="sm" 
                          className="bg-green-600"
                        >
                          <Check className="w-4 h-4" />
                        </Button>
                        <Button 
                          onClick={async () => {
                            await fetch(`${API}/live/superchats/${chat.id}/reject`, {
                              method: 'POST',
                              ...getAuthHeaders()
                            });
                            toast.success('Super chat rejected');
                            fetchData();
                          }} 
                          size="sm" 
                          variant="outline" 
                          className="text-red-500"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
