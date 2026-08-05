import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

export function DateTimeInput({
  value,
  onChange,
  invalid = false,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  invalid?: boolean;
  className?: string;
}) {
  return (
    <Input
      type="datetime-local"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "rounded-xl",
        invalid && "border-destructive text-destructive focus-visible:ring-destructive",
        className,
      )}
    />
  );
}
