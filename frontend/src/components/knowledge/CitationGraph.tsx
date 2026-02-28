"use client";

import { useState, useMemo, useCallback, useRef, useEffect } from "react";

interface GraphNode {
  id: string;
  title: string;
  citations: number;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface CitationGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface NodePosition {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  title: string;
  citations: number;
  radius: number;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export default function CitationGraph({ nodes, edges }: CitationGraphProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [positions, setPositions] = useState<NodePosition[]>([]);
  const animFrameRef = useRef<number>(0);
  const tickRef = useRef(0);

  const width = 600;
  const height = 400;

  const maxCitations = Math.max(...nodes.map((n) => n.citations), 1);

  const initialPositions = useMemo(() => {
    return nodes.map((node, i) => {
      const angle = (i / nodes.length) * Math.PI * 2;
      const spread = Math.min(width, height) * 0.3;
      const radius = 6 + (node.citations / maxCitations) * 14;
      return {
        id: node.id,
        x: width / 2 + Math.cos(angle) * spread + (Math.random() - 0.5) * 40,
        y: height / 2 + Math.sin(angle) * spread + (Math.random() - 0.5) * 40,
        vx: 0,
        vy: 0,
        title: node.title,
        citations: node.citations,
        radius,
      };
    });
  }, [nodes, maxCitations, width, height]);

  useEffect(() => {
    const pos = [...initialPositions];
    tickRef.current = 0;

    function simulate() {
      tickRef.current++;
      if (tickRef.current > 300) return;

      const alpha = Math.max(0.001, 1 - tickRef.current / 300);

      for (let i = 0; i < pos.length; i++) {
        for (let j = i + 1; j < pos.length; j++) {
          const dx = pos[j].x - pos[i].x;
          const dy = pos[j].y - pos[i].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = (300 * alpha) / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          pos[i].vx -= fx;
          pos[i].vy -= fy;
          pos[j].vx += fx;
          pos[j].vy += fy;
        }
      }

      for (const edge of edges) {
        const si = pos.findIndex((n) => n.id === edge.source);
        const ti = pos.findIndex((n) => n.id === edge.target);
        if (si === -1 || ti === -1) continue;

        const dx = pos[ti].x - pos[si].x;
        const dy = pos[ti].y - pos[si].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = (dist - 80) * 0.02 * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        pos[si].vx += fx;
        pos[si].vy += fy;
        pos[ti].vx -= fx;
        pos[ti].vy -= fy;
      }

      for (const p of pos) {
        const cdx = width / 2 - p.x;
        const cdy = height / 2 - p.y;
        p.vx += cdx * 0.001 * alpha;
        p.vy += cdy * 0.001 * alpha;
      }

      for (const p of pos) {
        p.vx *= 0.6;
        p.vy *= 0.6;
        p.x = clamp(p.x + p.vx, p.radius + 5, width - p.radius - 5);
        p.y = clamp(p.y + p.vy, p.radius + 5, height - p.radius - 5);
      }

      setPositions(pos.map((p) => ({ ...p })));
      animFrameRef.current = requestAnimationFrame(simulate);
    }

    animFrameRef.current = requestAnimationFrame(simulate);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [initialPositions, edges, width, height]);

  const highlightedEdges = useMemo(() => {
    if (!selectedNode) return new Set<string>();
    const set = new Set<string>();
    for (const edge of edges) {
      if (edge.source === selectedNode || edge.target === selectedNode) {
        set.add(`${edge.source}-${edge.target}`);
      }
    }
    return set;
  }, [selectedNode, edges]);

  const connectedNodes = useMemo(() => {
    if (!selectedNode) return new Set<string>();
    const set = new Set<string>([selectedNode]);
    for (const edge of edges) {
      if (edge.source === selectedNode) set.add(edge.target);
      if (edge.target === selectedNode) set.add(edge.source);
    }
    return set;
  }, [selectedNode, edges]);

  const getNodePos = useCallback(
    (id: string) => positions.find((p) => p.id === id),
    [positions]
  );

  const activeHover = hoveredNode ?? selectedNode;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full rounded-lg bg-slate-900">
        {/* Edges */}
        {edges.map((edge) => {
          const s = getNodePos(edge.source);
          const t = getNodePos(edge.target);
          if (!s || !t) return null;

          const key = `${edge.source}-${edge.target}`;
          const isHighlighted = highlightedEdges.has(key);
          const isDimmed = selectedNode && !isHighlighted;

          return (
            <line
              key={key}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={isHighlighted ? "#3b82f6" : "#334155"}
              strokeWidth={isHighlighted ? 2 : 1}
              opacity={isDimmed ? 0.15 : 0.6}
              className="transition-all duration-200"
            />
          );
        })}

        {/* Nodes */}
        {positions.map((node) => {
          const isHovered = activeHover === node.id;
          const isConnected = connectedNodes.has(node.id);
          const isDimmed = selectedNode && !isConnected;

          return (
            <g
              key={node.id}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              onClick={() =>
                setSelectedNode((prev) =>
                  prev === node.id ? null : node.id
                )
              }
              className="cursor-pointer"
            >
              <circle
                cx={node.x}
                cy={node.y}
                r={isHovered ? node.radius + 2 : node.radius}
                fill={isHovered || isConnected ? "#3b82f6" : "#475569"}
                opacity={isDimmed ? 0.2 : 0.9}
                className="transition-all duration-150"
              />
              {isHovered && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.radius + 6}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="1"
                  opacity="0.3"
                />
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {activeHover && getNodePos(activeHover) && (
        <div
          className="absolute z-10 rounded-md border border-slate-600 bg-slate-800 px-3 py-2 shadow-lg pointer-events-none max-w-xs"
          style={{
            left: `${((getNodePos(activeHover)!.x) / width) * 100}%`,
            top: `${((getNodePos(activeHover)!.y) / height) * 100}%`,
            transform: "translate(-50%, -140%)",
          }}
        >
          <p className="text-xs font-medium text-slate-200 truncate">
            {getNodePos(activeHover)!.title}
          </p>
          <p className="text-xs text-slate-500">
            {getNodePos(activeHover)!.citations} citations
          </p>
        </div>
      )}
    </div>
  );
}
