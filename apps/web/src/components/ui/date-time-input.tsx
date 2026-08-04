import { useRef } from "react";
import { Calendar } from "lucide-react";
import { Input } from "@/components/ui/input";

const pad = (n: number) => String(n).padStart(2, "0");

type AmPm = "AM" | "PM";

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

type FieldName = "day" | "month" | "year" | "hour" | "minute";

const FIELD_ORDER: FieldName[] = ["day", "month", "year", "hour", "minute"];
const FIELD_WIDTH: Record<FieldName, number> = { day: 2, month: 2, year: 4, hour: 2, minute: 2 };
const SEP_AFTER: Record<FieldName, string> = { day: "-", month: "-", year: " ", hour: ":", minute: " " };

const isDigit = (c: string) => c >= "0" && c <= "9";

interface ParseResult {
  fields: Record<FieldName, string>;
  suffix: AmPm | null;
  trailingAfter: FieldName | null;
}

function parseMask(raw: string): ParseResult {
  const fields: Record<FieldName, string> = { day: "", month: "", year: "", hour: "", minute: "" };

  const letter = raw.match(/[ap]/i);
  const suffix: AmPm | null = letter
    ? letter[0].toLowerCase() === "p"
      ? "PM"
      : "AM"
    : null;

  const sufMatch = raw.match(/(\s*)(AM|PM)/i);
  const text = sufMatch
    ? raw.slice(0, sufMatch.index ?? 0) + raw.slice((sufMatch.index ?? 0) + sufMatch[0].length)
    : raw;

  let current = 0;
  let trailingAfter: FieldName | null = null;

  for (const c of text) {
    const name = FIELD_ORDER[current];
    if (!name) break;
    if (isDigit(c)) {
      if (name === "hour" && fields.hour.length === 1 && parseInt(fields.hour + c, 10) > 23) {
        current = FIELD_ORDER.indexOf("minute");
        fields.minute += c;
        trailingAfter = null;
        continue;
      }
      if (name === "minute" && fields.minute.length === 1 && parseInt(fields.minute + c, 10) > 59) {
        continue;
      }
      if (fields[name].length < FIELD_WIDTH[name]) {
        fields[name] += c;
        trailingAfter = null;
      } else {
        let next = current + 1;
        while (next < FIELD_ORDER.length && fields[FIELD_ORDER[next]].length >= FIELD_WIDTH[FIELD_ORDER[next]]) {
          next += 1;
        }
        if (next < FIELD_ORDER.length) {
          current = next;
          fields[FIELD_ORDER[current]] += c;
          trailingAfter = null;
        }
      }
    } else if (c === SEP_AFTER[name] && fields[name].length > 0) {
      trailingAfter = name;
      current += 1;
    }
  }

  return { fields, suffix, trailingAfter };
}

function renderMask({ fields, suffix, trailingAfter }: ParseResult): string {
  const { hour, minute } = fields;

  let out = "";
  for (const name of ["day", "month", "year"] as FieldName[]) {
    const v = fields[name];
    if (v) {
      if (out) out += "-";
      out += v;
    }
  }

  if (hour) {
    if (out) out += " ";
    let hour24 = Math.min(parseInt(hour, 10), 23);
    const showSuffix = hour.length >= 2 || minute.length >= 1;
    const ampm = suffix || (hour24 >= 12 ? "PM" : "AM");
    if (showSuffix) {
      if (ampm === "PM" && hour24 < 12) hour24 += 12;
      else if (ampm === "AM" && hour24 >= 12) hour24 -= 12;
      out += pad(hour24 % 12 || 12);
    } else {
      out += hour;
    }
    if (minute) {
      const m = Math.min(parseInt(minute, 10), 59);
      out += `:${minute.length < 2 ? String(m) : pad(m)}`;
    }
    if (showSuffix) out += ` ${ampm}`;
  }

  if (trailingAfter && (trailingAfter === "day" || trailingAfter === "month") && fields[trailingAfter]) {
    out += SEP_AFTER[trailingAfter];
  }

  return out;
}

function getSuffixFromDisplay(value: string): AmPm | null {
  const m = value.trim().match(/(AM|PM)\s*$/i);
  return m ? (m[1].toUpperCase() as AmPm) : null;
}

function getHourFromDisplay(value: string): string {
  const m = value.trim().match(/(\d{1,2})(?::\d{1,2})?\s*(?:AM|PM)?$/i);
  return m ? m[1] : "";
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatDateTimeMask(value: string, lastValue = ""): string {
  const text = value.trim();
  if (!text) return "";
  const parsed = parseMask(text);
  if (!parsed.suffix) {
    const hour = parsed.fields.hour;
    if (hour !== getHourFromDisplay(lastValue)) {
      parsed.suffix = hour ? (parseInt(hour, 10) >= 12 ? "PM" : "AM") : null;
    } else {
      parsed.suffix = getSuffixFromDisplay(lastValue);
    }
  }
  return renderMask(parsed);
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
  const lastValueRef = useRef(value);

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
    if (raw.trim() === "") {
      lastValueRef.current = "";
      onChange("");
      return;
    }
    const formatted = formatDateTimeMask(raw, lastValueRef.current);
    lastValueRef.current = formatted;
    onChange(formatted);
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
            onChange(toDisplayText(new Date(e.target.value)));
          }
        }}
      />
    </div>
  );
}
