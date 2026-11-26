import { RotateCcw, TriangleAlert, X } from 'lucide-react';
import type { StreamStatus } from '../api/client';

interface Props {
  loadError: string | null;
  actionError: string | null;
  streamStatus: StreamStatus;
  onRetry: () => void;
  onDismissActionError: () => void;
}

export default function ConnectionNotice({
  loadError,
  actionError,
  streamStatus,
  onRetry,
  onDismissActionError,
}: Props) {
  if (loadError) {
    return (
      <div className="connection-notice connection-notice--error" role="alert">
        <TriangleAlert aria-hidden="true" size={19} />
        <div>
          <strong>Backend data is unavailable</strong>
          <span>{loadError}</span>
        </div>
        <button className="button button--secondary" type="button" onClick={onRetry}>
          <RotateCcw aria-hidden="true" size={17} />
          Retry connection
        </button>
      </div>
    );
  }

  if (actionError) {
    return (
      <div className="connection-notice connection-notice--error" role="alert">
        <TriangleAlert aria-hidden="true" size={19} />
        <div>
          <strong>Action not completed</strong>
          <span>{actionError}</span>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={onDismissActionError}
          aria-label="Dismiss action error"
        >
          <X aria-hidden="true" size={19} />
        </button>
      </div>
    );
  }

  if (streamStatus === 'reconnecting' || streamStatus === 'offline') {
    return (
      <div className="connection-notice" role="status">
        <RotateCcw aria-hidden="true" size={18} />
        <div>
          <strong>{streamStatus === 'offline' ? 'Stream offline' : 'Reconnecting stream'}</strong>
          <span>Displayed records remain available while live updates reconnect.</span>
        </div>
      </div>
    );
  }

  return null;
}
