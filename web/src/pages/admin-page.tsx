import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, Key, Film, MapPin, Calendar } from "lucide-react";
import { toast } from "sonner";
import { PageTransition } from "@/components/layout/page-transition";
import { adminApi, catalogApi } from "@/lib/api-routes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { EventType, EventResponse, VenueResponse } from "@/types/api";
import api from "@/lib/api";
import type { ShowtimeResponse } from "@/types/api";

type Tab = "catalog" | "newshow";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("catalog");
  const [adminTokenInput, setAdminTokenInput] = useState(adminApi.getAdminToken() ?? "");
  const [hasToken, setHasToken] = useState(!!adminApi.getAdminToken());
  const [validating, setValidating] = useState(false);

  const saveToken = async () => {
    setValidating(true);
    try {
      await api.get<ShowtimeResponse[]>("/admin/showtimes", {
        headers: { "X-Admin-Token": adminTokenInput },
      });
      adminApi.setAdminToken(adminTokenInput);
      setHasToken(true);
      toast.success("Admin token verified.");
    } catch {
      toast.error("Invalid admin token. Please check and try again.");
    } finally {
      setValidating(false);
    }
  };

  if (!hasToken) {
    return (
      <PageTransition>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="p-8 w-full max-w-md space-y-6 rounded-2xl border border-white/[0.06] bg-card/50 backdrop-blur-xl">
            <div className="flex items-center gap-2.5">
              <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                <Key className="h-4 w-4 text-primary" />
              </div>
              <h1 className="text-xl font-semibold tracking-tight">Admin Access</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              Enter your admin token to manage events, venues, and showtimes.
            </p>
            <div className="space-y-2">
              <Label className="text-muted-foreground text-xs font-medium">Admin Token</Label>
              <Input
                type="password"
                placeholder="X-Admin-Token value"
                value={adminTokenInput}
                onChange={(e) => setAdminTokenInput(e.target.value)}
                className="rounded-xl"
              />
            </div>
            <Button onClick={saveToken} disabled={!adminTokenInput.trim() || validating} className="w-full rounded-full">
              {validating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {validating ? "Verifying…" : "Continue"}
            </Button>
          </div>
        </div>
      </PageTransition>
    );
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "catalog", label: "Catalog", icon: <Film className="h-4 w-4" /> },
    { key: "newshow", label: "New Show", icon: <Plus className="h-4 w-4" /> },
  ];

  return (
    <PageTransition>
      <div className="min-h-screen px-4 py-16 md:py-24">
        <div className="max-w-3xl mx-auto space-y-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/10">
                <Key className="h-4 w-4 text-primary" />
              </div>
              <h1 className="text-xl font-semibold tracking-tight">Admin Dashboard</h1>
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setHasToken(false); }} className="rounded-full text-xs">
              Change Token
            </Button>
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
        </div>
      </div>
    </PageTransition>
  );
}

// ── Catalog Tab ────────────────────────────────────────────────────────────

function CatalogTab() {
  const queryClient = useQueryClient();

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ["adminEvents"],
    queryFn: () => catalogApi.getEvents().then((r) => r.data),
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
  });
  const deleteVenue = useMutation({
    mutationFn: (id: string) => adminApi.deleteVenue(id),
    onSuccess: () => { toast.success("Venue deleted."); queryClient.invalidateQueries({ queryKey: ["adminVenues"] }); },
  });
  const deleteShowtime = useMutation({
    mutationFn: (id: string) => adminApi.deleteShowtime(id),
    onSuccess: () => { toast.success("Showtime deleted."); queryClient.invalidateQueries({ queryKey: ["adminShowtimes"] }); },
  });

  const eventMap = (events ?? []).reduce<Record<string, EventResponse>>((m, e) => { m[e.event_id] = e; return m; }, {});
  const venueMap = (venues ?? []).reduce<Record<string, VenueResponse>>((m, v) => { m[v.venue_id] = v; return m; }, {});

  return (
    <div className="space-y-8">
      <Section title="Events & Movies" icon={<Film className="h-4 w-4" />} loading={eventsLoading} empty="No events yet."
        count={events?.length}>
        {events?.map((e) => (
          <Row key={e.event_id} label={e.name} sub={`${e.event_id} · ${e.event_type}`}
            onDelete={() => deleteEvent.mutate(e.event_id)} deleting={deleteEvent.isPending} />
        ))}
      </Section>

      <Section title="Venues" icon={<MapPin className="h-4 w-4" />} loading={venuesLoading} empty="No venues yet."
        count={venues?.length}>
        {venues?.map((v) => (
          <Row key={v.venue_id} label={v.name} sub={`${v.venue_id} · ${v.capacity} seats`}
            onDelete={() => deleteVenue.mutate(v.venue_id)} deleting={deleteVenue.isPending} />
        ))}
      </Section>

      <Section title="Showtimes" icon={<Calendar className="h-4 w-4" />} loading={showtimesLoading} empty="No showtimes yet."
        count={showtimes?.length}>
        {showtimes?.map((s) => {
          const ev = eventMap[s.event_id];
          const vn = venueMap[s.venue_id];
          return (
            <Row key={s.show_id}
              label={`${ev?.name ?? s.event_id} @ ${vn?.name ?? s.venue_id}`}
              sub={`${s.show_id.slice(0, 8)}… · ₹${s.base_price} · ${new Date(s.start_time).toLocaleDateString()}`}
              onDelete={() => deleteShowtime.mutate(s.show_id)} deleting={deleteShowtime.isPending} />
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

function Row({ label, sub, onDelete, deleting }: {
  label: string; sub: string; onDelete: () => void; deleting: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-3 rounded-xl bg-muted/20">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{sub}</p>
      </div>
      <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-400"
        onClick={onDelete} disabled={deleting}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

// ── New Show Tab ───────────────────────────────────────────────────────────

function NewShowTab() {
  const queryClient = useQueryClient();

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
    queryFn: () => catalogApi.getEvents().then((r) => r.data),
  });

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
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
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
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail ?? "Failed to create show.");
    },
  });

  const canSubmit =
    (eventMode === "select" ? !!selectedEventId : !!newEventName.trim()) &&
    (venueMode === "select" ? !!selectedVenueId : !!newVenueName.trim() && !!newVenueCapacity && parseInt(newVenueCapacity, 10) >= 1) &&
    !!price && !!startTime && !!endTime;

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
              {events?.map((e) => <option key={e.event_id} value={e.event_id}>{e.name} ({e.event_id})</option>)}
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
            <Input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="rounded-xl" />
          </Field>
          <Field label="End Time">
            <Input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="rounded-xl" />
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
