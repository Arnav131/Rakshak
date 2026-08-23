"""
Rakshak AI Engine — Custom Loss Functions
============================================
Specialized losses for each model type.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional


# ═══════════════════════════════════════════════════════════════════
# VAE LOSS (ELBO)
# ═══════════════════════════════════════════════════════════════════

class VAELoss(nn.Module):
    """
    VAE Evidence Lower Bound (ELBO) loss.

    ELBO = Reconstruction Loss + β * KL Divergence

    β-VAE with KL annealing: starts with β=0 (pure reconstruction)
    and linearly increases to the target β over warmup epochs.
    This prevents posterior collapse.
    """

    def __init__(
        self,
        kl_weight: float = 0.001,
        kl_anneal_epochs: int = 20,
    ):
        super().__init__()
        self.kl_weight = kl_weight
        self.kl_anneal_epochs = kl_anneal_epochs
        self._current_epoch = 0

    def set_epoch(self, epoch: int):
        """Update current epoch for KL annealing."""
        self._current_epoch = epoch

    @property
    def current_beta(self) -> float:
        """Get current KL weight based on annealing schedule."""
        if self.kl_anneal_epochs <= 0:
            return self.kl_weight
        progress = min(1.0, self._current_epoch / self.kl_anneal_epochs)
        return self.kl_weight * progress

    def forward(
        self,
        x_recon: torch.Tensor,
        x_target: torch.Tensor,
        mu: torch.Tensor,
        log_var: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute ELBO loss.

        Args:
            x_recon: Reconstructed input (B, W, C)
            x_target: Original input (B, W, C)
            mu: Latent mean (B, D)
            log_var: Latent log-variance (B, D)

        Returns:
            Dict with total_loss, recon_loss, kl_loss, beta
        """
        # Reconstruction loss (MSE)
        recon_loss = F.mse_loss(x_recon, x_target, reduction="mean")

        # KL divergence: D_KL(q(z|x) || p(z))
        # Closed-form for Gaussian: -0.5 * sum(1 + log_var - mu^2 - exp(log_var))
        kl_loss = -0.5 * torch.mean(
            1 + log_var - mu.pow(2) - log_var.exp()
        )

        beta = self.current_beta
        total_loss = recon_loss + beta * kl_loss

        return {
            "total_loss": total_loss,
            "recon_loss": recon_loss,
            "kl_loss": kl_loss,
            "beta": torch.tensor(beta),
        }


# ═══════════════════════════════════════════════════════════════════
# FOCAL LOSS (for imbalanced binary classification)
# ═══════════════════════════════════════════════════════════════════

class FocalLoss(nn.Module):
    """
    Focal Loss for imbalanced binary classification.

    FL(p_t) = -α_t * (1 - p_t)^γ * log(p_t)

    Down-weights easy examples (high p_t) and focuses training
    on hard examples (low p_t). Critical for the imbalanced
    anomaly detection problem.
    """

    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = "mean",
    ):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            predictions: (B,) predicted probabilities (after sigmoid)
            targets: (B,) binary labels

        Returns:
            Focal loss scalar
        """
        p = predictions.clamp(1e-7, 1 - 1e-7)
        ce_loss = F.binary_cross_entropy(p, targets, reduction="none")

        p_t = p * targets + (1 - p) * (1 - targets)
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        focal_weight = alpha_t * (1 - p_t) ** self.gamma

        loss = focal_weight * ce_loss

        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss


# ═══════════════════════════════════════════════════════════════════
# MULTI-TASK FAILURE PREDICTION LOSS
# ═══════════════════════════════════════════════════════════════════

class MultiTaskFailureLoss(nn.Module):
    """
    Combined loss for multi-horizon failure prediction.

    Each horizon gets its own Focal Loss. The total loss is a
    weighted sum, with shorter horizons weighted higher (they're
    more actionable).
    """

    def __init__(
        self,
        horizon_names: list = None,
        horizon_weights: Optional[Dict[str, float]] = None,
        focal_alpha: float = 0.25,
        focal_gamma: float = 2.0,
    ):
        super().__init__()
        if horizon_names is None:
            horizon_names = ["1h", "6h", "24h"]

        if horizon_weights is None:
            # Shorter horizons weighted higher (more urgent)
            horizon_weights = {"1h": 1.5, "6h": 1.0, "24h": 0.7}

        self.horizon_names = horizon_names
        self.horizon_weights = horizon_weights
        self.focal_losses = nn.ModuleDict({
            h: FocalLoss(alpha=focal_alpha, gamma=focal_gamma)
            for h in horizon_names
        })

    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Args:
            predictions: {horizon: (B,) probabilities}
            targets: (B, num_horizons) binary labels

        Returns:
            Dict with total_loss and per-horizon losses
        """
        losses = {}
        total = torch.tensor(0.0, device=targets.device)

        for i, h in enumerate(self.horizon_names):
            h_loss = self.focal_losses[h](predictions[h], targets[:, i])
            weight = self.horizon_weights.get(h, 1.0)
            losses[f"loss_{h}"] = h_loss
            total = total + weight * h_loss

        losses["total_loss"] = total
        return losses


# ═══════════════════════════════════════════════════════════════════
# LABEL SMOOTHING CROSS ENTROPY (for fault classification)
# ═══════════════════════════════════════════════════════════════════

class LabelSmoothingCrossEntropy(nn.Module):
    """
    Cross-entropy loss with label smoothing for fault classification.

    Smoothing prevents the model from becoming over-confident,
    which improves calibration and generalization.
    """

    def __init__(
        self,
        smoothing: float = 0.1,
        weight: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        self.smoothing = smoothing
        self.weight = weight

    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            logits: (B, C) raw class scores
            targets: (B,) integer class labels

        Returns:
            Smoothed cross-entropy loss
        """
        num_classes = logits.shape[1]
        log_probs = F.log_softmax(logits, dim=1)

        # Create smoothed target distribution
        with torch.no_grad():
            smooth_targets = torch.full_like(
                log_probs, self.smoothing / (num_classes - 1)
            )
            smooth_targets.scatter_(
                1, targets.unsqueeze(1), 1.0 - self.smoothing
            )

        # Weighted loss
        loss = -(smooth_targets * log_probs).sum(dim=1)

        if self.weight is not None:
            sample_weights = self.weight[targets]
            loss = loss * sample_weights

        return loss.mean()
