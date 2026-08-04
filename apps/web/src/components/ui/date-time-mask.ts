const pad = (n: number) => String(n).padStart(2, "0");

type AmPm = "AM" | "PM";

export function toDisplayText(d: Date) {
  const h = d.getHours() % 12 || 12;
  const ampm = d.getHours() >= 12 ? "PM" : "AM";
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()} ${pad(h)}:${pad(d.getMinutes())} ${ampm}`;
}

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

export type FieldName = "day" | "month" | "year" | "hour" | "minute" | "ampm";

const NUMERIC_FIELDS = ["day", "month", "year", "hour", "minute"] as const;
const SEGMENT_NAMES = [...NUMERIC_FIELDS, "ampm"] as FieldName[];

const FIELD_WIDTH: Record<FieldName, number> = { day: 2, month: 2, year: 4, hour: 2, minute: 2, ampm: 2 };
const SEP_BEFORE: Record<FieldName, string> = { day: "", month: "-", year: "-", hour: " ", minute: ":", ampm: " " };

export type Fields = Record<FieldName, string>;

export interface EditorState {
  fields: Fields;
  caret: number;
  si: number;
}

const emptyFields = (): Fields => ({ day: "", month: "", year: "", hour: "", minute: "", ampm: "" });

const isDigit = (c: string) => c >= "0" && c <= "9";

function displayHour(hour: string, ampm: string): string {
  if (!ampm) return hour;
  const h = parseInt(hour, 10);
  if (Number.isNaN(h) || h <= 12) return hour;
  return String(h - 12);
}

interface SegmentText {
  name: FieldName;
  text: string;
  sep: string;
}

function segmentTexts(f: Fields): SegmentText[] {
  const out: SegmentText[] = [];
  let hasPrior = false;
  for (const name of SEGMENT_NAMES) {
    let text = f[name];
    if (name === "hour" && f.ampm) text = displayHour(text, f.ampm);
    if (!text) continue;
    out.push({ name, text, sep: hasPrior ? SEP_BEFORE[name] : "" });
    hasPrior = true;
  }
  return out;
}

export function renderFields(f: Fields): string {
  let out = "";
  for (const { text, sep } of segmentTexts(f)) {
    out += sep + text;
  }
  return out;
}

interface Span {
  name: FieldName;
  start: number;
  end: number;
}

function segmentSpans(f: Fields): Span[] {
  const spans: Span[] = [];
  let pos = 0;
  for (const { name, text, sep } of segmentTexts(f)) {
    pos += sep.length;
    spans.push({ name, start: pos, end: pos + text.length });
    pos += text.length;
  }
  return spans;
}

export function fieldsFromDisplay(value: string): Fields {
  const f = emptyFields();
  const s = value.trim();
  if (!s) return f;
  const ampm = s.match(/(AM|PM)\s*$/i);
  let text = s;
  if (ampm && ampm.index != null) {
    f.ampm = ampm[1].toUpperCase() as AmPm;
    text = s.slice(0, ampm.index).trimEnd();
  }
  const runs = text.match(/\d+/g) ?? [];
  const yearFirst = runs.length >= 3 && (runs[0]?.length ?? 0) >= 4;
  const order = yearFirst
    ? (["year", "month", "day", "hour", "minute"] as const)
    : NUMERIC_FIELDS;
  for (let i = 0; i < order.length && i < runs.length; i++) {
    const name = order[i] as FieldName;
    f[name] = runs[i].slice(0, FIELD_WIDTH[name]);
  }
  return f;
}

export function locateSegment(f: Fields, caret: number): number {
  const spans = segmentSpans(f);
  if (!spans.length) return 0;
  let chosen = spans[0];
  for (const s of spans) if (s.start <= caret) chosen = s;
  return SEGMENT_NAMES.indexOf(chosen.name);
}

function segmentSlotStart(f: Fields, si: number): number {
  let pos = 0;
  let hasPrior = false;
  for (let i = 0; i < SEGMENT_NAMES.length; i++) {
    const name = SEGMENT_NAMES[i];
    let text = f[name];
    if (name === "hour" && f.ampm) text = displayHour(text, f.ampm);
    if (i === si) {
      return hasPrior ? pos + SEP_BEFORE[name].length : pos;
    }
    if (text) {
      if (hasPrior) pos += SEP_BEFORE[name].length;
      pos += text.length;
      hasPrior = true;
    }
  }
  return pos;
}

function maybeAutoAmpm(f: Fields) {
  if (f.ampm) return;
  if (f.minute.length >= 1) {
    f.ampm = parseInt(f.hour, 10) >= 12 ? "PM" : "AM";
  }
}

function isDateTimeText(text: string): boolean {
  const t = text.trim().replace(/\s*(AM|PM)\s*$/i, "");
  return /\d/.test(t) && /^[\d\s\-./:,]+$/i.test(t);
}

function overflowToNextNumeric(
  state: EditorState,
  name: FieldName,
  ch: string,
): EditorState | null {
  const idx = NUMERIC_FIELDS.indexOf(name as (typeof NUMERIC_FIELDS)[number]);
  if (idx < 0) return null;
  for (let i = idx + 1; i < NUMERIC_FIELDS.length; i++) {
    const n = NUMERIC_FIELDS[i];
    if (state.fields[n].length < FIELD_WIDTH[n]) {
      const fields = { ...state.fields, [n]: state.fields[n] + ch };
      if (n === "hour" || n === "minute") maybeAutoAmpm(fields);
      const caret = segmentSlotStart(fields, i) + fields[n].length;
      const si = fields[n].length >= FIELD_WIDTH[n] ? i + 1 : i;
      return { fields, caret, si };
    }
  }
  return null;
}

function insertDigit(state: EditorState, ch: string): EditorState | null {
  const name = SEGMENT_NAMES[state.si];
  if (name === "ampm") return null;
  const w = FIELD_WIDTH[name];
  const t = state.fields[name];
  const len = t.length;
  const slot = segmentSlotStart(state.fields, state.si);
  const off = Math.max(0, Math.min(state.caret - slot, len));

  if (name === "hour" && len === 1 && off === len && parseInt(t + ch, 10) > 23) {
    return overflowToNextNumeric(state, "hour", ch);
  }
  if (name === "minute" && len === 1 && off === len && parseInt(t + ch, 10) > 59) {
    return null;
  }

  if (len >= w) {
    if (off < len) {
      const newT = t.slice(0, off) + ch + t.slice(off + 1);
      if (name === "hour" && parseInt(newT, 10) > 23) return null;
      if (name === "minute" && parseInt(newT, 10) > 59) return null;
      const fields = { ...state.fields, [name]: newT };
      const caret = segmentSlotStart(fields, state.si) + newT.length;
      return { fields, caret, si: state.si };
    }
    return overflowToNextNumeric(state, name, ch);
  }

  const newT = t.slice(0, off) + ch + t.slice(off);
  if (name === "hour" && parseInt(newT, 10) > 23) return null;
  if (name === "minute" && parseInt(newT, 10) > 59) return null;
  const fields = { ...state.fields, [name]: newT };
  if (name === "hour" || name === "minute") maybeAutoAmpm(fields);
  const caret = segmentSlotStart(fields, state.si) + newT.length;
  const si = newT.length >= w ? state.si + 1 : state.si;
  return { fields, caret, si };
}

function advanceSegment(state: EditorState): EditorState | null {
  const name = SEGMENT_NAMES[state.si];
  if (state.fields[name] === "") return state;
  if (state.si >= SEGMENT_NAMES.length - 1) return null;
  const si = state.si + 1;
  return { fields: state.fields, caret: segmentSlotStart(state.fields, si), si };
}

function insertAmpm(state: EditorState, ch: string): EditorState | null {
  if (!state.fields.hour && !state.fields.minute) return null;
  const c = ch.toUpperCase();
  if (c === "M") return null;
  if (c !== "A" && c !== "P") return null;
  const fields = { ...state.fields, ampm: c === "P" ? "PM" : "AM" };
  return { fields, caret: renderFields(fields).length, si: SEGMENT_NAMES.indexOf("ampm") };
}

export function applyInsert(state: EditorState, data: string): EditorState | null {
  if (data.length > 1) {
    if (isDateTimeText(data)) {
      const parsed = fieldsFromDisplay(data);
      if (Object.values(parsed).some((v) => v !== "")) {
        const rendered = renderFields(parsed);
        return { fields: parsed, caret: rendered.length, si: locateSegment(parsed, rendered.length) };
      }
    }
    return null;
  }
  const ch = data[0];
  if (isDigit(ch)) return insertDigit(state, ch);
  if ("-/: .".includes(ch)) return advanceSegment(state);
  if ("apmAPM".includes(ch)) return insertAmpm(state, ch);
  return null;
}

export function clearSelection(f0: Fields, start: number, end: number): Fields {
  const f = { ...f0 };
  const from = Math.min(start, end);
  const to = Math.max(start, end);
  for (const span of segmentSpans(f)) {
    if (span.start < to && from < span.end) f[span.name] = "";
  }
  return f;
}

export function applyBackspace(state: EditorState): EditorState | null {
  const caret = state.caret;
  if (caret <= 0) return null;
  const spans = segmentSpans(state.fields);
  const pos = caret - 1;
  let target: Span | undefined;
  for (const s of spans) if (s.start <= pos) target = s;
  if (!target) return null;
  const fields = { ...state.fields };
  const o = pos - target.start;
  if (o >= 0 && o < target.end - target.start) {
    fields[target.name] = fields[target.name].slice(0, o) + fields[target.name].slice(o + 1);
  } else {
    fields[target.name] = fields[target.name].slice(0, -1);
  }
  const newCaret = caret - 1;
  return { fields, caret: newCaret, si: locateSegment(fields, newCaret) };
}

export function applyDelete(state: EditorState): EditorState | null {
  const caret = state.caret;
  const spans = segmentSpans(state.fields);
  const rendered = renderFields(state.fields);
  if (caret >= rendered.length) return null;
  let target: Span | undefined;
  for (const s of spans) if (s.start <= caret) target = s;
  if (!target) return null;
  const fields = { ...state.fields };
  const o = caret - target.start;
  if (o >= 0 && o < target.end - target.start) {
    fields[target.name] = fields[target.name].slice(0, o) + fields[target.name].slice(o + 1);
  } else {
    const next = spans.find((s) => s.start > target!.end);
    if (!next) return null;
    fields[next.name] = fields[next.name].slice(1);
  }
  return { fields, caret, si: locateSegment(fields, caret) };
}

export function formatDateTimeMask(value: string): string {
  return renderFields(fieldsFromDisplay(value));
}
