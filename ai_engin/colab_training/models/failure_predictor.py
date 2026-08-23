"""
Rakshak AI Engine — Failure Prediction Model
===============================================
Hierarchical Multi-Modal Spatio-Temporal architecture (adapted HM-STT).

Architecture (from agents_README, adapted for available data):
    Sensor Features → TCN Backbone (dilated: 1,2,4,8,16)
    → Multi-Head Self-Attention Transformer (6 layers)
    → Bidirectional LSTM (2 layers, hidden=256)
    → Multi-Task Prediction Heads (1h / 6h / 24h failure probability)
    → Monte Carlo Dropout for uncertainty estimation
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple

from config import FAILURE_CONFIG


# ═══════════════════════════════════════════════════════════════════
# TEMPORAL CONVOLUTIONAL NETWORK (TCN) BACKBONE
# ═══════════════════════════════════════════════════════════════════

class CausalConv1d(nn.Module):
    """Causal convolution — pads only on the left so output can't see future."""

    def __init__(self, in_channels, out_channels, kernel_size, dilation=1):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(
            in_channels, out_channels,
            kernel_size=kernel_size,
            dilation=dilation,
            padding=self.padding,
        )

    def forward(self, x):
        out = self.conv(x)
        # Remove right padding for causal behavior
        if self.padding > 0:
            out = out[:, :, :-self.padding]
        return out


class TCNBlock(nn.Module):
    """
    Single TCN residual block with dilated causal convolution.

    Structure: CausalConv → BatchNorm → GELU → Dropout →
               CausalConv → BatchNorm → GELU → Dropout → Residual
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size, dilation)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size, dilation)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()

        # Residual connection (1x1 conv if channel mismatch)
        self.residual = (
            nn.Conv1d(in_channels, out_channels, 1)
            if in_channels != out_channels
            else nn.Identity()
        )

    def forward(self, x):
        """x: (B, C, T)"""
        residual = self.residual(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.activation(out)
        out = self.dropout(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.activation(out)
        out = self.dropout(out)

        return out + residual


class TCNBackbone(nn.Module):
    """
    Temporal Convolutional Network with exponentially increasing dilations.

    Receptive field = sum(2 * (k-1) * d for d in dilations) for each block.
    With dilations [1,2,4,8,16] and k=3: RF = 2*(2*1 + 2*2 + 2*4 + 2*8 + 2*16) = 124
    """

    def __init__(
        self,
        input_features: int,
        channels: List[int] = None,
        kernel_size: int = None,
        dilations: List[int] = None,
        dropout: float = None,
    ):
        super().__init__()
        if channels is None:
            channels = FAILURE_CONFIG.tcn_channels
        if kernel_size is None:
            kernel_size = FAILURE_CONFIG.tcn_kernel_size
        if dilations is None:
            dilations = FAILURE_CONFIG.tcn_dilations
        if dropout is None:
            dropout = FAILURE_CONFIG.tcn_dropout

        blocks = []
        in_ch = input_features
        for ch, dil in zip(channels, dilations):
            blocks.append(TCNBlock(in_ch, ch, kernel_size, dil, dropout))
            in_ch = ch

        self.network = nn.Sequential(*blocks)
        self.output_channels = channels[-1]

    def forward(self, x):
        """
        Args:
            x: (B, T, F) — batch × time × features

        Returns:
            (B, T, C_out) — temporal features
        """
        # Conv1d expects (B, C, T)
        x = x.permute(0, 2, 1)
        out = self.network(x)
        return out.permute(0, 2, 1)


# ═══════════════════════════════════════════════════════════════════
# POSITIONAL ENCODING
# ═══════════════════════════════════════════════════════════════════

class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for the Transformer."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x):
        """x: (B, T, D)"""
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


# ═══════════════════════════════════════════════════════════════════
# CROSS-MODAL FUSION TRANSFORMER
# ═══════════════════════════════════════════════════════════════════

class FusionTransformer(nn.Module):
    """
    Multi-Head Self-Attention Transformer for temporal fusion.

    6 layers of self-attention over the TCN output sequence.
    Uses pre-norm (LayerNorm before attention) for stability.
    """

    def __init__(
        self,
        d_model: int = None,
        nhead: int = None,
        num_layers: int = None,
        dim_feedforward: int = None,
        dropout: float = None,
    ):
        super().__init__()
        if d_model is None:
            d_model = FAILURE_CONFIG.transformer_d_model
        if nhead is None:
            nhead = FAILURE_CONFIG.transformer_nhead
        if num_layers is None:
            num_layers = FAILURE_CONFIG.transformer_num_layers
        if dim_feedforward is None:
            dim_feedforward = FAILURE_CONFIG.transformer_dim_feedforward
        if dropout is None:
            dropout = FAILURE_CONFIG.transformer_dropout

        self.pos_encoder = PositionalEncoding(d_model, dropout=dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,  # Pre-norm for training stability
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
        )
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, D) — temporal features from TCN

        Returns:
            (B, T, D) — attention-enriched features
        """
        x = self.pos_encoder(x)
        x = self.transformer(x)
        x = self.layer_norm(x)
        return x


