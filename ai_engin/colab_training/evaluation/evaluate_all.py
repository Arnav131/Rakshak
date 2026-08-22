"""
Rakshak AI Engine — Full Evaluation Suite
============================================
Runs comprehensive evaluation on all trained models
and generates a detailed report.
"""

import os
import logging
import json
import numpy as np
import torch
from typing import Dict, Optional

from config import (
    CHECKPOINT_DIR, EXPORT_DIR,
    VAE_CONFIG, FAILURE_CONFIG, FAULT_CONFIG,
    FAULT_CLASSES, RAW_SENSOR_COLUMNS,
)
from models.vae_anomaly import VAEAnomalyDetector
from models.failure_predictor import FailurePredictionModel
from models.fault_classifier import FaultClassifier
from models.isolation_forest import RakshakIsolationForest, extract_window_features
from models.meta_classifier import (
    MetaClassifier,
    StatisticalAnomalyDetector,
    build_meta_features,
)
from training.metrics import (
    compute_binary_metrics,
    compute_multiclass_metrics,
    compute_failure_metrics,
    check_targets_against_readme,
    get_classification_report,
    get_confusion_matrix,
    find_optimal_threshold,
)

logger = logging.getLogger(__name__)


def evaluate_vae(
    model: VAEAnomalyDetector,
    test_loader,
    device: str = "cuda",
) -> Dict[str, float]:
    """Evaluate VAE anomaly detector on test set."""
    model = model.to(device).eval()
    all_scores = []
    all_labels = []

    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            scores = model.compute_anomaly_score(x)
            all_scores.append(scores.cpu().numpy())
            all_labels.append(y.numpy())

    scores = np.concatenate(all_scores)
    labels = np.concatenate(all_labels)

    # Normalize
    s_min, s_max = scores.min(), scores.max()
    if s_max > s_min:
        scores = (scores - s_min) / (s_max - s_min)

    # Find optimal threshold
    opt_thresh, opt_f1 = find_optimal_threshold(labels, scores)

    metrics = compute_binary_metrics(labels, scores, threshold=opt_thresh, prefix="vae_")
    metrics["vae_optimal_threshold"] = opt_thresh

    logger.info(f"VAE Evaluation — AUROC: {metrics['vae_auroc']:.4f}, "
                 f"F1: {metrics['vae_f1']:.4f}, FPR: {metrics['vae_fpr']:.4f}")

    return metrics


def evaluate_failure_predictor(
    model: FailurePredictionModel,
    test_loader,
    device: str = "cuda",
) -> Dict[str, float]:
    """Evaluate failure prediction model on test set."""
    model = model.to(device).eval()

    all_preds = {h: [] for h in model.horizons}
    all_labels = {h: [] for h in model.horizons}

    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            preds = model(x)

            for i, h in enumerate(sorted(model.horizons)):
                all_preds[h].append(preds[h].cpu().numpy())
                all_labels[h].append(y[:, i].numpy())

    predictions = {h: np.concatenate(all_preds[h]) for h in model.horizons}
    targets = {h: np.concatenate(all_labels[h]) for h in model.horizons}

    metrics = compute_failure_metrics(predictions, targets)

    for h in model.horizons:
        auroc = metrics.get(f"failure_{h}_auroc", 0)
        f1 = metrics.get(f"failure_{h}_f1", 0)
        logger.info(f"Failure Prediction {h} — AUROC: {auroc:.4f}, F1: {f1:.4f}")

    return metrics


def evaluate_fault_classifier(
    model: FaultClassifier,
    test_loader,
    class_names=None,
    device: str = "cuda",
) -> Dict:
    """Evaluate fault classifier on test set."""
    if class_names is None:
        class_names = sorted(FAULT_CLASSES)

    model = model.to(device).eval()

    all_probs = []
    all_labels = []

    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            logits = model(x)
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            all_probs.append(probs)
            all_labels.append(y.numpy())

    probs = np.concatenate(all_probs)
    labels = np.concatenate(all_labels)

    metrics = compute_multiclass_metrics(labels, probs, class_names, prefix="fault_")

    # Generate classification report
    y_pred = np.argmax(probs, axis=1)
    report = get_classification_report(labels, y_pred, class_names)
    cm = get_confusion_matrix(labels, y_pred, num_classes=len(class_names))

    logger.info(f"Fault Classifier — Top-1: {metrics.get('fault_top1_accuracy', 0):.4f}, "
                 f"Top-5: {metrics.get('fault_top5_accuracy', 0):.4f}")
    logger.info(f"\nClassification Report:\n{report}")

    return {
        "metrics": metrics,
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
    }


