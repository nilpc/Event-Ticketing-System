import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, Key, Film, MapPin, Calendar, Users, Pencil, Check, X } from "lucide-react";
import { toast } from "sonner";
import { PageTransition } from "@/components/layout/page-transition";
import { adminApi, catalogApi } from "@/lib/api-routes";
import { useAuth } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DateTimeInput } from "@/components/ui/date-time-input";
import { parseDateTimeText } from "@/components/ui/date-time-mask";
import type { EventType, AdminEventResponse, VenueResponse, ShowtimeResponse } from "@/types/api";

type Tab = "catalog" | "newshow" | "users";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("catalog");
  const { isMasterAdmin } = useAuth();

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "catalog", label: "Catalog", icon: <Film className="h-4 w-4" /> },
    { key: "newshow", label: "New Show", icon: <Plus className="h-4 w-4" /> },
  ];
  if (isMasterAdmin) {
    tabs.push({ key: "users", label: "Users", icon: <Users className="h-4 w-4" /> });
  }

  return (
    <PageTransition>
      <div className="min-h-screen px-4 py-16 md:py-24">
        <div className="max-w-3xl mx-auto space-y-8">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
              <Key className="h-4 w-4 text-primary" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">Merchant Dashboard</h1>
          </div>

          <div className="flex gap-1 p-1 rounded-xl bg-muted/30">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 flex-1 justify-center py-2.5 rounded-lg text-sm font-medium transition-all ${
                  tab === t.key
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>

          {tab === "catalog" && <CatalogTab />}
          {tab === "newshow" && <NewShowTab />}
          {tab === "users" && <UsersTab />}
        </div>
      </div>
    </PageTransition>
  );
}

// ── Catalog Tab ────────────────────────────────────────────────────────────

function CatalogTab() {
  const queryClient = useQueryClient();
  const { userId, isMasterAdmin } = useAuth();

  const canManageEvent = (e: AdminEventResponse) =>
    isMasterAdmin || (e.created_by != null && e.created_by === userId);

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ["adminEvents"],
    queryFn: () => adminApi.getAllEvents().then((r) => r.data),
  });

  const { data: venues, isLoading: venuesLoading } = useQuery({
    queryKey: ["adminVenues"],
    queryFn: () => catalogApi.getVenues().then((r) => r.data),
  });

  const { data: showtimes, isLoading: showtimesLoading } = useQuery({
    queryKey: ["adminShowtimes"],
    queryFn: () => adminApi.getAllShowtimes().then((r) => r.data),
  });

  const deleteEvent = useMutation({
    mutationFn: (id: string) => adminApi.deleteEvent(id),
    onSuccess: () => { toast.success("Event deleted."); queryClient.invalidateQueries({ queryKey: ["adminEvents"] }); },
    onError: (err: { response?: { data?: { detail?: string } } }) => { toast.error(err.response?.data?.detail ?? "Failed to delete event."); },
  });
  const deleteVenue = useMutation({
    mutationFn: (id: string) => adminApi.deleteVenue(id),
    onSuccess: () => { toast.success("Venue deleted."); queryClient.invalidateQueries({ queryKey: ["adminVenues"] }); },
    onError: () => { toast.error("Failed to delete venue."); },
  });
  const deleteShowtime = useMutation({
    mutationFn: (id: string) => adminApi.deleteShowtime(id),
    onSuccess: () => { toast.success("Showtime deleted."); queryClient.invalidateQueries({ queryKey: ["adminShowtimes"] }); },
    onError: () => { toast.error("Failed to delete showtime."); },
  });

  const updateEvent = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string; event_type?: EventType } }) =>
      adminApi.updateEvent(id, data),
    onSuccess: () => { toast.success("Event updated."); queryClient.invalidateQueries({ queryKey: ["adminEvents"] }); },
    onError: (err: { response?: { data?: { detail?: string } } }) => { toast.error(err.response?.data?.detail ?? "Failed to update event."); },
  });
  const updateVenue = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; capacity?: number } }) =>
      adminApi.updateVenue(id, data),
    onSuccess: () => { toast.success("Venue updated."); queryClient.invalidateQueries({ queryKey: ["adminVenues"] }); },
    onError: () => { toast.error("Failed to update venue."); },
  });
  const updateShowtime = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { base_price?: number; start_time?: string; end_time?: string } }) =>
      adminApi.updateShowtime(id, data),
    onSuccess: () => { toast.success("Showtime updated."); queryClient.invalidateQueries({ queryKey: ["adminShowtimes"] }); },
    onError: () => { toast.error("Failed to update showtime."); },
  });

  const eventMap = (events ?? []).reduce<Record<string, AdminEventResponse>>((m, e) => { m[e.event_id] = e; return m; }, {});
  const venueMap = (venues ?? []).reduce<Record<string, VenueResponse>>((m, v) => { m[v.venue_id] = v; return m; }, {});

  return (
    <div className="space-y-8">
      <Section title="Events & Movies" icon={<Film className="h-4 w-4" />} loading={eventsLoading} empty="No events yet."
        count={events?.length}>
        {events?.map((e) => (
          <EditableEventRow
            key={e.event_id}
            event={e}
            canManage={canManageEvent(e)}
            onUpdate={(data) => updateEvent.mutate({ id: e.event_id, data })}
            onDelete={() => deleteEvent.mutate(e.event_id)}
            isPending={updateEvent.isPending || deleteEvent.isPending}
          />
        ))}
      </Section>

      <Section title="Venues" icon={<MapPin className="h-4 w-4" />} loading={venuesLoading} empty="No venues yet."
        count={venues?.length}>
        {venues?.map((v) => (
          <EditableVenueRow
            key={v.venue_id}
            venue={v}
            isMasterAdmin={isMasterAdmin}
            onUpdate={(data) => updateVenue.mutate({ id: v.venue_id, data })}
            onDelete={() => deleteVenue.mutate(v.venue_id)}
            isPending={updateVenue.isPending || deleteVenue.isPending}
          />
        ))}
      </Section>

      <Section title="Showtimes" icon={<Calendar className="h-4 w-4" />} loading={showtimesLoading} empty="No showtimes yet."
        count={showtimes?.length}>
        {showtimes?.map((s) => {
          const ev = eventMap[s.event_id];
          const vn = venueMap[s.venue_id];
          const canManage =
            isMasterAdmin ||
            (ev != null && ev.created_by != null && ev.created_by === userId);
          return (
            <EditableShowtimeRow
              key={s.show_id}
              showtime={s}
              eventLabel={ev?.name ?? s.event_id}
              venueLabel={vn?.name ?? s.venue_id}
              canManage={canManage}
              onUpdate={(data) => updateShowtime.mutate({ id: s.show_id, data })}
              onDelete={() => deleteShowtime.mutate(s.show_id)}
              isPending={updateShowtime.isPending || deleteShowtime.isPending}
            />
          );
        })}
      </Section>
    </div>
  );
}

