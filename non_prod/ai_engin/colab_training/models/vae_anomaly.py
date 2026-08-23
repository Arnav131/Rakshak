"""
Rakshak AI Engine — Variational Autoencoder for Anomaly Detection
===================================================================
Tier-3 deep reconstruction model. Learns the distribution of normal
sensor behavior; anomalies produce high reconstruction error.

Architecture (from agents_README):
    Conv1D(64) → Conv1D(128) → Latent(32)
    → Deconv1D(128) → Deconv1D(64) → Reconstruction error
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict

from config import VAE_CONFIG


class ConvEncoder(nn.Module):
    """
    1D Convolutional Encoder.

    Maps input (B, W, C) → latent parameters (mu, log_var) of shape (B, latent_dim).
    """

    def __init__(
        self,
        input_channels: int = VAE_CONFIG.input_channels,
        channels: list = None,
        kernel_sizes: list = None,
        latent_dim: int = VAE_CONFIG.latent_dim,
    ):
        super().__init__()
        if channels is None:
            channels = VAE_CONFIG.encoder_channels
        if kernel_sizes is None:
            kernel_sizes = VAE_CONFIG.encoder_kernel_sizes

        layers = []
        in_ch = input_channels
        for out_ch, ks in zip(channels, kernel_sizes):
            layers.extend([
                nn.Conv1d(in_ch, out_ch, kernel_size=ks, stride=2, padding=ks // 2),
                nn.BatchNorm1d(out_ch),
                nn.LeakyReLU(0.2, inplace=True),
            ])
            in_ch = out_ch

        self.conv_layers = nn.Sequential(*layers)

        # Compute flattened size after convolutions
        self._flat_size = None
        self._last_conv_channels = channels[-1]

        # Latent space projections
        self.fc_mu = None
        self.fc_log_var = None
        self.latent_dim = latent_dim

    def _init_fc_layers(self, flat_size: int):
        """Initialize FC layers after first forward pass determines sizes."""
        device = next(self.conv_layers.parameters()).device
        self.fc_mu = nn.Linear(flat_size, self.latent_dim).to(device)
        self.fc_log_var = nn.Linear(flat_size, self.latent_dim).to(device)
        self._flat_size = flat_size

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (B, W, C) — batch × window × channels

        Returns:
            mu: (B, latent_dim)
            log_var: (B, latent_dim)
        """
        # Conv1d expects (B, C, W)
        x = x.permute(0, 2, 1)
        h = self.conv_layers(x)  # (B, last_ch, W')
        h = h.flatten(1)  # (B, last_ch * W')

        if self.fc_mu is None:
            self._init_fc_layers(h.shape[1])

        mu = self.fc_mu(h)
        log_var = self.fc_log_var(h)

        return mu, log_var


class ConvDecoder(nn.Module):
    """
    1D Convolutional Decoder (mirrors encoder).

    Maps latent (B, latent_dim) → reconstructed (B, W, C).
    """

    def __init__(
        self,
        output_channels: int = VAE_CONFIG.input_channels,
        channels: list = None,
        kernel_sizes: list = None,
        latent_dim: int = VAE_CONFIG.latent_dim,
        target_length: int = VAE_CONFIG.sequence_length,
    ):
        super().__init__()
        if channels is None:
            channels = list(reversed(VAE_CONFIG.encoder_channels))
        if kernel_sizes is None:
            kernel_sizes = list(reversed(VAE_CONFIG.encoder_kernel_sizes))

        self.target_length = target_length
        self.initial_channels = channels[0]

        # Calculate the spatial size after encoding
        conv_length = target_length
        num_convs = len(VAE_CONFIG.encoder_channels)
        for _ in range(num_convs):
            conv_length = (conv_length + 1) // 2  # stride=2

        self.initial_length = conv_length
        self.fc = nn.Linear(latent_dim, channels[0] * conv_length)

        layers = []
        in_ch = channels[0]
        for i, (out_ch, ks) in enumerate(zip(channels[1:] + [output_channels], kernel_sizes)):
            is_last = (i == len(kernel_sizes) - 1)
            layers.append(
                nn.ConvTranspose1d(
                    in_ch, out_ch,
                    kernel_size=ks, stride=2,
                    padding=ks // 2,
                    output_padding=1,
                )
            )
            if not is_last:
                layers.append(nn.BatchNorm1d(out_ch))
                layers.append(nn.LeakyReLU(0.2, inplace=True))
            in_ch = out_ch

        self.deconv_layers = nn.Sequential(*layers)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """
        Args:
            z: (B, latent_dim)

        Returns:
            x_recon: (B, W, C) — reconstructed input
        """
        h = self.fc(z)
        h = h.view(-1, self.initial_channels, self.initial_length)
        h = self.deconv_layers(h)  # (B, C, W')

        # Trim or pad to exact target length
        if h.shape[2] > self.target_length:
            h = h[:, :, :self.target_length]
        elif h.shape[2] < self.target_length:
            pad = self.target_length - h.shape[2]
            h = F.pad(h, (0, pad))

        # Back to (B, W, C)
        return h.permute(0, 2, 1)


class VAEAnomalyDetector(nn.Module):
    """
    Full Variational Autoencoder for sensor anomaly detection.

    Training: Minimize ELBO = Reconstruction Loss + β * KL Divergence
    Inference: Anomaly score = reconstruction error (MSE per window)
    """

    def __init__(self, config=VAE_CONFIG):
        super().__init__()
        self.config = config
        self.encoder = ConvEncoder(
            input_channels=config.input_channels,
            channels=config.encoder_channels,
            kernel_sizes=config.encoder_kernel_sizes,
            latent_dim=config.latent_dim,
        )
        self.decoder = ConvDecoder(
            output_channels=config.input_channels,
            latent_dim=config.latent_dim,
            target_length=config.sequence_length,
        )

    def reparameterize(self, mu: torch.Tensor, log_var: torch.Tensor) -> torch.Tensor:
        """Reparameterization trick: z = mu + sigma * epsilon."""
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Full forward pass.

        Args:
            x: (B, W, C) input windows

        Returns:
            dict with keys: x_recon, mu, log_var, z
        """
        mu, log_var = self.encoder(x)
        z = self.reparameterize(mu, log_var)
        x_recon = self.decoder(z)

        return {
            "x_recon": x_recon,
            "mu": mu,
            "log_var": log_var,
            "z": z,
        }

    def compute_anomaly_score(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute per-sample anomaly score based on reconstruction error.

        Higher score = more anomalous.

        Args:
            x: (B, W, C) input windows

        Returns:
            scores: (B,) reconstruction error per sample
        """
        with torch.no_grad():
            output = self.forward(x)
            # MSE per sample (averaged over time and channels)
            recon_error = F.mse_loss(
                output["x_recon"], x, reduction="none"
            ).mean(dim=(1, 2))  # (B,)

            return recon_error

    def get_latent(self, x: torch.Tensor) -> torch.Tensor:
        """Get latent representations for downstream use."""
        with torch.no_grad():
            mu, _ = self.encoder(x)
            return mu


def build_vae_model(config=VAE_CONFIG) -> VAEAnomalyDetector:
    """Factory function to create the VAE model."""
    model = VAEAnomalyDetector(config)
    # Initialize weights
    for m in model.modules():
        if isinstance(m, (nn.Conv1d, nn.ConvTranspose1d)):
            nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="leaky_relu")
        elif isinstance(m, nn.BatchNorm1d):
            nn.init.constant_(m.weight, 1)
            nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.Linear):
            nn.init.xavier_normal_(m.weight)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
    return model
