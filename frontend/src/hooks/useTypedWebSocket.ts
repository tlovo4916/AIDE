"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  WSFrameType,
  type WSFrame,
  type WSPushEvent,
  type WSPushPayloadMap,
} from "@/lib/ws-protocol";

type ConnectionStatus = "connecting" | "connected" | "disconnected";
type Listener = (payload: unknown) => void;

function getWsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.hostname}:30001`;
  }
  return "ws://localhost:30001";
}

const WS_BASE = getWsBase();
const HEARTBEAT_INTERVAL = 30_000;
const RECONNECT_BASE_DELAY = 1000;
const RECONNECT_MAX_DELAY = 30_000;

export function useTypedWebSocket(projectId: string) {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Map<string, Set<Listener>>>(new Map());
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const clearTimers = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const url = `${WS_BASE}/ws/projects/${projectId}`;
    setStatus("connecting");

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      setStatus("connected");
      reconnectAttemptRef.current = 0;

      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              type: WSFrameType.REQUEST,
              event: "ping",
              payload: {},
            })
          );
        }
      }, HEARTBEAT_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const frame: WSFrame = JSON.parse(event.data);
        if (frame.event === "pong") return;

        const listeners = listenersRef.current.get(frame.event);
        if (listeners) {
          listeners.forEach((fn) => fn(frame.payload));
        }
      } catch {
        // Ignore malformed frames
      }
    };

    ws.onclose = () => {
      clearTimers();
      if (!mountedRef.current) return;
      setStatus("disconnected");

      const delay = Math.min(
        RECONNECT_BASE_DELAY * 2 ** reconnectAttemptRef.current,
        RECONNECT_MAX_DELAY
      );
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [projectId, clearTimers]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearTimers();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearTimers]);

  const send = useCallback(
    (event: string, payload: unknown, requestId?: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: WSFrameType.REQUEST,
            event,
            payload,
            request_id: requestId,
          })
        );
      }
    },
    []
  );

  const subscribe = useCallback(
    <E extends WSPushEvent>(
      event: E,
      callback: (payload: WSPushPayloadMap[E]) => void
    ): (() => void) => {
      if (!listenersRef.current.has(event)) {
        listenersRef.current.set(event, new Set());
      }
      const listeners = listenersRef.current.get(event)!;
      const wrapped = callback as Listener;
      listeners.add(wrapped);
      return () => {
        listeners.delete(wrapped);
      };
    },
    []
  );

  return { status, send, subscribe };
}
