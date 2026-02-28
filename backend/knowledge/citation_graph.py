"""Citation graph built on NetworkX DiGraph with JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx  # type: ignore[import-untyped]

from backend.config import settings


class CitationGraph:

    def __init__(self, persist_path: str | None = None) -> None:
        self._persist_path = Path(
            persist_path
            or str(settings.workspace_dir / "citation_graph.json")
        )
        self._graph = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    def add_paper(self, paper_id: str, metadata: dict[str, Any] | None = None) -> None:
        self._graph.add_node(paper_id, **(metadata or {}))

    def add_citation(self, from_paper: str, to_paper: str) -> None:
        if from_paper not in self._graph:
            self._graph.add_node(from_paper)
        if to_paper not in self._graph:
            self._graph.add_node(to_paper)
        self._graph.add_edge(from_paper, to_paper)

    def get_most_cited(self, top_k: int = 10) -> list[str]:
        in_deg = self._graph.in_degree()
        sorted_nodes = sorted(in_deg, key=lambda x: x[1], reverse=True)
        return [node for node, _ in sorted_nodes[:top_k]]

    def get_citation_chain(self, paper_id: str, depth: int = 3) -> nx.DiGraph:
        if paper_id not in self._graph:
            return nx.DiGraph()

        nodes: set[str] = set()
        frontier = {paper_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for n in frontier:
                nodes.add(n)
                next_frontier.update(self._graph.successors(n))
                next_frontier.update(self._graph.predecessors(n))
            frontier = next_frontier - nodes
        nodes.update(frontier)

        return self._graph.subgraph(nodes).copy()

    def find_bridges(self) -> list[str]:
        undirected = self._graph.to_undirected()
        bridge_edges = list(nx.bridges(undirected))
        bridge_nodes: set[str] = set()
        for u, v in bridge_edges:
            bridge_nodes.add(u)
            bridge_nodes.add(v)
        return list(bridge_nodes)

    def save(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        self._persist_path.write_text(json.dumps(data, ensure_ascii=False, default=str))

    def load(self) -> None:
        if not self._persist_path.exists():
            return
        data = json.loads(self._persist_path.read_text())
        self._graph = nx.node_link_graph(data, directed=True)
