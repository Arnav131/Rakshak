"""
Rakshak AI Engine — Failure Prediction Training Loop
======================================================
Training pipeline for the TCN + Transformer + BiLSTM
multi-horizon failure prediction model.
"""

import os
import time
import logging
import numpy as np
import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from typing import Optional, Dict

from config import FAILURE_CONFIG, TRAINING_CONFIG, CHECKPOINT_DIR
from models.failure_predictor import build_failure_model, FailurePredictionModel
from training.losses import MultiTaskFailureLoss
from training.metrics import compute_binary_metrics

logger = logging.getLogger(__name__)


class FailurePredictorTrainer:
    """
    Training loop for the multi-horizon failure prediction model.

    Features:
    - Multi-task training with horizon-weighted focal loss
    - Mixed precision (FP16)
    - Gradient accumulation for large effective batch size
    - Warmup + cosine annealing LR schedule
    - Early stopping on average validation AUROC across horizons
    """

    def __init__(
        self,
        model: Optional[FailurePredictionModel] = None,
        config=FAILURE_CONFIG,
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
        self.model = model or build_failure_model(config)
        self.model = self.model.to(self.device)

        # Loss
        self.criterion = MultiTaskFailureLoss(
            horizon_names=config.prediction_horizons,
        )

        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )

        # LR Scheduler with warmup
        self.warmup_scheduler = torch.optim.lr_scheduler.LinearLR(
            self.optimizer,
            start_factor=0.01,
            end_factor=1.0,
            total_iters=training_config.warmup_epochs,
        )
        self.main_scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer,
            T_0=training_config.scheduler_T_0,
            T_mult=training_config.scheduler_T_mult,
        )
        self.scheduler = torch.optim.lr_scheduler.SequentialLR(
            self.optimizer,
            schedulers=[self.warmup_scheduler, self.main_scheduler],
            milestones=[training_config.warmup_epochs],
        )

        # Mixed precision
        self.scaler = GradScaler(enabled=training_config.use_mixed_precision)
        self.use_amp = training_config.use_mixed_precision

        # Training state
        self.best_val_auroc = 0.0
        self.epochs_without_improvement = 0
        self.history = {
            "train_loss": [], "val_loss": [],
            "val_auroc_1h": [], "val_auroc_6h": [], "val_auroc_24h": [],
            "lr": [],
        }

    def train_epoch(self, train_loader) -> Dict[str, float]:
        """Run one training epoch."""
        self.model.train()
        total_loss = 0
        horizon_losses = {h: 0 for h in self.config.prediction_horizons}
        num_batches = 0
        accum_steps = self.training_config.gradient_accumulation_steps

        self.optimizer.zero_grad()

        for batch_idx, (x, y) in enumerate(train_loader):
            x = x.to(self.device)
            y = y.to(self.device)

            with autocast(enabled=self.use_amp):
                predictions = self.model(x)
                loss_dict = self.criterion(predictions, y)
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

            total_loss += loss_dict["total_loss"].item()
            for h in self.config.prediction_horizons:
                horizon_losses[h] += loss_dict[f"loss_{h}"].item()
            num_batches += 1

        avg_metrics = {"total_loss": total_loss / max(num_batches, 1)}
        for h in self.config.prediction_horizons:
            avg_metrics[f"loss_{h}"] = horizon_losses[h] / max(num_batches, 1)

        return avg_metrics

    @torch.no_grad()
    def validate(self, val_loader) -> Dict[str, float]:
        """Run validation with full metric computation."""
        self.model.eval()
        total_loss = 0
        num_batches = 0

        all_preds = {h: [] for h in self.config.prediction_horizons}
        all_labels = {h: [] for h in self.config.prediction_horizons}

        for x, y in val_loader:
            x = x.to(self.device)
            y = y.to(self.device)

            predictions = self.model(x)
            loss_dict = self.criterion(predictions, y)
            total_loss += loss_dict["total_loss"].item()
            num_batches += 1

            for i, h in enumerate(sorted(self.config.prediction_horizons)):
                all_preds[h].append(predictions[h].cpu().numpy())
                all_labels[h].append(y[:, i].cpu().numpy())

        val_metrics = {"total_loss": total_loss / max(num_batches, 1)}

        # Per-horizon metrics
        auroc_sum = 0
        for h in self.config.prediction_horizons:
            preds = np.concatenate(all_preds[h])
            labels = np.concatenate(all_labels[h])
            h_metrics = compute_binary_metrics(labels, preds, prefix=f"failure_{h}_")
            val_metrics.update(h_metrics)
            auroc_sum += h_metrics.get(f"failure_{h}_auroc", 0)

        val_metrics["avg_auroc"] = auroc_sum / len(self.config.prediction_horizons)

        return val_metrics

    def train(
        self,
        train_loader,
        val_loader,
        max_epochs: int = None,
        patience: int = None,
        checkpoint_dir: str = None,
    ) -> Dict:
        """Full training loop."""
        max_epochs = max_epochs or self.config.max_epochs
        patience = patience or self.config.early_stopping_patience
        checkpoint_dir = checkpoint_dir or CHECKPOINT_DIR
        os.makedirs(checkpoint_dir, exist_ok=True)

        logger.info(f"Starting Failure Predictor training: {max_epochs} epochs")
        logger.info(f"Horizons: {self.config.prediction_horizons}")

        for epoch in range(max_epochs):
            t0 = time.time()

            train_metrics = self.train_epoch(train_loader)
            self.scheduler.step()
            val_metrics = self.validate(val_loader)

            lr = self.optimizer.param_groups[0]["lr"]
            self.history["train_loss"].append(train_metrics["total_loss"])
            self.history["val_loss"].append(val_metrics["total_loss"])
            self.history["lr"].append(lr)
            for h in self.config.prediction_horizons:
                key = f"val_auroc_{h}"
                self.history.setdefault(key, []).append(
                    val_metrics.get(f"failure_{h}_auroc", 0)
                )

            elapsed = time.time() - t0
            avg_auroc = val_metrics["avg_auroc"]

            logger.info(
                f"Epoch {epoch + 1}/{max_epochs} "
                f"| Train: {train_metrics['total_loss']:.4f} "
                f"| Val: {val_metrics['total_loss']:.4f} "
                f"| AUROC: " + " / ".join(
                    f"{h}={val_metrics.get(f'failure_{h}_auroc', 0):.4f}"
                    for h in self.config.prediction_horizons
                ) +
                f" | Avg: {avg_auroc:.4f}"
                f" | LR: {lr:.6f}"
                f" | {elapsed:.1f}s"
            )

            # Checkpointing
            if avg_auroc > self.best_val_auroc:
                self.best_val_auroc = avg_auroc
                self.epochs_without_improvement = 0
                self.save_checkpoint(
                    os.path.join(checkpoint_dir, "failure_predictor_best.pt"),
                    epoch, val_metrics,
                )
                logger.info(f"  ✓ New best (avg AUROC={avg_auroc:.4f})")
            else:
                self.epochs_without_improvement += 1
                if self.epochs_without_improvement >= patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

        # Load best
        best_path = os.path.join(checkpoint_dir, "failure_predictor_best.pt")
        if os.path.exists(best_path):
            self.load_checkpoint(best_path)

        return self.history

    def save_checkpoint(self, path: str, epoch: int, metrics: dict):
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_auroc": self.best_val_auroc,
            "metrics": metrics,
            "config": self.config,
        }, path)

    def load_checkpoint(self, path: str):
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded failure predictor from {path}")
