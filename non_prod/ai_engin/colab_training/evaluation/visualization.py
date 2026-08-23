"""
Rakshak AI Engine — Visualization
====================================
Plots for training history, ROC curves, confusion matrices, etc.
Designed to work in Google Colab with matplotlib inline.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from typing import Dict, List, Optional
from sklearn.metrics import roc_curve, precision_recall_curve, confusion_matrix

matplotlib.rcParams.update({
    "figure.figsize": (12, 6),
    "figure.dpi": 100,
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
})

# Rakshak color palette
COLORS = {
    "primary": "#2563EB",
    "secondary": "#7C3AED",
    "success": "#059669",
    "danger": "#DC2626",
    "warning": "#D97706",
    "info": "#0891B2",
    "dark": "#1F2937",
    "light": "#F3F4F6",
}


def plot_training_history(history: Dict[str, list], title: str = "Training History"):
    """Plot training and validation loss curves."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Loss
    axes[0].plot(history["train_loss"], label="Train", color=COLORS["primary"], linewidth=2)
    axes[0].plot(history["val_loss"], label="Validation", color=COLORS["danger"], linewidth=2)
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_title(f"{title} — Loss")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # LR
    if "lr" in history:
        axes[1].plot(history["lr"], color=COLORS["secondary"], linewidth=2)
        axes[1].set_xlabel("Epoch")
        axes[1].set_ylabel("Learning Rate")
        axes[1].set_title("Learning Rate Schedule")
        axes[1].grid(True, alpha=0.3)
        axes[1].set_yscale("log")

    plt.tight_layout()
    plt.show()


