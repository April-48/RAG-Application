/**
 * Reusable search input for document lists (Dashboard + Chat sidebar).
 * type="search" gives a nice clear button on some browsers.
 */

interface DocumentSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  placeholder?: string;
  className?: string;
}

/** Styled search input for filtering document lists. */
export default function DocumentSearchInput({
  value,
  onChange,
  ariaLabel,
  placeholder = "Search…",
  className = "",
}: DocumentSearchInputProps) {
  return (
    <input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel}
      placeholder={placeholder}
      autoComplete="off"
      className={`glass-input w-full text-sm ${className}`}
    />
  );
}