# ═══════════════════════════════════════════════════════════════════
# BIDIRECTIONAL LSTM
# ═══════════════════════════════════════════════════════════════════

class TemporalLSTM(nn.Module):
    """
    Bidirectional LSTM for capturing long-range temporal dependencies.

    Takes Transformer output and produces a fixed-size representation
    for the prediction heads.
    """

    def __init__(
        self,
        input_size: int = None,
        hidden_size: int = None,
        num_layers: int = None,
        dropout: float = None,
    ):
        super().__init__()
        if input_size is None:
            input_size = FAILURE_CONFIG.transformer_d_model
        if hidden_size is None:
            hidden_size = FAILURE_CONFIG.lstm_hidden_size
        if num_layers is None:
            num_layers = FAILURE_CONFIG.lstm_num_layers
        if dropout is None:
            dropout = FAILURE_CONFIG.lstm_dropout

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.output_size = hidden_size * 2  # Bidirectional

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, D) — transformer output

        Returns:
            (B, H*2) — final hidden state (concatenated forward + backward)
        """
        output, (h_n, _) = self.lstm(x)

        # Concatenate final forward and backward hidden states
        # h_n shape: (num_layers * 2, B, H)
        forward_h = h_n[-2]  # Last forward layer
        backward_h = h_n[-1]  # Last backward layer
        combined = torch.cat([forward_h, backward_h], dim=1)  # (B, H*2)

        return combined


# ═══════════════════════════════════════════════════════════════════
# MULTI-TASK PREDICTION HEADS
# ═══════════════════════════════════════════════════════════════════

class PredictionHead(nn.Module):
    """
    Single prediction head for one time horizon.

    3-layer MLP with dropout for Monte Carlo uncertainty estimation.
    Output: single sigmoid probability.
    """

    def __init__(
        self,
        input_size: int,
        hidden_dims: List[int] = None,
        dropout: float = None,
    ):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = FAILURE_CONFIG.head_hidden_dims
        if dropout is None:
            dropout = FAILURE_CONFIG.head_dropout

        layers = []
        in_dim = input_size
        for h_dim in hidden_dims:
            layers.extend([
                nn.Linear(in_dim, h_dim),
                nn.LayerNorm(h_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            ])
            in_dim = h_dim

        layers.append(nn.Linear(in_dim, 1))

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, D) — LSTM output

        Returns:
            (B, 1) — failure probability (before sigmoid)
        """
        return self.network(x)


# ═══════════════════════════════════════════════════════════════════
# FULL FAILURE PREDICTION MODEL
# ═══════════════════════════════════════════════════════════════════

