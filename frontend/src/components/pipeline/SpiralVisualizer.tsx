"use client";

import { useState, useMemo } from "react";

interface SpiralIteration {
  round: number;
  agent: string;
  action: string;
  timestamp: string;
}

interface SpiralVisualizerProps {
  iterations: SpiralIteration[];
}

const AGENT_COLORS: Record<string, string> = {
  director: "#a855f7",
  scientist: "#3b82f6",
  librarian: "#10b981",
  writer: "#06b6d4",
  critic: "#f59e0b",
  orchestrator: "#f43f5e",
};

function polarToCartesian(
  cx: number,
  cy: number,
  angle: number,
  radius: number
) {
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

export default function SpiralVisualizer({
  iterations,
}: SpiralVisualizerProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const width = 400;
  const height = 400;
  const cx = width / 2;
  const cy = height / 2;

  const { pathD, nodes } = useMemo(() => {
    const totalNodes = iterations.length;
    if (totalNodes === 0) return { pathD: "", nodes: [] };

    const maxRadius = Math.min(width, height) / 2 - 30;
    const minRadius = 20;
    const totalAngle = totalNodes * 0.8;

    const computedNodes: { x: number; y: number; iteration: SpiralIteration }[] = [];
    const pathPoints: string[] = [];

    for (let i = 0; i < totalNodes; i++) {
      const t = i / Math.max(totalNodes - 1, 1);
      const angle = t * totalAngle - Math.PI / 2;
      const radius = minRadius + t * (maxRadius - minRadius);
      const { x, y } = polarToCartesian(cx, cy, angle, radius);

      computedNodes.push({ x, y, iteration: iterations[i] });

      if (i === 0) {
        pathPoints.push(`M ${x} ${y}`);
      } else {
        const prevT = (i - 1) / Math.max(totalNodes - 1, 1);
        const prevAngle = prevT * totalAngle - Math.PI / 2;
        const prevRadius = minRadius + prevT * (maxRadius - minRadius);
        const prev = polarToCartesian(cx, cy, prevAngle, prevRadius);

        const midAngle = (prevAngle + angle) / 2;
        const midRadius = (prevRadius + radius) / 2 + 10;
        const ctrl = polarToCartesian(cx, cy, midAngle, midRadius);

        pathPoints.push(`Q ${ctrl.x} ${ctrl.y} ${x} ${y}`);
      }
    }

    return { pathD: pathPoints.join(" "), nodes: computedNodes };
  }, [iterations, cx, cy, width, height]);

  const lastNode = nodes[nodes.length - 1];

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full max-w-md mx-auto"
      >
        {/* Spiral Path */}
        <path
          d={pathD}
          fill="none"
          stroke="#334155"
          strokeWidth="2"
          strokeLinecap="round"
        />

        {/* Nodes */}
        {nodes.map((node, i) => {
          const color =
            AGENT_COLORS[node.iteration.agent] ?? "#64748b";
          const isHovered = hoveredIndex === i;
          const isLast = i === nodes.length - 1;

          return (
            <g
              key={i}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
              className="cursor-pointer"
            >
              <circle
                cx={node.x}
                cy={node.y}
                r={isHovered ? 7 : 5}
                fill={color}
                opacity={isHovered ? 1 : 0.8}
                className="transition-all duration-150"
              />
              {isLast && (
                <>
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r="10"
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    opacity="0.4"
                  >
                    <animate
                      attributeName="r"
                      values="8;14;8"
                      dur="2s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="opacity"
                      values="0.4;0;0.4"
                      dur="2s"
                      repeatCount="indefinite"
                    />
                  </circle>
                </>
              )}
            </g>
          );
        })}

        {/* Round Labels */}
        {nodes.map((node, i) => {
          const showLabel =
            i === 0 ||
            node.iteration.round !== nodes[i - 1]?.iteration.round;

          if (!showLabel) return null;

          return (
            <text
              key={`label-${i}`}
              x={node.x}
              y={node.y - 12}
              textAnchor="middle"
              className="text-[9px] fill-slate-500 select-none"
            >
              R{node.iteration.round}
            </text>
          );
        })}
      </svg>

      {/* Hover Tooltip */}
      {hoveredIndex !== null && nodes[hoveredIndex] && (
        <div
          className="absolute z-10 rounded-md border border-slate-600 bg-slate-800 px-3 py-2 shadow-lg pointer-events-none"
          style={{
            left: `${(nodes[hoveredIndex].x / width) * 100}%`,
            top: `${(nodes[hoveredIndex].y / height) * 100}%`,
            transform: "translate(-50%, -130%)",
          }}
        >
          <p className="text-xs font-medium text-slate-200">
            {nodes[hoveredIndex].iteration.action}
          </p>
          <p className="text-xs text-slate-500">
            {nodes[hoveredIndex].iteration.agent} -- Round{" "}
            {nodes[hoveredIndex].iteration.round}
          </p>
        </div>
      )}

      {/* Legend */}
      <div className="mt-3 flex flex-wrap justify-center gap-3">
        {Object.entries(AGENT_COLORS).map(([role, color]) => (
          <span
            key={role}
            className="inline-flex items-center gap-1.5 text-xs text-slate-500"
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            {role}
          </span>
        ))}
      </div>
    </div>
  );
}