def plot_vae_history(history: Dict[str, list]):
    """Plot VAE-specific training curves."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    axes[0].plot(history["train_loss"], label="Train", color=COLORS["primary"], linewidth=2)
    axes[0].plot(history["val_loss"], label="Val", color=COLORS["danger"], linewidth=2)
    axes[0].set_title("Total Loss (Recon + β·KL)")
    axes[0].set_xlabel("Epoch")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(history["recon_loss"], label="Recon Loss", color=COLORS["success"], linewidth=2)
    axes[1].set_title("Reconstruction Loss")
    axes[1].set_xlabel("Epoch")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(history["kl_loss"], label="KL Loss", color=COLORS["warning"], linewidth=2)
    axes[2].set_title("KL Divergence")
    axes[2].set_xlabel("Epoch")
    axes[2].grid(True, alpha=0.3)

    plt.suptitle("VAE Training History", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.show()


def plot_roc_curves(
    results: Dict[str, Dict],
    title: str = "ROC Curves",
):
    """
    Plot ROC curves for multiple models/horizons.

    results: {name: {y_true: array, y_pred_proba: array}}
    """
    fig, ax = plt.subplots(figsize=(8, 8))
    colors = list(COLORS.values())

    for i, (name, data) in enumerate(results.items()):
        fpr, tpr, _ = roc_curve(data["y_true"], data["y_pred_proba"])
        from sklearn.metrics import auc
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, color=colors[i % len(colors)],
                linewidth=2, label=f"{name} (AUC={roc_auc:.4f})")

    ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1.05])

    plt.tight_layout()
    plt.show()


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: List[str],
    title: str = "Confusion Matrix",
    normalize: bool = True,
):
    """Plot confusion matrix heatmap."""
    if normalize:
        cm_norm = cm.astype(float) / (cm.sum(axis=1, keepdims=True) + 1e-8)
    else:
        cm_norm = cm.astype(float)

    fig, ax = plt.subplots(figsize=(max(10, len(class_names) * 0.6),
                                      max(8, len(class_names) * 0.5)))

    im = ax.imshow(cm_norm, cmap="Blues", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(class_names, fontsize=8)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)

    plt.colorbar(im, ax=ax, shrink=0.8)
    plt.tight_layout()
    plt.show()


def plot_failure_prediction_horizons(history: Dict[str, list]):
    """Plot per-horizon AUROC over training epochs."""
    fig, ax = plt.subplots(figsize=(10, 6))
    horizon_colors = {"1h": COLORS["danger"], "6h": COLORS["warning"], "24h": COLORS["primary"]}

    for h in ["1h", "6h", "24h"]:
        key = f"val_auroc_{h}"
        if key in history:
            ax.plot(history[key], label=f"{h} Horizon",
                    color=horizon_colors.get(h, COLORS["info"]), linewidth=2)

    ax.axhline(y=0.95, color=COLORS["success"], linestyle="--", alpha=0.7,
               label="Target AUROC (0.95)")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("AUROC")
    ax.set_title("Failure Prediction — Per-Horizon AUROC")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0.5, 1.02])

    plt.tight_layout()
    plt.show()


def plot_anomaly_score_distribution(
    normal_scores: np.ndarray,
    anomaly_scores: np.ndarray,
    threshold: Optional[float] = None,
    title: str = "Anomaly Score Distribution",
):
    """Plot score distributions for normal vs anomalous samples."""
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(normal_scores, bins=100, alpha=0.6, color=COLORS["success"],
            label="Normal", density=True)
    ax.hist(anomaly_scores, bins=100, alpha=0.6, color=COLORS["danger"],
            label="Anomaly", density=True)

    if threshold is not None:
        ax.axvline(x=threshold, color=COLORS["dark"], linestyle="--",
                   linewidth=2, label=f"Threshold ({threshold:.3f})")

    ax.set_xlabel("Anomaly Score")
    ax.set_ylabel("Density")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def plot_summary_dashboard(all_metrics: Dict[str, float]):
    """Plot a summary dashboard of all model performance metrics."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("🛡️ Rakshak AI Engine — Performance Dashboard",
                 fontsize=18, fontweight="bold", y=1.02)

    # 1. Anomaly Detection
    ax = axes[0, 0]
    metrics_names = ["AUROC", "F1", "Precision", "Recall"]
    vae_vals = [all_metrics.get(f"vae_{m.lower()}", 0) for m in ["auroc", "f1", "precision", "recall"]]
    ens_vals = [all_metrics.get(f"ensemble_{m.lower()}", 0) for m in ["auroc", "f1", "precision", "recall"]]
    x = np.arange(len(metrics_names))
    w = 0.35
    ax.bar(x - w/2, vae_vals, w, label="VAE (Tier 3)", color=COLORS["primary"])
    ax.bar(x + w/2, ens_vals, w, label="Ensemble", color=COLORS["success"])
    ax.set_xticks(x)
    ax.set_xticklabels(metrics_names)
    ax.set_title("Anomaly Detection")
    ax.set_ylim([0, 1.1])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # 2. Failure Prediction AUROC by horizon
    ax = axes[0, 1]
    horizons = ["1h", "6h", "24h"]
    aurocs = [all_metrics.get(f"failure_{h}_auroc", 0) for h in horizons]
    bars = ax.bar(horizons, aurocs, color=[COLORS["danger"], COLORS["warning"], COLORS["primary"]])
    ax.axhline(y=0.95, color=COLORS["success"], linestyle="--", label="Target (0.95)")
    ax.set_title("Failure Prediction AUROC")
    ax.set_ylim([0, 1.1])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    for bar, val in zip(bars, aurocs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{val:.3f}", ha="center", fontweight="bold")

    # 3. Fault Classification
    ax = axes[1, 0]
    cls_metrics = ["Top-1 Acc", "Top-5 Acc", "F1 (weighted)"]
    cls_vals = [
        all_metrics.get("fault_top1_accuracy", 0),
        all_metrics.get("fault_top5_accuracy", 0),
        all_metrics.get("fault_f1_weighted", 0),
    ]
    targets = [0.85, 0.97, 0.85]
    x = np.arange(len(cls_metrics))
    ax.bar(x, cls_vals, 0.4, label="Achieved", color=COLORS["secondary"])
    ax.scatter(x, targets, color=COLORS["danger"], s=100, zorder=5,
               marker="D", label="Target")
    ax.set_xticks(x)
    ax.set_xticklabels(cls_metrics)
    ax.set_title("Fault Classification")
    ax.set_ylim([0, 1.1])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # 4. False Positive Rate
    ax = axes[1, 1]
    fpr_metrics = ["VAE FPR", "Ensemble FPR"]
    fpr_vals = [
        all_metrics.get("vae_fpr", 0),
        all_metrics.get("ensemble_fpr", 0),
    ]
    colors_fpr = [COLORS["warning"] if v > 0.04 else COLORS["success"] for v in fpr_vals]
    ax.bar(fpr_metrics, fpr_vals, color=colors_fpr)
    ax.axhline(y=0.04, color=COLORS["danger"], linestyle="--", label="Target (< 4%)")
    ax.set_title("False Positive Rate")
    ax.set_ylim([0, max(0.1, max(fpr_vals) * 1.3)])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.show()
