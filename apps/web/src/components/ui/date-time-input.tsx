import { useEffect, useRef } from "react";
import { Calendar } from "lucide-react";
import { Input } from "@/components/ui/input";

const pad = (n: number) => String(n).padStart(2, "0");

// eslint-disable-next-line react-refresh/only-export-components
export function toDisplayText(d: Date) {
  const h = d.getHours() % 12 || 12;
  const ampm = d.getHours() >= 12 ? "PM" : "AM";
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()} ${pad(h)}:${pad(d.getMinutes())} ${ampm}`;
}

// eslint-disable-next-line react-refresh/only-export-components
export function parseDateTimeText(value: string): string | null {
  const m = value.trim().match(/^(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
  if (!m) return null;
  const [, dd, mm, yyyy, hh, min, ampm] = m;
  let hour = parseInt(hh, 10);
  if (ampm) {
    const isPM = ampm.toUpperCase() === "PM";
    if (isPM && hour < 12) hour += 12;
    if (!isPM && hour === 12) hour = 0;
  }
  const day = parseInt(dd, 10);
  const month = parseInt(mm, 10) - 1;
  const year = parseInt(yyyy, 10);
  const date = new Date(year, month, day, hour, parseInt(min, 10), 0, 0);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month ||
    date.getDate() !== day
  ) {
    return null;
  }
  return date.toISOString();
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatDateTimeMask(value: string): string {
  const pmHint = /PM$/i.test(value.trim());
  const amHint = /AM$/i.test(value.trim());
  const digits = value.replace(/\D/g, "").slice(0, 12);
  if (!digits) return "";
  const dd = digits.slice(0, 2);
  const mm = digits.slice(2, 4);
  const yyyy = digits.slice(4, 8);
  const hh = digits.slice(8, 10);
  const min = digits.slice(10, 12);

  let out = dd;
  if (digits.length > 2) out += `-${mm}`;
  if (digits.length > 4) out += `-${yyyy}`;

  if (digits.length > 8) {
    out += " ";
    if (hh.length < 2) {
      out += hh;
    } else {
      let hour = parseInt(hh, 10);
      if (hour > 23) hour = 23;
      if (pmHint && hour < 12) hour += 12;
      if (amHint && hour >= 12) hour -= 12;
      const ampm = hour >= 12 ? "PM" : "AM";
      let h12 = hour % 12;
      if (h12 === 0) h12 = 12;
      out += pad(h12);
      if (min) {
        let minute = parseInt(min, 10);
        if (minute > 59) minute = 59;
        out += `:${min.length < 2 ? String(minute) : pad(minute)}`;
      }
      out += ` ${ampm}`;
    }
  }
  return out;
}

function streamFromDisplay(value: string): string {
  const iso = parseDateTimeText(value);
  if (iso) {
    const d = new Date(iso);
    return `${pad(d.getDate())}${pad(d.getMonth() + 1)}${d.getFullYear()}${pad(d.getHours())}${pad(d.getMinutes())}`;
  }
  return value.replace(/\D/g, "").slice(0, 12);
}

export function DateTimeInput({
  value,
  onChange,
  placeholder = "DD-MM-YYYY 00:00 AM/PM",
}: {
  value: string;
  onChange: (iso: string) => void;
  placeholder?: string;
}) {
  const pickerRef = useRef<HTMLInputElement>(null);
  const lastRawRef = useRef(value);
  const rawRef = useRef<string>(streamFromDisplay(value));

  useEffect(() => {
    if (value.trim() === "") {
      rawRef.current = "";
    } else if (formatDateTimeMask(rawRef.current) !== value) {
      rawRef.current = streamFromDisplay(value);
    }
    lastRawRef.current = value;
  }, [value]);

  const openPicker = () => {
    const el = pickerRef.current as (HTMLInputElement & { showPicker?: () => void }) | null;
    if (!el) return;
    try {
      if (el.showPicker) {
        el.showPicker();
      } else {
        el.focus();
        el.click();
      }
    } catch {
      el.focus();
    }
  };

  const handleChange = (raw: string) => {
    const prev = lastRawRef.current;
    lastRawRef.current = raw;
    if (raw.trim() === "") {
      rawRef.current = "";
      onChange("");
    } else if (raw.length < prev.length && prev.startsWith(raw)) {
      rawRef.current = rawRef.current.slice(0, -1);
      onChange(formatDateTimeMask(rawRef.current));
    } else if (raw.length > prev.length && raw.startsWith(prev)) {
      const appended = streamFromDisplay(raw.slice(prev.length));
      rawRef.current = (rawRef.current + appended).slice(0, 12);
      onChange(formatDateTimeMask(rawRef.current));
    } else {
      const display = formatDateTimeMask(raw);
      rawRef.current = streamFromDisplay(display);
      onChange(display);
    }
  };

  return (
    <div className="relative">
      <Input
        type="text"
        inputMode="numeric"
        placeholder={placeholder}
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        className="rounded-xl pr-10"
      />
      <button
        type="button"
        onClick={openPicker}
        aria-label="Open calendar"
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground"
      >
        <Calendar className="h-4 w-4" />
      </button>
      <input
        ref={pickerRef}
        type="datetime-local"
        className="sr-only"
        onChange={(e) => {
          if (e.target.value) {
            const d = new Date(e.target.value);
            rawRef.current = `${pad(d.getDate())}${pad(d.getMonth() + 1)}${d.getFullYear()}${pad(d.getHours())}${pad(d.getMinutes())}`;
            onChange(toDisplayText(d));
          }
        }}
      />
    </div>
  );
}
