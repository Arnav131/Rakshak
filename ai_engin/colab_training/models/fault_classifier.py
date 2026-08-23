"""
Rakshak AI Engine — Fault Classification Model
=================================================
ResNet-style 1D CNN for multi-class fault type classification.

Identifies which specific fault type is occurring when an anomaly
is detected (e.g., thermal_buckle, rail_fracture, gauge_widening).

Architecture:
    Input (B, W, F) → Conv1D stem → 4 ResNet stages
    → Global Average Pooling → Dense classifier → Softmax
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict

from config import FAULT_CONFIG


# ═══════════════════════════════════════════════════════════════════
# RESNET 1D BUILDING BLOCKS
# ═══════════════════════════════════════════════════════════════════

class ResBlock1D(nn.Module):
    """
    1D Residual Block with two convolutions and skip connection.

    Structure:
        x → Conv1D → BN → GELU → Conv1D → BN → + → GELU
        └───────────────── (1x1 conv if needed) ──┘
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        dropout: float = 0.1,
    ):
        super().__init__()
        padding = kernel_size // 2

        self.conv1 = nn.Conv1d(
            in_channels, out_channels,
            kernel_size=kernel_size, stride=stride, padding=padding,
        )
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = nn.Conv1d(
            out_channels, out_channels,
            kernel_size=kernel_size, stride=1, padding=padding,
        )
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()

        # Skip connection (1x1 conv if dimensions change)
        self.skip = nn.Identity()
        if in_channels != out_channels or stride != 1:
            self.skip = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride),
                nn.BatchNorm1d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, C, T)"""
        identity = self.skip(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.activation(out)
        out = self.dropout(out)

        out = self.conv2(out)
        out = self.bn2(out)

        out = out + identity
        out = self.activation(out)

        return out


class ResNetStage(nn.Module):
    """A stage of multiple ResNet blocks with the same output channels."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_blocks: int = 2,
        stride: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        blocks = [ResBlock1D(in_channels, out_channels, stride=stride, dropout=dropout)]
        for _ in range(1, num_blocks):
            blocks.append(ResBlock1D(out_channels, out_channels, dropout=dropout))
        self.blocks = nn.Sequential(*blocks)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.blocks(x)


# ═══════════════════════════════════════════════════════════════════
# SQUEEZE-AND-EXCITATION MODULE
# ═══════════════════════════════════════════════════════════════════

class SqueezeExcitation1D(nn.Module):
    """
    SE block for 1D convolutions.

    Learns channel-wise attention weights to emphasize
    informative features and suppress less useful ones.
    """

    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        self.squeeze = nn.AdaptiveAvgPool1d(1)
        self.excitation = nn.Sequential(
            nn.Linear(channels, channels // reduction),
            nn.GELU(),
            nn.Linear(channels // reduction, channels),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, C, T)"""
        B, C, T = x.shape
        se = self.squeeze(x).view(B, C)
        se = self.excitation(se).view(B, C, 1)
        return x * se


# ═══════════════════════════════════════════════════════════════════
# FULL FAULT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════

class FaultClassifier(nn.Module):
    """
    ResNet-1D multi-class fault classifier.

    Takes sensor feature windows (with optional anomaly score) and
    predicts which fault type is occurring.

    Architecture:
        Conv1D Stem → 4 ResNet Stages (with SE blocks)
        → Global Average Pooling
        → Dense Classifier with Dropout
    """

    def __init__(self, config=FAULT_CONFIG):
        super().__init__()
        self.config = config

        # Stem: initial feature extraction
        self.stem = nn.Sequential(
            nn.Conv1d(config.num_features, config.initial_channels, kernel_size=7, stride=1, padding=3),
            nn.BatchNorm1d(config.initial_channels),
            nn.GELU(),
        )

        # ResNet stages with increasing channels
        stages = []
        in_ch = config.initial_channels
        for i, out_ch in enumerate(config.block_channels):
            stride = 2 if i > 0 else 1  # Downsample from second stage
            stages.append(ResNetStage(
                in_ch, out_ch,
                num_blocks=config.blocks_per_stage,
                stride=stride,
                dropout=0.1,
            ))
            # Add SE block after each stage
            stages.append(SqueezeExcitation1D(out_ch))
            in_ch = out_ch

        self.stages = nn.Sequential(*stages)

        # Global Average Pooling
        self.gap = nn.AdaptiveAvgPool1d(1)

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(config.block_channels[-1], 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(config.head_dropout),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(config.head_dropout),
            nn.Linear(128, config.num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, W, F) — windowed features

        Returns:
            logits: (B, num_classes) — raw class scores (before softmax)
        """
        # (B, W, F) → (B, F, W) for Conv1d
        x = x.permute(0, 2, 1)

        # Stem
        x = self.stem(x)

        # ResNet stages
        x = self.stages(x)

        # Global Average Pooling → (B, C, 1) → (B, C)
        x = self.gap(x).squeeze(-1)

        # Classifier
        logits = self.classifier(x)

        return logits

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Get probability distribution over fault types."""
        with torch.no_grad():
            logits = self.forward(x)
            return F.softmax(logits, dim=1)

    def predict_top_k(
        self,
        x: torch.Tensor,
        k: int = 5,
        class_names: List[str] = None,
    ) -> List[List[Dict]]:
        """
        Get top-K predictions with probabilities.

        Returns:
            List of lists of dicts: [{class, probability}, ...]
        """
        probs = self.predict_proba(x)
        top_probs, top_indices = torch.topk(probs, k=min(k, probs.shape[1]), dim=1)

        results = []
        for i in range(len(x)):
            sample_results = []
            for j in range(top_probs.shape[1]):
                idx = top_indices[i, j].item()
                prob = top_probs[i, j].item()
                name = class_names[idx] if class_names else str(idx)
                sample_results.append({"class": name, "probability": prob})
            results.append(sample_results)

        return results


def build_fault_classifier(config=FAULT_CONFIG) -> FaultClassifier:
    """Factory function to create the fault classifier."""
    model = FaultClassifier(config)

    # Kaiming initialization for conv layers, Xavier for linear
    for m in model.modules():
        if isinstance(m, nn.Conv1d):
            nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
        elif isinstance(m, nn.BatchNorm1d):
            nn.init.constant_(m.weight, 1)
            nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.Linear):
            nn.init.xavier_normal_(m.weight)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"FaultClassifier: {total_params:,} params, {config.num_classes} classes")

    return model
