# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
"""The seam network: message passing on the face-adjacency graph. Requires PyTorch.

Each face is a node; two faces that share an edge are joined. Every layer lets a face see its neighbours and a
per-mesh mean (so the network can reason about whole-shape structure such as closed seam loops, not just local
neighbourhoods). The head scores each dual edge from the two faces it joins and is symmetric in them, so an
undirected edge has exactly one answer.
"""
import torch  # pylint: disable=import-error  # optional dependency, not installed in CI
from torch import nn  # pylint: disable=import-error

from ._geometry import EDGE_DIM, NODE_DIM

__all__ = ['MessagePassingLayer', 'SeamNet']


class MessagePassingLayer(nn.Module):
    """One round of neighbour messages plus a per-mesh global context vector, with a residual connection."""

    def __init__(self, hidden: int) -> None:
        """Create the layer.

        Args:
            hidden: Feature width of nodes and edges.
        """
        super().__init__()
        self.message = _mlp(3 * hidden, hidden, hidden)
        self.norm = nn.LayerNorm(hidden)
        self.update = _mlp(3 * hidden, hidden, hidden)

    def forward(self, node: torch.Tensor, edge: torch.Tensor, src: torch.Tensor, dst: torch.Tensor,
                graph_index: torch.Tensor, face_counts: torch.Tensor) -> torch.Tensor:
        """Update the node features.

        Args:
            node: ``(N, hidden)`` node features.
            edge: ``(2E, hidden)`` features of the directed edges ``src -> dst``.
            src: ``(2E,)`` message sender per directed edge.
            dst: ``(2E,)`` message receiver per directed edge.
            graph_index: ``(N,)`` which mesh each node belongs to.
            face_counts: ``(B,)`` float nodes per mesh.

        Returns:
            ``(N, hidden)`` updated node features.
        """
        message = self.message(torch.cat([node[src], node[dst], edge], dim=-1)).to(node.dtype)
        total = torch.zeros_like(node).index_add_(0, dst, message)
        degree = torch.zeros(node.shape[0], device=node.device, dtype=node.dtype).index_add_(
            0, dst, torch.ones(dst.shape[0], device=node.device, dtype=node.dtype))
        neighbours = total / degree.clamp(min=1).unsqueeze(-1)
        # Accumulate the per-mesh mean in float32: a bfloat16 sum over 10k+ faces loses precision.
        context = torch.zeros(face_counts.shape[0], node.shape[1], device=node.device, dtype=torch.float32)
        context = context.index_add_(0, graph_index, node.float())
        context = (context / face_counts.unsqueeze(-1))[graph_index].to(node.dtype)
        return self.norm(node + self.update(torch.cat([node, neighbours, context], dim=-1)).to(node.dtype))


class SeamNet(nn.Module):
    """Predicts a seam logit for every dual edge of a (batched) face graph."""

    def __init__(self, hidden: int = 128, layers: int = 8) -> None:
        """Create the network.

        Args:
            hidden: Feature width.
            layers: Number of message-passing layers.

        Raises:
            ValueError: If ``hidden`` or ``layers`` is less than 1.
        """
        super().__init__()
        if hidden < 1 or layers < 1:
            raise ValueError(f'hidden and layers must be >= 1, got hidden={hidden}, layers={layers}')
        self.edge_in = _mlp(EDGE_DIM, hidden, hidden)
        self.head = _mlp(3 * hidden, hidden, 1)
        self.layers = nn.ModuleList(MessagePassingLayer(hidden) for _ in range(layers))
        self.node_in = _mlp(NODE_DIM, hidden, hidden)

    def forward(self, node_feat: torch.Tensor, edge_feat: torch.Tensor, pairs: torch.Tensor,
                graph_index: torch.Tensor, face_counts: torch.Tensor) -> torch.Tensor:
        """Score every dual edge.

        Args:
            node_feat: ``(N, NODE_DIM)`` face features.
            edge_feat: ``(E, EDGE_DIM)`` dual-edge features.
            pairs: ``(E, 2)`` face indices joined by each edge.
            graph_index: ``(N,)`` which mesh each face belongs to.
            face_counts: ``(B,)`` float number of faces per mesh.

        Returns:
            ``(E,)`` seam logits (apply a sigmoid for probabilities).
        """
        node = self.node_in(node_feat)
        edge = self.edge_in(edge_feat)
        src, dst = torch.cat([pairs[:, 0], pairs[:, 1]]), torch.cat([pairs[:, 1], pairs[:, 0]])
        both_ways = torch.cat([edge, edge])
        for layer in self.layers:
            node = layer(node, both_ways, src, dst, graph_index, face_counts)
        node_a, node_b = node[pairs[:, 0]], node[pairs[:, 1]]
        return self.head(torch.cat([node_a + node_b, (node_a - node_b).abs(), edge], dim=-1)).squeeze(-1)


def _mlp(inputs: int, hidden: int, outputs: int) -> nn.Sequential:
    """Two linear layers with a SiLU between them."""
    return nn.Sequential(nn.Linear(inputs, hidden), nn.SiLU(), nn.Linear(hidden, outputs))
