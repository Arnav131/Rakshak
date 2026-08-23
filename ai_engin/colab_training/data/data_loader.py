"""
Rakshak AI Engine — Memory-Efficient Parquet Data Loader
=========================================================
Streams parquet files from a ZIP archive without extracting
the entire 3GB dataset at once. Designed for Google Colab
with limited RAM (12-25 GB).
"""

import io
import os
import re
import zipfile
import logging
from typing import List, Optional, Tuple, Generator, Dict

import numpy as np
import pandas as pd

from config import (
    DATASET_ZIP_PATH,
    EXTRACTED_DATA_DIR,
    RAW_SENSOR_COLUMNS,
    TIMESTAMP_COL,
    SCENARIO_COL,
    LABEL_COL,
    FAULT_TYPE_MAP,
    DATA_CONFIG,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# SCENARIO METADATA EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def parse_scenario_id(scenario_id: str) -> Dict[str, str]:
    """
    Parse a scenario_id like 'DP_SUM_BUCKLEPRECUR_045' into components.

    Returns:
        dict with keys: region, season, fault_keyword, scenario_num, fault_type
    """
    parts = scenario_id.split("_")
    region = parts[0]
    season = parts[1]

    # The fault keyword is everything between season and the numeric ID
    # e.g., "DP_SUM_BUCKLEPRECUR_045" → fault_keyword = "BUCKLEPRECUR"
    scenario_num = parts[-1]
    fault_keyword = "_".join(parts[2:-1])

    # Map to canonical fault type
    fault_type = FAULT_TYPE_MAP.get(fault_keyword, "unknown")

    return {
        "region": region,
        "season": season,
        "fault_keyword": fault_keyword,
        "scenario_num": scenario_num,
        "fault_type": fault_type,
    }


def get_fault_type_from_filename(filename: str) -> str:
    """
    Extract fault type from a parquet filename.

    Example: 'DP_SUM_BUCKLEPRECUR_045_chunk_16.parquet' → 'buckle_precursor'
    """
    # Remove chunk suffix and extension
    scenario_id = re.sub(r"_chunk_\d+\.parquet$", "", filename)
    meta = parse_scenario_id(scenario_id)
    return meta["fault_type"]


# ═══════════════════════════════════════════════════════════════════
# ZIP-BASED STREAMING LOADER
# ═══════════════════════════════════════════════════════════════════

class ParquetStreamLoader:
    """
    Streams parquet files from a ZIP archive in configurable chunks.

    This loader never extracts the full dataset to disk. It reads
    parquet files directly from the ZIP into memory one batch at a time.

    Usage:
        loader = ParquetStreamLoader(zip_path="path/to/dataset.zip")
        for batch_df in loader.stream(files_per_chunk=10):
            process(batch_df)
    """

    def __init__(self, zip_path: str = DATASET_ZIP_PATH):
        self.zip_path = zip_path
        self._file_list: Optional[List[str]] = None
        self._scenario_map: Optional[Dict[str, List[str]]] = None

    @property
    def file_list(self) -> List[str]:
        """Get sorted list of all parquet files in the ZIP."""
        if self._file_list is None:
            with zipfile.ZipFile(self.zip_path, "r") as z:
                self._file_list = sorted([
                    f for f in z.namelist()
                    if f.endswith(".parquet")
                ])
        return self._file_list

    @property
    def scenario_map(self) -> Dict[str, List[str]]:
        """Group filenames by scenario_id."""
        if self._scenario_map is None:
            self._scenario_map = {}
            for f in self.file_list:
                scenario = re.sub(r"_chunk_\d+\.parquet$", "", f)
                self._scenario_map.setdefault(scenario, []).append(f)
        return self._scenario_map

    @property
    def num_files(self) -> int:
        return len(self.file_list)

    @property
    def num_scenarios(self) -> int:
        return len(self.scenario_map)

    def read_single_file(
        self,
        filename: str,
        max_rows: Optional[int] = None,
    ) -> pd.DataFrame:
        """Read a single parquet file from the ZIP archive."""
        with zipfile.ZipFile(self.zip_path, "r") as z:
            with z.open(filename) as f:
                data = f.read()
        df = pd.read_parquet(io.BytesIO(data))

        if max_rows is not None and len(df) > max_rows:
            df = df.sample(n=max_rows, random_state=DATA_CONFIG.seed)
            df = df.sort_values(TIMESTAMP_COL).reset_index(drop=True)

        return df

    def stream(
        self,
        files_per_chunk: int = DATA_CONFIG.files_per_chunk,
        max_rows_per_file: Optional[int] = DATA_CONFIG.max_rows_per_file,
        file_list: Optional[List[str]] = None,
        add_fault_column: bool = True,
    ) -> Generator[pd.DataFrame, None, None]:
        """
        Yield DataFrames in chunks of `files_per_chunk` files.

        Each yielded DataFrame contains data from multiple parquet files
        concatenated together, with an additional 'fault_type' column.

        Args:
            files_per_chunk: Number of files to load per chunk
            max_rows_per_file: Max rows to sample per file (None = all)
            file_list: Specific files to stream (None = all files)
            add_fault_column: Whether to add 'fault_type' column

        Yields:
            pd.DataFrame with columns: timestamp, scenario_id, ambient_temp,
            humidity, vibration_rms, gauge_width, is_anomaly, fault_type
        """
        files = file_list or self.file_list
        total = len(files)

        for i in range(0, total, files_per_chunk):
            chunk_files = files[i:i + files_per_chunk]
            dfs = []

            for fname in chunk_files:
                try:
                    df = self.read_single_file(fname, max_rows=max_rows_per_file)

                    if add_fault_column:
                        fault_type = get_fault_type_from_filename(fname)
                        df["fault_type"] = fault_type

                    dfs.append(df)
                except Exception as e:
                    logger.warning(f"Failed to read {fname}: {e}")
                    continue

            if dfs:
                chunk_df = pd.concat(dfs, ignore_index=True)
                logger.info(
                    f"Loaded chunk {i // files_per_chunk + 1}: "
                    f"{len(chunk_files)} files, {len(chunk_df)} rows "
                    f"({i + len(chunk_files)}/{total} files processed)"
                )
                yield chunk_df

    def load_scenario(
        self,
        scenario_id: str,
        max_rows: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load all chunks for a specific scenario, concatenated."""
        files = self.scenario_map.get(scenario_id, [])
        if not files:
            raise ValueError(f"Scenario '{scenario_id}' not found in dataset.")

        dfs = []
        for fname in sorted(files):
            df = self.read_single_file(fname, max_rows=max_rows)
            dfs.append(df)

        result = pd.concat(dfs, ignore_index=True)
        result = result.sort_values(TIMESTAMP_COL).reset_index(drop=True)
        return result

    def get_scenario_summary(self) -> pd.DataFrame:
        """
        Return a summary DataFrame with one row per scenario,
        showing region, season, fault type, and chunk count.
        """
        rows = []
        for scenario_id, files in sorted(self.scenario_map.items()):
            meta = parse_scenario_id(scenario_id)
            rows.append({
                "scenario_id": scenario_id,
                "region": meta["region"],
                "season": meta["season"],
                "fault_type": meta["fault_type"],
                "num_chunks": len(files),
                "is_normal": meta["fault_type"] == "normal",
            })
        return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════
# SCENARIO-LEVEL TRAIN/VAL/TEST SPLIT
# ═══════════════════════════════════════════════════════════════════

def split_scenarios_by_type(
    loader: ParquetStreamLoader,
    train_ratio: float = DATA_CONFIG.train_ratio,
    val_ratio: float = DATA_CONFIG.val_ratio,
    seed: int = DATA_CONFIG.seed,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Split scenario_ids into train/val/test sets.

    The split is stratified by fault_type so each fault type is
    represented proportionally in all splits.

    Returns:
        (train_files, val_files, test_files) — lists of filenames
    """
    from sklearn.model_selection import train_test_split

    summary = loader.get_scenario_summary()
    scenarios = summary["scenario_id"].tolist()
    fault_types = summary["fault_type"].tolist()

    # First split: train vs (val + test)
    train_scenarios, temp_scenarios, _, temp_labels = train_test_split(
        scenarios, fault_types,
        train_size=train_ratio,
        stratify=fault_types,
        random_state=seed,
    )

    # Second split: val vs test from the remainder
    relative_val = val_ratio / (1 - train_ratio)
    val_scenarios, test_scenarios = train_test_split(
        temp_scenarios,
        train_size=relative_val,
        stratify=temp_labels,
        random_state=seed,
    )

    # Convert scenario IDs to file lists
    scenario_to_files = loader.scenario_map
    train_files = [f for s in train_scenarios for f in scenario_to_files[s]]
    val_files = [f for s in val_scenarios for f in scenario_to_files[s]]
    test_files = [f for s in test_scenarios for f in scenario_to_files[s]]

    logger.info(
        f"Split: {len(train_scenarios)} train / {len(val_scenarios)} val / "
        f"{len(test_scenarios)} test scenarios → "
        f"{len(train_files)} / {len(val_files)} / {len(test_files)} files"
    )

    return train_files, val_files, test_files


# ═══════════════════════════════════════════════════════════════════
# UTILITY: EXTRACT ZIP TO DISK (OPTIONAL — for faster repeated access)
# ═══════════════════════════════════════════════════════════════════

def extract_dataset(
    zip_path: str = DATASET_ZIP_PATH,
    extract_to: str = EXTRACTED_DATA_DIR,
) -> str:
    """
    Extract the ZIP to disk for faster access during training.
    Only needed if you prefer disk-based loading over ZIP streaming.

    Returns the extraction directory path.
    """
    if os.path.exists(extract_to) and len(os.listdir(extract_to)) > 0:
        logger.info(f"Dataset already extracted at {extract_to}")
        return extract_to

    os.makedirs(extract_to, exist_ok=True)
    logger.info(f"Extracting {zip_path} to {extract_to} ...")

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

    logger.info(f"Extraction complete: {len(os.listdir(extract_to))} files")
    return extract_to