function Section({ title, icon, loading, empty, count, children }: {
  title: string; icon: React.ReactNode; loading: boolean; empty: string;
  count?: number; children: React.ReactNode;
}) {
  return (
    <div className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">{icon}</span>
          <h2 className="text-sm font-medium text-muted-foreground">{title}</h2>
        </div>
        {count !== undefined && <span className="text-xs text-muted-foreground">{count}</span>}
      </div>
      {loading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      ) : (
        <div className="space-y-2">{children ?? <p className="text-sm text-muted-foreground">{empty}</p>}</div>
      )}
    </div>
  );
}

// ── Editable Event Row ─────────────────────────────────────────────────────

function EditableEventRow({ event, canManage, onUpdate, onDelete, isPending }: {
  event: AdminEventResponse;
  canManage: boolean;
  onUpdate: (data: { name?: string; description?: string; event_type?: EventType }) => void;
  onDelete: () => void;
  isPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(event.name);
  const [desc, setDesc] = useState(event.description ?? "");
  const [eventType, setEventType] = useState<EventType>(event.event_type);

  const save = () => { onUpdate({ name, description: desc || undefined, event_type: eventType }); setEditing(false); };
  const cancel = () => { setName(event.name); setDesc(event.description ?? ""); setEventType(event.event_type); setEditing(false); };

  if (editing) {
    return (
      <div className="p-3 rounded-xl bg-muted/20 space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8 text-sm rounded-lg" placeholder="Name" />
          <select value={eventType} onChange={(e) => setEventType(e.target.value as EventType)}
            className="h-8 rounded-lg border border-white/[0.06] bg-background px-2 text-sm">
            <option value="MOVIE">Movie</option>
            <option value="EVENT">Event</option>
          </select>
        </div>
        <Input value={desc} onChange={(e) => setDesc(e.target.value)} className="h-8 text-sm rounded-lg" placeholder="Description" />
        <div className="flex gap-1 justify-end">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={cancel} disabled={isPending}><X className="h-3.5 w-3.5" /></Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-green-400" onClick={save} disabled={isPending || !name.trim()}>
            {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-3 rounded-xl bg-muted/20">
      <div>
        <p className="text-sm font-medium">{event.name}</p>
        <p className="text-xs text-muted-foreground">{event.event_id} · {event.event_type}</p>
      </div>
      {canManage && (
        <div className="flex gap-0.5">
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => setEditing(true)} disabled={isPending}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-400"
            onClick={onDelete} disabled={isPending}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Editable Venue Row ─────────────────────────────────────────────────────

function EditableVenueRow({ venue, isMasterAdmin, onUpdate, onDelete, isPending }: {
  venue: VenueResponse;
  isMasterAdmin: boolean;
  onUpdate: (data: { name?: string; capacity?: number }) => void;
  onDelete: () => void;
  isPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(venue.name);
  const [capacity, setCapacity] = useState(String(venue.capacity));

  const save = () => { onUpdate({ name, capacity: parseInt(capacity, 10) }); setEditing(false); };
  const cancel = () => { setName(venue.name); setCapacity(String(venue.capacity)); setEditing(false); };

  if (editing) {
    return (
      <div className="p-3 rounded-xl bg-muted/20 space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8 text-sm rounded-lg" placeholder="Name" />
          <Input type="number" value={capacity} onChange={(e) => setCapacity(e.target.value)} className="h-8 text-sm rounded-lg" placeholder="Capacity" />
        </div>
        <div className="flex gap-1 justify-end">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={cancel} disabled={isPending}><X className="h-3.5 w-3.5" /></Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-green-400" onClick={save} disabled={isPending || !name.trim() || parseInt(capacity, 10) < 1}>
            {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-3 rounded-xl bg-muted/20">
      <div>
        <p className="text-sm font-medium">{venue.name}</p>
        <p className="text-xs text-muted-foreground">{venue.venue_id} · {venue.capacity} seats</p>
      </div>
      {isMasterAdmin && (
        <div className="flex gap-0.5">
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => setEditing(true)} disabled={isPending}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-400"
            onClick={onDelete} disabled={isPending}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Editable Showtime Row ──────────────────────────────────────────────────

function EditableShowtimeRow({ showtime, eventLabel, venueLabel, canManage, onUpdate, onDelete, isPending }: {
  showtime: ShowtimeResponse;
  eventLabel: string;
  venueLabel: string;
  canManage: boolean;
  onUpdate: (data: { base_price?: number; start_time?: string; end_time?: string }) => void;
  onDelete: () => void;
  isPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState(showtime.base_price);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const save = () => {
    const data: { base_price?: number; start_time?: string; end_time?: string } = {};
    if (price !== showtime.base_price) data.base_price = parseFloat(price);
    const parsedStart = parseDateTimeText(start);
    const parsedEnd = parseDateTimeText(end);
    if (parsedStart) data.start_time = parsedStart;
    if (parsedEnd) data.end_time = parsedEnd;
    if (Object.keys(data).length > 0) onUpdate(data);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="p-3 rounded-xl bg-muted/20 space-y-2">
        <p className="text-xs text-muted-foreground">{eventLabel} @ {venueLabel}</p>
        <div className="grid grid-cols-3 gap-2">
          <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className="h-8 text-sm rounded-lg" placeholder="Price" />
          <DateTimeInput value={start} onChange={setStart} />
          <DateTimeInput value={end} onChange={setEnd} />
        </div>
        <p className="text-xs text-muted-foreground">Leave start/end blank to keep current values.</p>
        <div className="flex gap-1 justify-end">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditing(false)} disabled={isPending}><X className="h-3.5 w-3.5" /></Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-green-400" onClick={save} disabled={isPending}>
            {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-3 rounded-xl bg-muted/20">
      <div>
        <p className="text-sm font-medium">{eventLabel} @ {venueLabel}</p>
        <p className="text-xs text-muted-foreground">{showtime.show_id.slice(0, 8)}… · ₹{showtime.base_price} · {new Date(showtime.start_time).toLocaleDateString()}</p>
      </div>
      {canManage && (
        <div className="flex gap-0.5">
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => setEditing(true)} disabled={isPending}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-400"
            onClick={onDelete} disabled={isPending}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// ── New Show Tab ───────────────────────────────────────────────────────────

function NewShowTab() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { userId, isMasterAdmin } = useAuth();

  const [eventMode, setEventMode] = useState<"select" | "new">("select");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [newEventName, setNewEventName] = useState("");
  const [newEventType, setNewEventType] = useState<EventType>("MOVIE");
  const [newEventDesc, setNewEventDesc] = useState("");

  const [venueMode, setVenueMode] = useState<"select" | "new">("select");
  const [selectedVenueId, setSelectedVenueId] = useState("");
  const [newVenueName, setNewVenueName] = useState("");
  const [newVenueCapacity, setNewVenueCapacity] = useState("");

  const [price, setPrice] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  const { data: events } = useQuery({
    queryKey: ["adminEvents"],
    queryFn: () => adminApi.getAllEvents().then((r) => r.data),
  });

  const manageableEvents = (events ?? []).filter(
    (e) => isMasterAdmin || (e.created_by != null && e.created_by === userId),
  );

  const { data: venues } = useQuery({
    queryKey: ["adminVenues"],
    queryFn: () => catalogApi.getVenues().then((r) => r.data),
  });

  const submit = useMutation({
    mutationFn: async () => {
      let eventId = selectedEventId;
      let venueId = selectedVenueId;

      if (eventMode === "new") {
        const res = await adminApi.createEvent({
          event_type: newEventType,
          name: newEventName,
          description: newEventDesc || undefined,
        });
        eventId = res.data.event_id;
      }

      if (venueMode === "new") {
        const res = await adminApi.createVenue({
          name: newVenueName,
          capacity: parseInt(newVenueCapacity, 10),
        });
        venueId = res.data.venue_id;
      }

      await adminApi.createShowtime({
        event_id: eventId,
        venue_id: venueId,
        base_price: parseFloat(price),
        start_time: parseDateTimeText(startTime) ?? "",
        end_time: parseDateTimeText(endTime) ?? "",
      });
    },
    onSuccess: () => {
      toast.success("Show created with auto-generated seats.");
      setEventMode("select"); setSelectedEventId("");
      setNewEventName(""); setNewEventDesc("");
      setVenueMode("select"); setSelectedVenueId("");
      setNewVenueName(""); setNewVenueCapacity("");
      setPrice(""); setStartTime(""); setEndTime("");
      queryClient.invalidateQueries({ queryKey: ["adminEvents"] });
      queryClient.invalidateQueries({ queryKey: ["adminVenues"] });
      queryClient.invalidateQueries({ queryKey: ["adminShowtimes"] });
      navigate("/");
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail ?? "Failed to create show.");
    },
  });

  const validStart = !!startTime && parseDateTimeText(startTime) !== null;
  const validEnd = !!endTime && parseDateTimeText(endTime) !== null;

  const canSubmit =
    (eventMode === "select" ? !!selectedEventId : !!newEventName.trim()) &&
    (venueMode === "select" ? !!selectedVenueId : !!newVenueName.trim() && !!newVenueCapacity && parseInt(newVenueCapacity, 10) >= 1) &&
    !!price && validStart && validEnd;

  return (
    <div className="space-y-6">
      {/* Event */}
      <Card>
        <SectionLabel icon={<Film className="h-3.5 w-3.5" />} text="Event / Movie" />
        <RadioGroup value={eventMode} onChange={setEventMode} />
        {eventMode === "select" ? (
          <div className="space-y-2">
            <Label className="text-muted-foreground text-xs font-medium">Select Event</Label>
            <select value={selectedEventId} onChange={(e) => setSelectedEventId(e.target.value)}
              className="flex h-10 w-full rounded-xl border border-white/[0.06] bg-background px-3 py-2 text-sm">
              <option value="">Choose an event…</option>
              {manageableEvents.map((e) => <option key={e.event_id} value={e.event_id}>{e.name} ({e.event_id})</option>)}
            </select>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Name">
                <Input placeholder="Event name" value={newEventName} onChange={(e) => setNewEventName(e.target.value)} className="rounded-xl" />
              </Field>
              <Field label="Type">
                <select value={newEventType} onChange={(e) => setNewEventType(e.target.value as EventType)}
                  className="flex h-10 w-full rounded-xl border border-white/[0.06] bg-background px-3 py-2 text-sm">
                  <option value="MOVIE">Movie</option>
                  <option value="EVENT">Event</option>
                </select>
              </Field>
            </div>
            <Field label="Description">
              <Input placeholder="Optional" value={newEventDesc} onChange={(e) => setNewEventDesc(e.target.value)} className="rounded-xl" />
            </Field>
          </div>
        )}
      </Card>

      {/* Venue */}
      <Card>
        <SectionLabel icon={<MapPin className="h-3.5 w-3.5" />} text="Venue" />
        <RadioGroup value={venueMode} onChange={setVenueMode} />
        {venueMode === "select" ? (
          <div className="space-y-2">
            <Label className="text-muted-foreground text-xs font-medium">Select Venue</Label>
            <select value={selectedVenueId} onChange={(e) => setSelectedVenueId(e.target.value)}
              className="flex h-10 w-full rounded-xl border border-white/[0.06] bg-background px-3 py-2 text-sm">
              <option value="">Choose a venue…</option>
              {venues?.map((v) => <option key={v.venue_id} value={v.venue_id}>{v.name} ({v.capacity} seats)</option>)}
            </select>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Name">
              <Input placeholder="Venue name" value={newVenueName} onChange={(e) => setNewVenueName(e.target.value)} className="rounded-xl" />
            </Field>
            <Field label="Capacity">
              <Input type="number" placeholder="e.g. 100" value={newVenueCapacity} onChange={(e) => setNewVenueCapacity(e.target.value)} className="rounded-xl" />
            </Field>
          </div>
        )}
      </Card>

      {/* Showtime */}
      <Card>
        <SectionLabel icon={<Calendar className="h-3.5 w-3.5" />} text="Showtime" />
        <div className="grid grid-cols-3 gap-4">
          <Field label="Base Price (₹)">
            <Input type="number" placeholder="e.g. 75.00" value={price} onChange={(e) => setPrice(e.target.value)} className="rounded-xl" />
          </Field>
          <Field label="Start Time">
            <DateTimeInput value={startTime} onChange={setStartTime} />
          </Field>
          <Field label="End Time">
            <DateTimeInput value={endTime} onChange={setEndTime} />
          </Field>
        </div>
        <p className="text-xs text-muted-foreground">
          Seats are auto-generated based on venue capacity: VIP (10%), Premium (30%), Standard (60%).
        </p>
      </Card>

      <Button onClick={() => submit.mutate()} disabled={!canSubmit || submit.isPending} className="w-full rounded-full" size="lg">
        {submit.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
        Create Show
      </Button>
    </div>
  );
}

// ── Users Tab ─────────────────────────────────────────────────────────────

function UsersTab() {
  const [userId, setUserId] = useState("");
  const [result, setResult] = useState<{ email: string } | null>(null);

  const promoteUser = useMutation({
    mutationFn: (uid: string) => adminApi.promoteUser(uid).then(r => r.data),
    onSuccess: (data) => {
      toast.success(`${data.email} promoted to merchant.`);
      setResult({ email: data.email });
      setUserId("");
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail ?? "Failed to promote user.");
    },
  });

  return (
    <div className="space-y-4">
      <div className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-medium text-muted-foreground">Promote User to Merchant</h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Enter a user&apos;s UUID to grant them merchant privileges.
        </p>
        <div className="flex gap-3">
          <Input
            placeholder="User ID (UUID)"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="rounded-xl flex-1 font-mono text-xs"
          />
          <Button
            onClick={() => promoteUser.mutate(userId.trim())}
            disabled={!userId.trim() || promoteUser.isPending}
            className="rounded-full"
          >
            {promoteUser.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Promote"}
          </Button>
        </div>
      </div>
      {result && (
        <div className="p-4 rounded-2xl border border-green-500/20 bg-green-500/5 text-sm text-green-400">
          Promoted {result.email} to merchant.
        </div>
      )}
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl space-y-4">
      {children}
    </div>
  );
}

function SectionLabel({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">{icon}</span>
      <h3 className="text-sm font-medium text-muted-foreground">{text}</h3>
    </div>
  );
}

function RadioGroup({ value, onChange }: { value: "select" | "new"; onChange: (v: "select" | "new") => void }) {
  return (
    <div className="flex gap-4 text-sm">
      <label className="flex items-center gap-1.5 cursor-pointer">
        <input type="radio" checked={value === "select"} onChange={() => onChange("select")} className="accent-primary" />
        Select existing
      </label>
      <label className="flex items-center gap-1.5 cursor-pointer">
        <input type="radio" checked={value === "new"} onChange={() => onChange("new")} className="accent-primary" />
        Create new
      </label>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="text-muted-foreground text-xs font-medium">{label}</Label>
      {children}
    </div>
  );
}
