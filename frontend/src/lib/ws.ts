type EventHandler = (data: any) => void;

class NexlySocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<EventHandler>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private maxReconnectDelay = 30000; // 30s max

  connect() {
    const token = localStorage.getItem('token');
    if (!token || this.ws?.readyState === WebSocket.OPEN) return;

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${protocol}//${location.host}/ws?token=${token}`);

    this.ws.onopen = () => {
      this.reconnectAttempt = 0; // Reset on successful connection
    };

    this.ws.onmessage = (e) => {
      try {
        const { event, data } = JSON.parse(e.data);
        this.handlers.get(event)?.forEach((fn) => fn(data));
      } catch {}
    };

    // M-15 FIX: Exponential backoff with jitter
    this.ws.onclose = () => {
      this.reconnectAttempt++;
      const baseDelay = Math.min(1000 * 2 ** this.reconnectAttempt, this.maxReconnectDelay);
      const jitter = Math.random() * 1000; // 0-1s random jitter
      this.reconnectTimer = setTimeout(() => this.connect(), baseDelay + jitter);
    };

    this.ws.onerror = () => this.ws?.close();
  }

  disconnect() {
    this.reconnectAttempt = 0;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  on(event: string, handler: EventHandler) {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler);
    return () => this.handlers.get(event)?.delete(handler);
  }

  send(event: string, data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event, data }));
    }
  }
}

export const socket = new NexlySocket();
