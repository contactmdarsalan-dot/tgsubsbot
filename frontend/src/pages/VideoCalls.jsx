import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { Video, Calendar, Clock, User, Link, Check, X, Trash2, RefreshCw } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function VideoCalls() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [meetingLinks, setMeetingLinks] = useState({});

  const fetchBookings = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API}/video-calls`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setBookings(data);
      }
    } catch (error) {
      console.error('Error fetching bookings:', error);
      toast.error('Failed to fetch bookings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  const updateBooking = async (bookingId, data) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API}/video-calls/${bookingId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });
      
      if (response.ok) {
        toast.success('Booking updated');
        fetchBookings();
      } else {
        toast.error('Failed to update booking');
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Error updating booking');
    }
  };

  const deleteBooking = async (bookingId) => {
    if (!window.confirm('Are you sure you want to delete this booking?')) return;
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API}/video-calls/${bookingId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        toast.success('Booking deleted');
        fetchBookings();
      } else {
        toast.error('Failed to delete booking');
      }
    } catch (error) {
      console.error('Error:', error);
      toast.error('Error deleting booking');
    }
  };

  const confirmBooking = (bookingId) => {
    const link = meetingLinks[bookingId] || '';
    updateBooking(bookingId, { 
      status: 'confirmed',
      meeting_link: link
    });
  };

  const getStatusBadge = (status) => {
    const statusColors = {
      pending: 'bg-yellow-500/20 text-yellow-400',
      pending_payment: 'bg-orange-500/20 text-orange-400',
      confirmed: 'bg-green-500/20 text-green-400',
      completed: 'bg-blue-500/20 text-blue-400',
      cancelled: 'bg-red-500/20 text-red-400'
    };
    return (
      <Badge className={statusColors[status] || 'bg-gray-500/20 text-gray-400'}>
        {status?.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="video-calls-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Video className="w-7 h-7 text-purple-500" />
            Video Call Bookings
          </h1>
          <p className="text-gray-400 mt-1">Manage video call appointments</p>
        </div>
        <Button onClick={fetchBookings} variant="outline" className="border-gray-700">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {bookings.length === 0 ? (
        <Card className="bg-gray-800/50 border-gray-700">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Video className="w-16 h-16 text-gray-600 mb-4" />
            <h3 className="text-xl text-gray-300">No Bookings Yet</h3>
            <p className="text-gray-500 mt-2">Video call bookings will appear here</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {bookings.map((booking) => (
            <Card key={booking.id} className="bg-gray-800/50 border-gray-700" data-testid={`booking-${booking.id}`}>
              <CardContent className="p-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <User className="w-5 h-5 text-purple-400" />
                      <span className="text-white font-medium">
                        @{booking.telegram_username || booking.telegram_user_id}
                      </span>
                      {getStatusBadge(booking.status)}
                    </div>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div className="flex items-center gap-2 text-gray-400">
                        <Calendar className="w-4 h-4" />
                        <span>{booking.scheduled_date}</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-400">
                        <Clock className="w-4 h-4" />
                        <span>{booking.scheduled_time}</span>
                      </div>
                      <div className="text-gray-400">
                        Duration: {booking.duration_minutes} min
                      </div>
                      <div className="text-green-400 font-medium">
                        Rs {booking.price}
                      </div>
                    </div>

                    {booking.status === 'pending_payment' && (
                      <div className="mt-3">
                        <div className="flex items-center gap-2">
                          <Input
                            placeholder="Enter meeting link (Google Meet, Zoom, etc.)"
                            value={meetingLinks[booking.id] || ''}
                            onChange={(e) => setMeetingLinks({...meetingLinks, [booking.id]: e.target.value})}
                            className="bg-gray-900 border-gray-700 flex-1"
                          />
                        </div>
                      </div>
                    )}

                    {booking.meeting_link && (
                      <div className="mt-2 flex items-center gap-2 text-blue-400">
                        <Link className="w-4 h-4" />
                        <a href={booking.meeting_link} target="_blank" rel="noreferrer" className="hover:underline">
                          {booking.meeting_link}
                        </a>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {booking.status === 'pending_payment' && (
                      <Button 
                        onClick={() => confirmBooking(booking.id)}
                        className="bg-green-600 hover:bg-green-700"
                        data-testid={`confirm-${booking.id}`}
                      >
                        <Check className="w-4 h-4 mr-1" />
                        Confirm
                      </Button>
                    )}
                    
                    {booking.status === 'confirmed' && (
                      <Button 
                        onClick={() => updateBooking(booking.id, { status: 'completed' })}
                        className="bg-blue-600 hover:bg-blue-700"
                      >
                        <Check className="w-4 h-4 mr-1" />
                        Complete
                      </Button>
                    )}
                    
                    {booking.status !== 'cancelled' && booking.status !== 'completed' && (
                      <Button 
                        onClick={() => updateBooking(booking.id, { status: 'cancelled' })}
                        variant="outline"
                        className="border-red-700 text-red-400 hover:bg-red-900/30"
                      >
                        <X className="w-4 h-4 mr-1" />
                        Cancel
                      </Button>
                    )}
                    
                    <Button 
                      onClick={() => deleteBooking(booking.id)}
                      variant="outline"
                      className="border-gray-700 text-gray-400 hover:bg-gray-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
