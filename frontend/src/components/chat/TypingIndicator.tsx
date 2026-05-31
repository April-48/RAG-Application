/**
 * Left-aligned assistant bubble shown while waiting for the first streamed token.
 */

import "./TypingIndicator.css";

/** Animated assistant bubble with three bouncing dots while waiting for tokens. */
export default function TypingIndicator({
  label = "AI is answering",
}: {
  label?: string;
}) {
  return (
    <div
      className="typing-indicator"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <span className="typing-indicator__label">{label}</span>
      <span className="typing-indicator__dots" aria-hidden="true">
        <span className="typing-indicator__dot" />
        <span className="typing-indicator__dot" />
        <span className="typing-indicator__dot" />
      </span>
    </div>
  );
}
