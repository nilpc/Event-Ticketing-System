import { useLayoutEffect, useRef } from "react";
import type { ClipboardEvent, FormEvent, KeyboardEvent } from "react";
import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import {
  applyBackspace,
  applyDelete,
  applyInsert,
  clearSelection,
  fieldsFromDisplay,
  locateSegment,
  parseDateTimeText,
  renderFields,
  toDisplayText,
  type EditorState,
} from "@/components/ui/date-time-mask";

export function DateTimeInput({
  value,
  onChange,
  placeholder = "DD-MM-YYYY 00:00 AM/PM",
  invalid = false,
}: {
  value: string;
  onChange: (iso: string) => void;
  placeholder?: string;
  invalid?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLInputElement>(null);
  const pendingCaretRef = useRef<number | null>(null);
  const lastCaretRef = useRef<number>(-1);
  const siRef = useRef(0);
  const pasteHandledRef = useRef(false);

  const setCaret = (pos: number) => {
    const el = inputRef.current;
    if (!el) return;
    const clamped = Math.max(0, Math.min(pos, el.value.length));
    el.setSelectionRange(clamped, clamped);
    lastCaretRef.current = clamped;
  };

  useLayoutEffect(() => {
    if (pendingCaretRef.current != null) {
      setCaret(pendingCaretRef.current);
      pendingCaretRef.current = null;
    }
    const picker = pickerRef.current;
    if (!picker) return;
    const iso = parseDateTimeText(value);
    if (!iso) {
      picker.value = "";
      return;
    }
    const date = new Date(iso);
    const localValue = `${date.getFullYear().toString().padStart(4, "0")}-${(date.getMonth() + 1).toString().padStart(2, "0")}-${date
      .getDate()
      .toString()
      .padStart(2, "0")}T${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
    picker.value = localValue;
  }, [value]);

  const resolveState = (caretOverride?: number): EditorState => {
    const el = inputRef.current;
    const caret = caretOverride ?? el?.selectionStart ?? value.length;
    const fields = fieldsFromDisplay(value);
    if (caret !== lastCaretRef.current) {
      siRef.current = locateSegment(fields, caret);
      lastCaretRef.current = caret;
    }
    return { fields, caret, si: siRef.current };
  };

  const commit = (result: EditorState | null) => {
    if (!result) return;
    const formatted = renderFields(result.fields);
    const clampedCaret = Math.min(result.caret, formatted.length);
    siRef.current = result.si;
    pendingCaretRef.current = clampedCaret;
    lastCaretRef.current = clampedCaret;
    if (formatted !== value) {
      onChange(formatted);
    } else {
      setCaret(clampedCaret);
    }
  };

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

  const handleBeforeInput = (e: FormEvent<HTMLInputElement>) => {
    const native = e.nativeEvent as InputEvent;
    if (native.isComposing) return;
    if (native.inputType.startsWith("deleteContent")) {
      e.preventDefault();
      return;
    }
    if (native.inputType === "insertFromPaste") {
      if (pasteHandledRef.current) {
        pasteHandledRef.current = false;
        return;
      }
    }
    if (native.data == null) return;
    e.preventDefault();
    const el = e.currentTarget;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    let state = resolveState(start);
    if (start !== end) {
      const cleared = clearSelection(state.fields, start, end);
      siRef.current = locateSegment(state.fields, start);
      lastCaretRef.current = start;
      state = { fields: cleared, caret: start, si: siRef.current };
    }
    commit(applyInsert(state, native.data));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    const el = e.currentTarget;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;

    if (e.key === "Backspace" || e.key === "Delete") {
      e.preventDefault();
      if (start !== end) {
        const cleared = clearSelection(fieldsFromDisplay(value), start, end);
        const formatted = renderFields(cleared);
        pendingCaretRef.current = start;
        lastCaretRef.current = start;
        siRef.current = locateSegment(cleared, start);
        if (formatted !== value) {
          onChange(formatted);
        } else {
          setCaret(start);
        }
        return;
      }
      commit(e.key === "Backspace" ? applyBackspace(resolveState(start)) : applyDelete(resolveState(start)));
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      setCaret(start);
      siRef.current = locateSegment(fieldsFromDisplay(value), start);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      setCaret(end);
      siRef.current = locateSegment(fieldsFromDisplay(value), end);
    } else if (e.key === "Home") {
      e.preventDefault();
      setCaret(0);
      siRef.current = locateSegment(fieldsFromDisplay(value), 0);
    } else if (e.key === "End") {
      e.preventDefault();
      setCaret(value.length);
      siRef.current = locateSegment(fieldsFromDisplay(value), value.length);
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text");
    if (!text) return;
    e.preventDefault();
    pasteHandledRef.current = true;
    const el = e.currentTarget;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    let state = resolveState(start);
    if (start !== end) {
      const cleared = clearSelection(state.fields, start, end);
      siRef.current = locateSegment(state.fields, start);
      lastCaretRef.current = start;
      state = { fields: cleared, caret: start, si: siRef.current };
    }
    commit(applyInsert(state, text));
  };

  const handleInput = (e: FormEvent<HTMLInputElement>) => {
    const raw = e.currentTarget.value;
    const parsed = fieldsFromDisplay(raw);
    const formatted = renderFields(parsed);
    if (formatted !== value) {
      e.currentTarget.value = formatted;
      pendingCaretRef.current = raw.length;
      lastCaretRef.current = Math.min(raw.length, formatted.length);
      siRef.current = locateSegment(parsed, raw.length);
      onChange(formatted);
    }
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        placeholder={placeholder}
        value={value}
        onChange={handleInput}
        onBeforeInput={handleBeforeInput}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        className={cn(
          "rounded-xl pr-10",
          invalid && "border-destructive text-destructive placeholder:text-destructive/70 focus-visible:ring-destructive"
        )}
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
            const text = toDisplayText(new Date(e.target.value));
            pendingCaretRef.current = text.length;
            lastCaretRef.current = text.length;
            siRef.current = locateSegment(fieldsFromDisplay(text), text.length);
            onChange(text);
          }
        }}
      />
    </div>
  );
}
