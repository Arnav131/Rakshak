"""
Rakshak AI Engine — Fault Classification Inference
=====================================================
Identifies the specific fault type when an anomaly is detected.
"""

import numpy as np
import torch
import torch.nn.functional as F
import logging
from typing import Optional, List, Dict

from ai_engin.inference.utils import FaultClassification

logger = logging.getLogger(__name__)


class FaultClassifier:
    """
    Multi-class fault type classification inference.

    Only runs when an anomaly is detected (saves compute on
    normal readings). Produces top-K fault type predictions
    with confidence scores.
    """

    def __init__(self, registry, top_k: int = 5):
        self.registry = registry
        self.device = registry.device
        self.top_k = top_k
        self.fault_classes = registry.get_fault_classes()

    def classify(
        self,
        window: np.ndarray,
        anomaly_score: float = 0.0,
    ) -> FaultClassification:
        """
        Classify the fault type from a sensor window.

        Args:
            window: (W, 4) raw sensor window
            anomaly_score: Anomaly score from the detection pipeline
                          (appended as an extra feature)

        Returns:
            FaultClassification with top-K predictions
        """
        model = self.registry.get_fault_classifier()
        if model is None:
            return FaultClassification()

        # Prepare input: raw features + anomaly score
        W, C = window.shape
        anomaly_col = np.full((W, 1), anomaly_score, dtype=np.float32)
        features = np.concatenate([window, anomaly_col], axis=1)

        # Match expected feature count
        expected = model.config.num_features
        actual = features.shape[1]
        if actual < expected:
            pad = np.zeros((W, expected - actual), dtype=np.float32)
            features = np.concatenate([features, pad], axis=1)
        elif actual > expected:
            features = features[:, :expected]

        x = torch.from_numpy(features).float().unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = model(x)
            probs = F.softmax(logits, dim=1).cpu().numpy()[0]

        # Top-K
        k = min(self.top_k, len(probs))
        top_indices = np.argsort(probs)[-k:][::-1]

        top_k_results = []
        for idx in top_indices:
            class_name = self.fault_classes[idx] if idx < len(self.fault_classes) else f"class_{idx}"
            top_k_results.append({
                "class": class_name,
                "probability": float(probs[idx]),
            })

        best_idx = top_indices[0]
        best_class = self.fault_classes[best_idx] if best_idx < len(self.fault_classes) else "unknown"

        return FaultClassification(
            fault_type=best_class,
            confidence=float(probs[best_idx]),
            top_k=top_k_results,
        )