def evaluate_ensemble(
    stat_detector: StatisticalAnomalyDetector,
    iso_forest: RakshakIsolationForest,
    meta_classifier: MetaClassifier,
    vae_model: VAEAnomalyDetector,
    test_windows: np.ndarray,
    test_labels: np.ndarray,
    device: str = "cuda",
) -> Dict[str, float]:
    """Evaluate the full 3-tier ensemble on test set."""
    # Extract features
    window_features = extract_window_features(test_windows)

    # Tier 1
    t1_zscore, t1_iqr = stat_detector.predict_scores(window_features)

    # Tier 2
    t2_scores = iso_forest.predict_scores(window_features)

    # Tier 3
    vae_model = vae_model.to(device).eval()
    t3_scores = []
    for i in range(0, len(test_windows), 512):
        batch = torch.from_numpy(test_windows[i:i+512]).float().to(device)
        scores = vae_model.compute_anomaly_score(batch)
        t3_scores.append(scores.cpu().numpy())
    t3_scores = np.concatenate(t3_scores)
    s_min, s_max = t3_scores.min(), t3_scores.max()
    if s_max > s_min:
        t3_scores = (t3_scores - s_min) / (s_max - s_min)

    # Meta
    meta_features = build_meta_features(
        t1_zscore, t1_iqr, t2_scores, t3_scores,
        raw_features=window_features[:, :len(RAW_SENSOR_COLUMNS)],
    )
    meta_probs = meta_classifier.predict_proba(meta_features)

    metrics = compute_binary_metrics(test_labels, meta_probs, prefix="ensemble_")

    # Also evaluate each tier independently
    t2_metrics = compute_binary_metrics(test_labels, t2_scores, prefix="tier2_")
    t3_metrics = compute_binary_metrics(test_labels, t3_scores.astype(np.float32), prefix="tier3_")

    metrics.update(t2_metrics)
    metrics.update(t3_metrics)

    return metrics


def run_full_evaluation(
    checkpoint_dir: str = CHECKPOINT_DIR,
    test_loaders: Dict = None,
    test_windows: np.ndarray = None,
    test_labels: np.ndarray = None,
    device: str = "cuda",
) -> Dict:
    """
    Run complete evaluation suite on all models.

    Returns comprehensive results dict with per-model metrics,
    README target comparison, and summary statistics.
    """
    device = device if torch.cuda.is_available() else "cpu"
    results = {}

    logger.info("=" * 60)
    logger.info("RAKSHAK AI ENGINE — FULL EVALUATION SUITE")
    logger.info("=" * 60)

    # Collect all metrics for target comparison
    all_metrics = {}

    # 1. VAE
    if test_loaders and "vae" in test_loaders:
        logger.info("\n[1/4] Evaluating VAE Anomaly Detector...")
        vae = VAEAnomalyDetector(VAE_CONFIG)
        ckpt = torch.load(os.path.join(checkpoint_dir, "vae_best.pt"), map_location=device)
        vae.load_state_dict(ckpt["model_state_dict"])
        vae_metrics = evaluate_vae(vae, test_loaders["vae"], device)
        results["vae"] = vae_metrics
        all_metrics.update(vae_metrics)

    # 2. Failure Predictor
    if test_loaders and "failure" in test_loaders:
        logger.info("\n[2/4] Evaluating Failure Predictor...")
        fp = FailurePredictionModel(FAILURE_CONFIG)
        ckpt = torch.load(os.path.join(checkpoint_dir, "failure_predictor_best.pt"), map_location=device)
        fp.load_state_dict(ckpt["model_state_dict"])
        fp_metrics = evaluate_failure_predictor(fp, test_loaders["failure"], device)
        results["failure_predictor"] = fp_metrics
        all_metrics.update(fp_metrics)

    # 3. Fault Classifier
    if test_loaders and "classifier" in test_loaders:
        logger.info("\n[3/4] Evaluating Fault Classifier...")
        fc = FaultClassifier(FAULT_CONFIG)
        ckpt = torch.load(os.path.join(checkpoint_dir, "fault_classifier_best.pt"), map_location=device)
        fc.load_state_dict(ckpt["model_state_dict"])
        fc_result = evaluate_fault_classifier(fc, test_loaders["classifier"], device=device)
        results["fault_classifier"] = fc_result
        all_metrics.update(fc_result["metrics"])

    # 4. Ensemble
    if test_windows is not None and test_labels is not None:
        logger.info("\n[4/4] Evaluating 3-Tier Ensemble...")
        stat = StatisticalAnomalyDetector()
        stat.load(os.path.join(checkpoint_dir, "stat_detector.joblib"))
        iso = RakshakIsolationForest()
        iso.load(os.path.join(checkpoint_dir, "isolation_forest.joblib"))
        meta = MetaClassifier()
        meta.load(os.path.join(checkpoint_dir, "meta_classifier.joblib"))

        vae = VAEAnomalyDetector(VAE_CONFIG)
        ckpt = torch.load(os.path.join(checkpoint_dir, "vae_best.pt"), map_location=device)
        vae.load_state_dict(ckpt["model_state_dict"])

        ensemble_metrics = evaluate_ensemble(
            stat, iso, meta, vae, test_windows, test_labels, device
        )
        results["ensemble"] = ensemble_metrics
        all_metrics.update(ensemble_metrics)

    # Compare against README targets
    logger.info("\n" + "=" * 60)
    logger.info("TARGET COMPARISON (vs agents_README)")
    logger.info("=" * 60)
    target_results = check_targets_against_readme(all_metrics)
    for name, info in target_results.items():
        logger.info(f"  {name}: {info['status']} "
                     f"(target={info['target']}, actual={info['actual']}, "
                     f"margin={info.get('margin', 'N/A')})")
    results["target_comparison"] = target_results

    return results
