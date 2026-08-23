"""
Rakshak AI Engine — VAE Training Loop
========================================
Complete training pipeline for the Variational Autoencoder
anomaly detector with KL annealing, mixed precision, and
early stopping.
"""

import os
import time
import logging
import numpy as np
import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from typing import Optional, Dict, Tuple

from config import VAE_CONFIG, TRAINING_CONFIG, DATA_CONFIG, CHECKPOINT_DIR
from models.vae_anomaly import build_vae_model, VAEAnomalyDetector
from training.losses import VAELoss
from training.metrics import compute_binary_metrics, find_optimal_threshold

logger = logging.getLogger(__name__)


class VAETrainer:
    """
    Training loop for the VAE Anomaly Detector.

    Features:
    - Mixed precision training (FP16)
    - KL annealing (prevents posterior collapse)
    - Cosine annealing LR schedule with warm restarts
    - Early stopping on validation reconstruction loss
    - Best model checkpointing
    """

    def __init__(
        self,
        model: Optional[VAEAnomalyDetector] = None,
        config=VAE_CONFIG,
        training_config=TRAINING_CONFIG,
        device: Optional[str] = None,
    ):
        self.config = config
        self.training_config = training_config
        self.device = device or training_config.device

        if torch.cuda.is_available() and self.device == "cuda":
            self.device = "cuda"
        else:
            self.device = "cpu"
            logger.warning("CUDA not available, using CPU")

        # Model
        self.model = model or build_vae_model(config)
        self.model = self.model.to(self.device)

        # Loss
        self.criterion = VAELoss(
            kl_weight=config.kl_weight,
            kl_anneal_epochs=config.kl_anneal_epochs,
        )

        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )

        # LR Scheduler
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer,
            T_0=training_config.scheduler_T_0,
            T_mult=training_config.scheduler_T_mult,
        )

        # Mixed precision
        self.scaler = GradScaler(enabled=training_config.use_mixed_precision)
        self.use_amp = training_config.use_mixed_precision

        # Training state
        self.best_val_loss = float("inf")
        self.epochs_without_improvement = 0
        self.history = {"train_loss": [], "val_loss": [], "kl_loss": [], "recon_loss": [], "lr": []}

    def train_epoch(self, train_loader) -> Dict[str, float]:
        """Run one training epoch."""
        self.model.train()
        epoch_losses = {"total": 0, "recon": 0, "kl": 0}
        num_batches = 0
        accum_steps = self.training_config.gradient_accumulation_steps

        self.optimizer.zero_grad()

        for batch_idx, (x, _) in enumerate(train_loader):
            x = x.to(self.device)

            with autocast(enabled=self.use_amp):
                output = self.model(x)
                loss_dict = self.criterion(
                    output["x_recon"], x,
                    output["mu"], output["log_var"],
                )
                loss = loss_dict["total_loss"] / accum_steps

            self.scaler.scale(loss).backward()

            if (batch_idx + 1) % accum_steps == 0:
                self.scaler.unscale_(self.optimizer)
                nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.training_config.max_grad_norm,
                )
                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.optimizer.zero_grad()

            epoch_losses["total"] += loss_dict["total_loss"].item()
            epoch_losses["recon"] += loss_dict["recon_loss"].item()
            epoch_losses["kl"] += loss_dict["kl_loss"].item()
            num_batches += 1

        return {k: v / max(num_batches, 1) for k, v in epoch_losses.items()}

    @torch.no_grad()
    def validate(self, val_loader) -> Dict[str, float]:
        """Run validation."""
        self.model.eval()
        epoch_losses = {"total": 0, "recon": 0, "kl": 0}
        all_scores = []
        all_labels = []
        num_batches = 0

        for x, y in val_loader:
            x = x.to(self.device)

            output = self.model(x)
            loss_dict = self.criterion(
                output["x_recon"], x,
                output["mu"], output["log_var"],
            )

            epoch_losses["total"] += loss_dict["total_loss"].item()
            epoch_losses["recon"] += loss_dict["recon_loss"].item()
            epoch_losses["kl"] += loss_dict["kl_loss"].item()

            # Compute anomaly scores
            scores = self.model.compute_anomaly_score(x)
            all_scores.append(scores.cpu().numpy())
            all_labels.append(y.numpy())

            num_batches += 1

        avg_losses = {k: v / max(num_batches, 1) for k, v in epoch_losses.items()}

        # Compute detection metrics
        if all_scores:
            scores = np.concatenate(all_scores)
            labels = np.concatenate(all_labels)

            # Normalize scores to [0, 1]
            score_min, score_max = scores.min(), scores.max()
            if score_max > score_min:
                norm_scores = (scores - score_min) / (score_max - score_min)
            else:
                norm_scores = np.zeros_like(scores)

            detection_metrics = compute_binary_metrics(
                labels, norm_scores, prefix="vae_"
            )
            avg_losses.update(detection_metrics)

        return avg_losses

    def train(
        self,
        train_loader,
        val_loader,
        max_epochs: int = None,
        patience: int = None,
        checkpoint_dir: str = None,
    ) -> Dict:
        """
        Full training loop.

        Args:
            train_loader: Training DataLoader
            val_loader: Validation DataLoader
            max_epochs: Max training epochs
            patience: Early stopping patience
            checkpoint_dir: Directory to save checkpoints

        Returns:
            Training history dict
        """
        max_epochs = max_epochs or self.config.max_epochs
        patience = patience or self.config.early_stopping_patience
        checkpoint_dir = checkpoint_dir or CHECKPOINT_DIR
        os.makedirs(checkpoint_dir, exist_ok=True)

        logger.info(f"Starting VAE training: {max_epochs} epochs, patience={patience}")
        logger.info(f"Device: {self.device}, AMP: {self.use_amp}")

        for epoch in range(max_epochs):
            t0 = time.time()
            self.criterion.set_epoch(epoch)

            # Train
            train_metrics = self.train_epoch(train_loader)
            self.scheduler.step()

            # Validate
            val_metrics = self.validate(val_loader)

            # Record history
            lr = self.optimizer.param_groups[0]["lr"]
            self.history["train_loss"].append(train_metrics["total"])
            self.history["val_loss"].append(val_metrics["total"])
            self.history["recon_loss"].append(val_metrics["recon"])
            self.history["kl_loss"].append(val_metrics["kl"])
            self.history["lr"].append(lr)

            elapsed = time.time() - t0

            # Log
            vae_f1 = val_metrics.get("vae_f1", 0)
            vae_auroc = val_metrics.get("vae_auroc", 0)
            logger.info(
                f"Epoch {epoch + 1}/{max_epochs} "
                f"| Train Loss: {train_metrics['total']:.4f} "
                f"| Val Loss: {val_metrics['total']:.4f} "
                f"| Val F1: {vae_f1:.4f} "
                f"| Val AUROC: {vae_auroc:.4f} "
                f"| β: {self.criterion.current_beta:.5f} "
                f"| LR: {lr:.6f} "
                f"| {elapsed:.1f}s"
            )

            # Checkpointing (best model)
            if val_metrics["total"] < self.best_val_loss:
                self.best_val_loss = val_metrics["total"]
                self.epochs_without_improvement = 0
                self.save_checkpoint(
                    os.path.join(checkpoint_dir, "vae_best.pt"),
                    epoch, val_metrics,
                )
                logger.info(f"  ✓ New best model saved (loss={self.best_val_loss:.4f})")
            else:
                self.epochs_without_improvement += 1
                if self.epochs_without_improvement >= patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

        # Load best model
        best_path = os.path.join(checkpoint_dir, "vae_best.pt")
        if os.path.exists(best_path):
            self.load_checkpoint(best_path)
            logger.info("Loaded best model checkpoint")

        return self.history

    def save_checkpoint(self, path: str, epoch: int, metrics: dict):
        """Save model checkpoint."""
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scheduler_state_dict": self.scheduler.state_dict(),
            "best_val_loss": self.best_val_loss,
            "metrics": metrics,
            "config": self.config,
        }, path)

    def load_checkpoint(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded checkpoint from {path} (epoch {checkpoint['epoch']})")

    def compute_threshold(self, val_loader) -> float:
        """
        Compute optimal anomaly threshold on validation data.

        Returns the threshold that maximizes F1 score.
        """
        self.model.eval()
        all_scores = []
        all_labels = []

        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(self.device)
                scores = self.model.compute_anomaly_score(x)
                all_scores.append(scores.cpu().numpy())
                all_labels.append(y.numpy())

        scores = np.concatenate(all_scores)
        labels = np.concatenate(all_labels)

        # Normalize
        s_min, s_max = scores.min(), scores.max()
        if s_max > s_min:
            scores = (scores - s_min) / (s_max - s_min)

        threshold, f1 = find_optimal_threshold(labels, scores, metric="f1")
        logger.info(f"Optimal threshold: {threshold:.3f} (F1={f1:.4f})")

        return threshold
