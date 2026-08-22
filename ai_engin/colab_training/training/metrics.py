"""
Rakshak AI Engine — Evaluation Metrics
=========================================
Comprehensive metrics for all model types.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
    confusion_matrix,
    classification_report,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_curve,
)


# ═══════════════════════════════════════════════════════════════════
# BINARY CLASSIFICATION METRICS (Anomaly Detection + Failure Pred)
# ═══════════════════════════════════════════════════════════════════

def compute_binary_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.5,
    prefix: str = "",
) -> Dict[str, float]:
    """
    Comprehensive binary classification metrics.

    Args:
        y_true: Ground truth binary labels
        y_pred_proba: Predicted probabilities
        threshold: Decision threshold
        prefix: Metric name prefix (e.g., 'vae_', 'failure_1h_')

    Returns:
        Dict of metric_name → value
    """
    y_pred = (y_pred_proba >= threshold).astype(np.int32)

    metrics = {}
    p = prefix

    # Discrimination metrics
    try:
        metrics[f"{p}auroc"] = roc_auc_score(y_true, y_pred_proba)
    except ValueError:
        metrics[f"{p}auroc"] = 0.0

    try:
        metrics[f"{p}auprc"] = average_precision_score(y_true, y_pred_proba)
    except ValueError:
        metrics[f"{p}auprc"] = 0.0

    # Classification metrics at threshold
    metrics[f"{p}f1"] = f1_score(y_true, y_pred, zero_division=0)
    metrics[f"{p}precision"] = precision_score(y_true, y_pred, zero_division=0)
    metrics[f"{p}recall"] = recall_score(y_true, y_pred, zero_division=0)
    metrics[f"{p}accuracy"] = accuracy_score(y_true, y_pred)

    # False positive rate
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    metrics[f"{p}fpr"] = fp / (fp + tn + 1e-8)
    metrics[f"{p}fnr"] = fn / (fn + tp + 1e-8)

    # Calibration
    metrics[f"{p}brier_score"] = brier_score_loss(y_true, y_pred_proba)

    try:
        metrics[f"{p}log_loss"] = log_loss(y_true, y_pred_proba)
    except ValueError:
        metrics[f"{p}log_loss"] = float("inf")

    return metrics


def find_optimal_threshold(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    metric: str = "f1",
) -> Tuple[float, float]:
    """
    Find the optimal decision threshold maximizing a given metric.

    Returns:
        (best_threshold, best_metric_value)
    """
    thresholds = np.arange(0.01, 1.0, 0.01)
    best_thresh = 0.5
    best_score = 0.0

    for t in thresholds:
        y_pred = (y_pred_proba >= t).astype(np.int32)

        if metric == "f1":
            score = f1_score(y_true, y_pred, zero_division=0)
        elif metric == "precision":
            score = precision_score(y_true, y_pred, zero_division=0)
        elif metric == "recall":
            score = recall_score(y_true, y_pred, zero_division=0)
        else:
            score = f1_score(y_true, y_pred, zero_division=0)

        if score > best_score:
            best_score = score
            best_thresh = t

    return best_thresh, best_score


# ═══════════════════════════════════════════════════════════════════
# MULTI-CLASS METRICS (Fault Classification)
# ═══════════════════════════════════════════════════════════════════

def compute_multiclass_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    class_names: Optional[List[str]] = None,
    prefix: str = "",
) -> Dict[str, float]:
    """
    Multi-class classification metrics for fault classification.

    Args:
        y_true: Integer class labels
        y_pred_proba: (N, C) probability matrix
        class_names: List of class names
        prefix: Metric name prefix

    Returns:
        Dict of metrics
    """
    y_pred = np.argmax(y_pred_proba, axis=1)
    metrics = {}
    p = prefix

    # Overall accuracy
    metrics[f"{p}accuracy"] = accuracy_score(y_true, y_pred)

    # Top-K accuracy
    for k in [1, 3, 5]:
        if y_pred_proba.shape[1] >= k:
            top_k = np.argsort(y_pred_proba, axis=1)[:, -k:]
            top_k_correct = np.array([y_true[i] in top_k[i] for i in range(len(y_true))])
            metrics[f"{p}top{k}_accuracy"] = top_k_correct.mean()

    # Weighted F1, Precision, Recall
    metrics[f"{p}f1_weighted"] = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    metrics[f"{p}f1_macro"] = f1_score(y_true, y_pred, average="macro", zero_division=0)
    metrics[f"{p}precision_weighted"] = precision_score(y_true, y_pred, average="weighted", zero_division=0)
    metrics[f"{p}recall_weighted"] = recall_score(y_true, y_pred, average="weighted", zero_division=0)

    # Multi-class AUROC (one-vs-rest)
    try:
        metrics[f"{p}auroc_ovr"] = roc_auc_score(
            y_true, y_pred_proba, multi_class="ovr", average="weighted"
        )
    except ValueError:
        metrics[f"{p}auroc_ovr"] = 0.0

    return metrics


def get_classification_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: Optional[List[str]] = None,
) -> str:
    """Get a formatted classification report string."""
    return classification_report(
        y_true, y_pred,
        target_names=class_names,
        zero_division=0,
    )


def get_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    num_classes: int = None,
) -> np.ndarray:
    """Get confusion matrix."""
    labels = list(range(num_classes)) if num_classes else None
    return confusion_matrix(y_true, y_pred, labels=labels)


# ═══════════════════════════════════════════════════════════════════
# FAILURE PREDICTION SPECIFIC METRICS
# ═══════════════════════════════════════════════════════════════════

def compute_failure_metrics(
    predictions: Dict[str, np.ndarray],
    targets: Dict[str, np.ndarray],
) -> Dict[str, float]:
    """
    Compute metrics for multi-horizon failure prediction.

    Args:
        predictions: {horizon: (N,) probabilities}
        targets: {horizon: (N,) binary labels}

    Returns:
        Dict of metrics for each horizon
    """
    metrics = {}
    for horizon in predictions:
        h_metrics = compute_binary_metrics(
            targets[horizon],
            predictions[horizon],
            prefix=f"failure_{horizon}_",
        )
        metrics.update(h_metrics)

    return metrics


# ═══════════════════════════════════════════════════════════════════
# TARGET QUALITY CHECK
# ═══════════════════════════════════════════════════════════════════

def check_targets_against_readme(metrics: Dict[str, float]) -> Dict[str, Dict]:
    """
    Compare achieved metrics against agents_README quality targets.

    Returns status for each target: PASS/FAIL with margin.
    """
    targets = {
        "Anomaly Detection F1": {"metric_key": "vae_f1", "target": 0.96, "direction": ">="},
        "Anomaly Detection FPR": {"metric_key": "vae_fpr", "target": 0.04, "direction": "<="},
        "Failure Prediction AUROC": {"metric_key": "failure_24h_auroc", "target": 0.95, "direction": ">="},
        "Fault Classification Top-1": {"metric_key": "fault_top1_accuracy", "target": 0.85, "direction": ">="},
        "Fault Classification Top-5": {"metric_key": "fault_top5_accuracy", "target": 0.97, "direction": ">="},
    }

    results = {}
    for name, info in targets.items():
        actual = metrics.get(info["metric_key"], None)
        if actual is None:
            results[name] = {"status": "MISSING", "target": info["target"], "actual": None}
            continue

        if info["direction"] == ">=":
            passed = actual >= info["target"]
        else:
            passed = actual <= info["target"]

        results[name] = {
            "status": "PASS ✅" if passed else "FAIL ❌",
            "target": info["target"],
            "actual": round(actual, 4),
            "margin": round(actual - info["target"], 4) if info["direction"] == ">=" else round(info["target"] - actual, 4),
        }

    return results
