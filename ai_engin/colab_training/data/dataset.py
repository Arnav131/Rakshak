"""
Rakshak AI Engine — PyTorch Datasets & DataLoaders
=====================================================
Custom PyTorch Dataset classes for each model type.
Supports in-memory and memory-mapped data sources.
"""

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from typing import Dict, List, Optional, Tuple, Union

from config import DATA_CONFIG, TRAINING_CONFIG


# ═══════════════════════════════════════════════════════════════════
# BASE DATASET
# ═══════════════════════════════════════════════════════════════════

class RakshakBaseDataset(Dataset):
    """
    Base Dataset for windowed sensor data.

    Stores pre-computed windows (N, W, F) and labels in memory.
    For datasets that fit in RAM after subsampling.
    """

    def __init__(
        self,
        windows: np.ndarray,
        labels: np.ndarray,
        transform=None,
    ):
        """
        Args:
            windows: Shape (N, W, F) — float32
            labels: Shape (N,) or (N, C) — labels
            transform: Optional transform applied to each sample
        """
        self.windows = torch.from_numpy(windows).float()
        self.labels = torch.from_numpy(labels)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.windows[idx]  # (W, F)
        y = self.labels[idx]

        if self.transform is not None:
            x = self.transform(x)

        return x, y


# ═══════════════════════════════════════════════════════════════════
# VAE DATASET
# ═══════════════════════════════════════════════════════════════════

class VAEDataset(RakshakBaseDataset):
    """
    Dataset for the VAE anomaly detector.

    For training: returns (window, window) — VAE reconstructs its input.
    For evaluation: returns (window, anomaly_label).
    """

    def __init__(
        self,
        windows: np.ndarray,
        labels: np.ndarray,
        is_training: bool = True,
        transform=None,
    ):
        super().__init__(windows, labels, transform)
        self.is_training = is_training

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.windows[idx]  # (W, F)

        if self.transform is not None:
            x = self.transform(x)

        if self.is_training:
            return x, x  # Autoencoder: target = input
        else:
            return x, self.labels[idx]


# ═══════════════════════════════════════════════════════════════════
# FAILURE PREDICTION DATASET
# ═══════════════════════════════════════════════════════════════════

class FailurePredictionDataset(Dataset):
    """
    Dataset for the multi-horizon failure predictor.

    Each sample has:
    - Input: window of features (W, F)
    - Labels: dict of {horizon_name: binary_label}
    """

    def __init__(
        self,
        windows: np.ndarray,
        horizon_labels: Dict[str, np.ndarray],
        transform=None,
    ):
        self.windows = torch.from_numpy(windows).float()
        self.horizon_labels = {
            name: torch.from_numpy(labels).float()
            for name, labels in horizon_labels.items()
        }
        self.horizon_names = sorted(horizon_labels.keys())
        self.transform = transform

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.windows[idx]

        if self.transform is not None:
            x = self.transform(x)

        # Stack horizon labels into a single tensor
        y = torch.stack([self.horizon_labels[h][idx] for h in self.horizon_names])

        return x, y


# ═══════════════════════════════════════════════════════════════════
# FAULT CLASSIFICATION DATASET
# ═══════════════════════════════════════════════════════════════════

class FaultClassificationDataset(RakshakBaseDataset):
    """
    Dataset for multi-class fault classification.
    Labels are integer class indices.
    """

    def __init__(
        self,
        windows: np.ndarray,
        labels: np.ndarray,
        transform=None,
    ):
        labels = labels.astype(np.int64)
        super().__init__(windows, labels, transform)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.windows[idx]
        y = self.labels[idx].long()

        if self.transform is not None:
            x = self.transform(x)

        return x, y


# ═══════════════════════════════════════════════════════════════════
# DATA AUGMENTATION TRANSFORMS
# ═══════════════════════════════════════════════════════════════════

class SensorAugmentation:
    """
    Data augmentation transforms for sensor time series.

    Applies random noise injection, time warping, and channel dropout
    to improve model generalization.
    """

    def __init__(
        self,
        noise_std: float = 0.05,
        time_mask_ratio: float = 0.1,
        channel_dropout_prob: float = 0.1,
    ):
        self.noise_std = noise_std
        self.time_mask_ratio = time_mask_ratio
        self.channel_dropout_prob = channel_dropout_prob

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply augmentations to a single window (W, F).
        """
        # 1. Gaussian noise injection
        if self.noise_std > 0:
            noise = torch.randn_like(x) * self.noise_std
            x = x + noise

        # 2. Random time masking (zero out random timesteps)
        if self.time_mask_ratio > 0:
            W = x.shape[0]
            num_mask = int(W * self.time_mask_ratio)
            if num_mask > 0:
                mask_indices = torch.randperm(W)[:num_mask]
                x[mask_indices] = 0.0

        # 3. Channel dropout (zero out entire feature channels)
        if self.channel_dropout_prob > 0:
            F = x.shape[1]
            channel_mask = torch.bernoulli(
                torch.full((F,), 1 - self.channel_dropout_prob)
            )
            x = x * channel_mask.unsqueeze(0)

        return x


# ═══════════════════════════════════════════════════════════════════
# DATALOADER FACTORY
# ═══════════════════════════════════════════════════════════════════

def create_weighted_sampler(
    labels: np.ndarray,
    num_samples: Optional[int] = None,
) -> WeightedRandomSampler:
    """
    Create a WeightedRandomSampler for class-balanced training.

    Upsamples minority class, downsamples majority class so each
    batch sees roughly equal representation.
    """
    unique, counts = np.unique(labels, return_counts=True)
    class_weights = {int(c): 1.0 / cnt for c, cnt in zip(unique, counts)}
    sample_weights = np.array([class_weights[int(l)] for l in labels])
    sample_weights = torch.from_numpy(sample_weights).double()

    if num_samples is None:
        num_samples = len(labels)

    return WeightedRandomSampler(
        weights=sample_weights,
        num_samples=num_samples,
        replacement=True,
    )


def create_dataloaders(
    train_dataset: Dataset,
    val_dataset: Dataset,
    test_dataset: Optional[Dataset] = None,
    batch_size: int = 256,
    balance_train: bool = True,
    train_labels: Optional[np.ndarray] = None,
    num_workers: int = 2,
    pin_memory: bool = True,
) -> Dict[str, DataLoader]:
    """
    Create DataLoaders for train/val/test splits.

    Args:
        train_dataset: Training dataset
        val_dataset: Validation dataset
        test_dataset: Optional test dataset
        batch_size: Batch size
        balance_train: Whether to use weighted sampling for training
        train_labels: Labels for weighted sampling (required if balance_train)
        num_workers: Number of data loading workers
        pin_memory: Pin memory for GPU transfer

    Returns:
        Dict with 'train', 'val', and optionally 'test' DataLoaders
    """
    train_sampler = None
    train_shuffle = True

    if balance_train and train_labels is not None:
        train_sampler = create_weighted_sampler(train_labels)
        train_shuffle = False  # Sampler handles this

    loaders = {
        "train": DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=train_shuffle,
            sampler=train_sampler,
            num_workers=num_workers,
            pin_memory=pin_memory,
            drop_last=True,
        ),
        "val": DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=pin_memory,
        ),
    }

    if test_dataset is not None:
        loaders["test"] = DataLoader(
            test_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=pin_memory,
        )

    return loaders