class FailurePredictionModel(nn.Module):
    """
    Complete Hierarchical Multi-Modal Spatio-Temporal model.

    Pipeline:
        Input Features (B, W, F)
        → TCN Backbone (dilated causal convolutions)
        → Projection to transformer dimension
        → Multi-Head Self-Attention Transformer (6 layers)
        → Bidirectional LSTM (2 layers)
        → 3 Parallel Prediction Heads (1h, 6h, 24h)
        → Sigmoid probabilities

    Supports Monte Carlo Dropout for uncertainty estimation.
    """

    def __init__(self, config=FAILURE_CONFIG):
        super().__init__()
        self.config = config
        self.horizons = config.prediction_horizons

        # 1. TCN Backbone
        self.tcn = TCNBackbone(
            input_features=config.num_features,
            channels=config.tcn_channels,
            kernel_size=config.tcn_kernel_size,
            dilations=config.tcn_dilations,
            dropout=config.tcn_dropout,
        )

        # 2. Project TCN output to transformer dimension
        tcn_out = config.tcn_channels[-1]
        self.projection = nn.Sequential(
            nn.Linear(tcn_out, config.transformer_d_model),
            nn.LayerNorm(config.transformer_d_model),
            nn.GELU(),
        )

        # 3. Transformer Fusion
        self.transformer = FusionTransformer(
            d_model=config.transformer_d_model,
            nhead=config.transformer_nhead,
            num_layers=config.transformer_num_layers,
            dim_feedforward=config.transformer_dim_feedforward,
            dropout=config.transformer_dropout,
        )

        # 4. BiLSTM
        self.lstm = TemporalLSTM(
            input_size=config.transformer_d_model,
            hidden_size=config.lstm_hidden_size,
            num_layers=config.lstm_num_layers,
            dropout=config.lstm_dropout,
        )

        # 5. Multi-Task Prediction Heads
        lstm_out = self.lstm.output_size
        self.heads = nn.ModuleDict({
            horizon: PredictionHead(
                input_size=lstm_out,
                hidden_dims=config.head_hidden_dims,
                dropout=config.head_dropout,
            )
            for horizon in self.horizons
        })

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Full forward pass.

        Args:
            x: (B, W, F) — windowed features

        Returns:
            dict of {horizon: probability} where each is (B, 1)
        """
        # TCN: (B, W, F) → (B, W, C_tcn)
        tcn_out = self.tcn(x)

        # Project: (B, W, C_tcn) → (B, W, D_model)
        projected = self.projection(tcn_out)

        # Transformer: (B, W, D_model) → (B, W, D_model)
        attn_out = self.transformer(projected)

        # BiLSTM: (B, W, D_model) → (B, H*2)
        lstm_out = self.lstm(attn_out)

        # Prediction heads: (B, H*2) → {horizon: (B, 1)}
        predictions = {}
        for horizon in self.horizons:
            logits = self.heads[horizon](lstm_out)
            predictions[horizon] = torch.sigmoid(logits).squeeze(1)  # (B,)

        return predictions

    def predict_with_uncertainty(
        self,
        x: torch.Tensor,
        n_passes: int = None,
    ) -> Dict[str, Dict[str, torch.Tensor]]:
        """
        Monte Carlo Dropout inference for uncertainty estimation.

        Runs n_passes forward passes with dropout enabled, then
        computes mean and std of predictions.

        Returns:
            dict of {horizon: {mean, std, samples}}
        """
        if n_passes is None:
            n_passes = self.config.mc_dropout_passes

        self.train()  # Enable dropout

        all_preds = {h: [] for h in self.horizons}

        with torch.no_grad():
            for _ in range(n_passes):
                preds = self.forward(x)
                for h in self.horizons:
                    all_preds[h].append(preds[h])

        self.eval()

        results = {}
        for h in self.horizons:
            stacked = torch.stack(all_preds[h])  # (n_passes, B)
            results[h] = {
                "mean": stacked.mean(dim=0),
                "std": stacked.std(dim=0),
                "samples": stacked,
            }

        return results


def build_failure_model(config=FAILURE_CONFIG) -> FailurePredictionModel:
    """Factory function to create the failure prediction model."""
    model = FailurePredictionModel(config)

    # Initialize weights
    for name, param in model.named_parameters():
        if "weight" in name and param.dim() >= 2:
            nn.init.xavier_uniform_(param)
        elif "bias" in name:
            nn.init.zeros_(param)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"FailurePredictionModel: {total_params:,} params ({trainable_params:,} trainable)")

    return model
