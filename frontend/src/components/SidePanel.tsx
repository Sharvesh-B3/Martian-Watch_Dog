import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface Props {
  open: boolean;
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
}

const FOCUSABLE =
  'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function SidePanel({
  open,
  title,
  description,
  onClose,
  children,
}: Props) {
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const frame = requestAnimationFrame(() => closeRef.current?.focus());

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.dataset.panelOpen = 'true';
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', handleKeyDown);
      delete document.body.dataset.panelOpen;
      previous?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="panel-layer">
      <button
        className="panel-scrim"
        type="button"
        aria-label={`Close ${title}`}
        onClick={onClose}
      />
      <aside
        className="side-panel"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="side-panel-title"
        aria-describedby="side-panel-description"
      >
        <div className="side-panel__head">
          <div>
            <h2 id="side-panel-title">{title}</h2>
            <p id="side-panel-description">{description}</p>
          </div>
          <button
            className="icon-button"
            type="button"
            ref={closeRef}
            onClick={onClose}
            aria-label={`Close ${title}`}
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>
        <div className="side-panel__body">{children}</div>
      </aside>
    </div>
  );
}
