"""
Rakshak AI Engine — Fault Classifier Training Loop
=====================================================
Training pipeline for the ResNet-1D multi-class fault classifier.
"""

import os
import time
import logging
import numpy as np
import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from typing import Optional, Dict

from config import FAULT_CONFIG, TRAINING_CONFIG, CHECKPOINT_DIR
from models.fault_classifier import build_fault_classifier, FaultClassifier
from training.losses import LabelSmoothingCrossEntropy
from training.metrics import compute_multiclass_metrics

logger = logging.getLogger(__name__)


class FaultClassifierTrainer:
    """
    Training loop for the multi-class fault classifier.

    Features:
    - Label smoothing cross-entropy loss
    - Class-weighted loss for imbalanced fault distribution
    - Mixed precision training
    - Cosine annealing with warmup
    - Early stopping on validation top-1 accuracy
    """

    def __init__(
        self,
        model: Optional[FaultClassifier] = None,
        config=FAULT_CONFIG,
        training_config=TRAINING_CONFIG,
        class_weights: Optional[np.ndarray] = None,
        device: Optional[str] = None,
    ):
        self.config = config
        self.training_config = training_config
        self.device = device or training_config.device

        if torch.cuda.is_available() and self.device == "cuda":
            self.device = "cuda"
        else:
            self.device = "cpu"

        # Model
        self.model = model or build_fault_classifier(config)
        self.model = self.model.to(self.device)

        # Loss
        weight_tensor = None
        if class_weights is not None:
            weight_tensor = torch.from_numpy(class_weights).float().to(self.device)

        self.criterion = LabelSmoothingCrossEntropy(
            smoothing=config.label_smoothing,
            weight=weight_tensor,
        )

        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )

        # LR Scheduler
        self.warmup_scheduler = torch.optim.lr_scheduler.LinearLR(
            self.optimizer, start_factor=0.01, end_factor=1.0,
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

        # State
        self.best_val_acc = 0.0
        self.epochs_without_improvement = 0
        self.history = {
            "train_loss": [], "val_loss": [],
            "val_top1_acc": [], "val_top5_acc": [],
            "val_f1_weighted": [], "lr": [],
        }

    def train_epoch(self, train_loader) -> Dict[str, float]:
        """Run one training epoch."""
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0
        num_batches = 0
        accum_steps = self.training_config.gradient_accumulation_steps

        self.optimizer.zero_grad()

        for batch_idx, (x, y) in enumerate(train_loader):
            x = x.to(self.device)
            y = y.to(self.device)

            with autocast(enabled=self.use_amp):
                logits = self.model(x)
                loss = self.criterion(logits, y) / accum_steps

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

            total_loss += loss.item() * accum_steps
            pred = logits.argmax(dim=1)
            correct += (pred == y).sum().item()
            total += y.size(0)
            num_batches += 1

        return {
            "loss": total_loss / max(num_batches, 1),
            "accuracy": correct / max(total, 1),
        }

    @torch.no_grad()
    def validate(self, val_loader) -> Dict[str, float]:
        """Run validation with full metric computation."""
        self.model.eval()
        total_loss = 0
        num_batches = 0

        all_probs = []
        all_labels = []

        for x, y in val_loader:
            x = x.to(self.device)
            y = y.to(self.device)

            logits = self.model(x)
            loss = self.criterion(logits, y)
            total_loss += loss.item()
            num_batches += 1

            probs = torch.softmax(logits, dim=1).cpu().numpy()
            all_probs.append(probs)
            all_labels.append(y.cpu().numpy())

        val_metrics = {"loss": total_loss / max(num_batches, 1)}

        if all_probs:
            probs = np.concatenate(all_probs)
            labels = np.concatenate(all_labels)
            cls_metrics = compute_multiclass_metrics(
                labels, probs, prefix="fault_"
            )
            val_metrics.update(cls_metrics)

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

        logger.info(f"Starting Fault Classifier training: {max_epochs} epochs, "
                     f"{self.config.num_classes} classes")

        for epoch in range(max_epochs):
            t0 = time.time()

            train_metrics = self.train_epoch(train_loader)
            self.scheduler.step()
            val_metrics = self.validate(val_loader)

            lr = self.optimizer.param_groups[0]["lr"]
            self.history["train_loss"].append(train_metrics["loss"])
            self.history["val_loss"].append(val_metrics["loss"])
            self.history["val_top1_acc"].append(val_metrics.get("fault_top1_accuracy", 0))
            self.history["val_top5_acc"].append(val_metrics.get("fault_top5_accuracy", 0))
            self.history["val_f1_weighted"].append(val_metrics.get("fault_f1_weighted", 0))
            self.history["lr"].append(lr)

            elapsed = time.time() - t0
            top1 = val_metrics.get("fault_top1_accuracy", 0)
            top5 = val_metrics.get("fault_top5_accuracy", 0)
            f1 = val_metrics.get("fault_f1_weighted", 0)

            logger.info(
                f"Epoch {epoch + 1}/{max_epochs} "
                f"| Train Loss: {train_metrics['loss']:.4f} "
                f"| Train Acc: {train_metrics['accuracy']:.4f} "
                f"| Val Top-1: {top1:.4f} "
                f"| Val Top-5: {top5:.4f} "
                f"| Val F1: {f1:.4f} "
                f"| LR: {lr:.6f} "
                f"| {elapsed:.1f}s"
            )

            # Checkpointing
            if top1 > self.best_val_acc:
                self.best_val_acc = top1
                self.epochs_without_improvement = 0
                self.save_checkpoint(
                    os.path.join(checkpoint_dir, "fault_classifier_best.pt"),
                    epoch, val_metrics,
                )
                logger.info(f"  ✓ New best (Top-1={top1:.4f}, Top-5={top5:.4f})")
            else:
                self.epochs_without_improvement += 1
                if self.epochs_without_improvement >= patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

        # Load best
        best_path = os.path.join(checkpoint_dir, "fault_classifier_best.pt")
        if os.path.exists(best_path):
            self.load_checkpoint(best_path)

        return self.history

    def save_checkpoint(self, path: str, epoch: int, metrics: dict):
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_acc": self.best_val_acc,
            "metrics": metrics,
            "config": self.config,
        }, path)

    def load_checkpoint(self, path: str):
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded fault classifier from {path}")
