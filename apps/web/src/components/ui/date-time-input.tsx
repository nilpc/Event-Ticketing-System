import { useRef } from "react";
import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { parseDateTimeText, toDisplayText } from "@/components/ui/date-time-mask";

export function DateTimeInput({
  value,
  onChange,
  invalid = false,
}: {
  value: string;
  onChange: (iso: string) => void;
  invalid?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const isoValue = (() => {
    const iso = parseDateTimeText(value);
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  })();

  const openPicker = () => {
    const el = inputRef.current as (HTMLInputElement & { showPicker?: () => void }) | null;
    if (!el) return;
    try {
      if (el.showPicker) {
        el.showPicker();
      } else {
        el.focus();
      }
    } catch {
      el.focus();
    }
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        type="datetime-local"
        value={isoValue}
        onChange={(e) => {
          if (e.target.value) {
            onChange(toDisplayText(new Date(e.target.value)));
          }
        }}
        className={cn(
          "rounded-xl pr-10",
          invalid && "border-destructive text-destructive focus-visible:ring-destructive",
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
    </div>
  );
}
