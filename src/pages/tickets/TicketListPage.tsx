import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Ticket } from '@/types';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { 
  Card, CardContent, CardHeader, CardTitle, CardDescription 
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  Search, 
  Filter, 
  Calendar as CalendarIcon, 
  LayoutGrid,
  MoreVertical,
  Clock,
  User,
  AlertCircle,
  CheckSquare,
  Square,
  UserPlus,
  ArrowRightCircle
} from 'lucide-react';
import { DayPicker } from 'react-day-picker';
import 'react-day-picker/dist/style.css';
import { Skeleton } from '@/components/ui/skeleton';
import apiClient from '@/api/client';
import { format, isSameDay } from 'date-fns';
import { toast } from 'sonner';

const TICKET_STATUSES = ['OPEN', 'IN_PROGRESS', 'PENDING', 'RESOLVED', 'CLOSED', 'CANCELLED'];

const TicketListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<'kanban' | 'calendar'>('kanban');
  const [selectedTickets, setSelectedTickets] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date());

  // Fetch Tickets
  const { data: tickets, isLoading } = useQuery({
    queryKey: ['tickets'],
    queryFn: async () => {
      const response = await apiClient.get('/tickets');
      return response.data;
    },
  });

  // Fetch Users (for assignment)
  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await apiClient.get('/auth/users'); 
      return response.data;
    },
  });

  // Bulk Status Update Mutation
  const bulkUpdateMutation = useMutation({
    mutationFn: async ({ ticketIds, status }: { ticketIds: string[]; status: string }) => {
      return await apiClient.patch('/tickets/bulk-status', { ticket_ids: ticketIds, status });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
      setSelectedTickets([]);
      toast.success('Bulk update successful');
    },
  });

  const onDragEnd = (result: any) => {
    const { destination, source, draggableId } = result;
    if (!destination) return;
    if (destination.droppableId === source.droppableId) return;

    // SRS 4 & 7.2 Enforcement
    const ticket = tickets?.find((t: Ticket) => t.id === draggableId);
    if (!ticket) return;

    if (ticket.is_sla_breached) {
      toast.error('Cannot change status of a ticket that has breached SLA (SRS 7.2)');
      return;
    }

    if (ticket.status === 'RESOLVED' && destination.droppableId === 'OPEN') {
      toast.error('Transition from RESOLVED to OPEN is forbidden (SRS 4)');
      return;
    }

    bulkUpdateMutation.mutate({
      ticketIds: [draggableId],
      status: destination.droppableId,
    });
  };

  const toggleTicketSelection = (id: string) => {
    setSelectedTickets(prev => 
      prev.includes(id) ? prev.filter(tid => tid !== id) : [...prev, id]
    );
  };

  const getTicketsByStatus = (status: string) => {
    return tickets?.filter((t: any) => t.status === status) || [];
  };

  const getTicketsByDate = (date: Date) => {
    return tickets?.filter((t: any) => t.sla_deadline && isSameDay(new Date(t.sla_deadline), date)) || [];
  };

  return (
    <div className="container mx-auto p-6 space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">ITSM Service Desk</h1>
          <p className="text-muted-foreground">Manage support tickets, SLA performance, and incident response.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex border rounded-lg p-1 bg-muted/50">
            <Button 
              variant={viewMode === 'kanban' ? 'secondary' : 'ghost'} 
              size="sm" 
              onClick={() => setViewMode('kanban')}
            >
              <LayoutGrid className="h-4 w-4 mr-2" /> Kanban
            </Button>
            <Button 
              variant={viewMode === 'calendar' ? 'secondary' : 'ghost'} 
              size="sm" 
              onClick={() => setViewMode('calendar')}
            >
              <CalendarIcon className="h-4 w-4 mr-2" /> Calendar
            </Button>
          </div>
          <Button>
            <Plus className="h-4 w-4 mr-2" /> New Ticket
          </Button>
        </div>
      </div>

      {/* Bulk Action Toolbar */}
      {selectedTickets.length > 0 && (
        <div className="bg-primary/10 border border-primary/20 p-4 rounded-xl flex items-center justify-between animate-in slide-in-from-top-4">
          <div className="flex items-center gap-4">
            <Badge variant="default" className="rounded-full px-3">
              {selectedTickets.length} selected
            </Badge>
            <div className="h-4 w-[1px] bg-primary/20" />
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium">Update Status:</span>
              {TICKET_STATUSES.map(status => {
                const hasBreached = tickets?.filter((t: Ticket) => selectedTickets.includes(t.id) && t.is_sla_breached).length > 0;
                
                return (
                  <Button 
                    key={status} 
                    variant="outline" 
                    size="sm" 
                    className="h-7 text-[10px]"
                    disabled={hasBreached}
                    onClick={() => bulkUpdateMutation.mutate({ ticketIds: selectedTickets, status })}
                  >
                    {status}
                  </Button>
                );
              })}
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setSelectedTickets([])}>Cancel</Button>
        </div>
      )}

      {/* Filters & Search */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input 
            className="w-full pl-10 pr-4 py-2 rounded-lg border bg-background focus:ring-2 focus:ring-primary/20 outline-none transition-all"
            placeholder="Search tickets by ID, title, or user..."
          />
        </div>
        <Button variant="outline">
          <Filter className="h-4 w-4 mr-2" /> Filters
        </Button>
      </div>

      {/* Kanban Board */}
      {viewMode === 'kanban' && (
        <DragDropContext onDragEnd={onDragEnd}>
          <div className="flex gap-6 overflow-x-auto pb-6 min-h-[600px]">
            {TICKET_STATUSES.map((status) => (
              <Droppable key={status} droppableId={status}>
                {(provided, snapshot) => (
                  <div
                    {...provided.droppableProps}
                    ref={provided.innerRef}
                    className={`flex-shrink-0 w-80 rounded-xl p-4 transition-colors ${
                      snapshot.isDraggingOver ? 'bg-muted/80' : 'bg-muted/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-sm uppercase tracking-wider">{status.replace('_', ' ')}</h3>
                        <Badge variant="secondary" className="rounded-full px-2 py-0">
                          {isLoading ? '...' : getTicketsByStatus(status).length}
                        </Badge>
                      </div>
                      <Button variant="ghost" size="icon" className="h-6 w-6">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="space-y-4">
                      {isLoading ? (
                        Array.from({ length: 3 }).map((_, i) => (
                          <Card key={i} className="p-4 space-y-3 animate-pulse">
                            <div className="flex items-center justify-between">
                              <Skeleton className="h-3 w-1/4" />
                              <Skeleton className="h-4 w-4 rounded-full" />
                            </div>
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-2/3" />
                            <div className="flex items-center gap-4">
                              <Skeleton className="h-3 w-1/3" />
                              <Skeleton className="h-3 w-1/3" />
                            </div>
                            <div className="flex items-center justify-between pt-2 border-t">
                              <Skeleton className="h-4 w-1/4" />
                              <Skeleton className="h-6 w-6 rounded-full" />
                            </div>
                          </Card>
                        ))
                      ) : getTicketsByStatus(status).map((ticket: Ticket, index: number) => (
                        // @ts-ignore
                        <Draggable key={ticket.id} draggableId={ticket.id} index={index}>
                          {(provided: any, snapshot: any) => (
                            <Card
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              className={`relative shadow-sm hover:shadow-md transition-all border-l-4 ${
                                ticket.priority === 'HIGH' ? 'border-l-red-500' : 
                                ticket.priority === 'MEDIUM' ? 'border-l-orange-500' : 'border-l-blue-500'
                              } ${snapshot.isDragging ? 'rotate-2 scale-105 shadow-xl ring-2 ring-primary/20' : ''}`}
                            >
                              <CardContent className="p-4 space-y-3">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="flex items-center gap-2">
                                    <button 
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toggleTicketSelection(ticket.id);
                                      }}
                                      className="hover:text-primary transition-colors"
                                    >
                                      {selectedTickets.includes(ticket.id) ? (
                                        <CheckSquare className="h-4 w-4 text-primary" />
                                      ) : (
                                        <Square className="h-4 w-4 text-muted-foreground" />
                                      )}
                                    </button>
                                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                                      #{ticket.id.substring(0, 8)}
                                    </span>
                                  </div>
                                  {ticket.is_sla_breached && (
                                    <AlertCircle className="h-4 w-4 text-red-500" />
                                  )}
                                </div>
                                <h4 className="text-sm font-semibold leading-tight line-clamp-2">
                                  {ticket.title}
                                </h4>
                                <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
                                  <div className="flex items-center gap-1">
                                    <User className="h-3 w-3" /> {ticket.reporter_name || 'User'}
                                  </div>
                                  <div className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" /> {format(new Date(ticket.created_at), 'MMM d')}
                                  </div>
                                </div>
                                <div className="flex items-center justify-between pt-2 border-t mt-2">
                                  <Badge variant="outline" className="text-[10px] capitalize">
                                    {ticket.category || 'General'}
                                  </Badge>
                                  <div className="h-6 w-6 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary">
                                    {ticket.assignee_name?.[0] || '?'}
                                  </div>
                                </div>
                              </CardContent>
                            </Card>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                    </div>
                  </div>
                )}
              </Droppable>
            ))}
          </div>
        </DragDropContext>
      )}

      {/* Calendar View */}
      {viewMode === 'calendar' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in slide-in-from-bottom-4">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle>SLA Calendar</CardTitle>
              <CardDescription>View tickets by deadline</CardDescription>
            </CardHeader>
            <CardContent className="flex justify-center">
              <DayPicker
                mode="single"
                selected={selectedDate}
                onSelect={setSelectedDate}
                modifiers={{
                  hasTicket: (date) => getTicketsByDate(date).length > 0
                }}
                modifiersStyles={{
                  hasTicket: { fontWeight: 'bold', color: 'var(--primary)', textDecoration: 'underline' }
                }}
                className="border rounded-lg p-4"
              />
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>
                Tickets due on {selectedDate ? format(selectedDate, 'MMMM d, yyyy') : '...'}
              </CardTitle>
              <CardDescription>
                {getTicketsByDate(selectedDate || new Date()).length} tickets found
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {getTicketsByDate(selectedDate || new Date()).map((ticket: Ticket) => (
                  <div key={ticket.id} className="flex items-center justify-between p-4 border rounded-xl hover:bg-muted/30 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className={`h-2 w-2 rounded-full ${
                        ticket.priority === 'HIGH' ? 'bg-red-500' : 'bg-blue-500'
                      }`} />
                      <div>
                        <p className="text-sm font-bold">{ticket.title}</p>
                        <p className="text-xs text-muted-foreground">#{ticket.id.substring(0, 8)} • {ticket.status}</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm">
                      <ArrowRightCircle className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                {getTicketsByDate(selectedDate || new Date()).length === 0 && (
                  <div className="text-center py-12 text-muted-foreground italic">
                    No tickets due on this day.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default TicketListPage;
