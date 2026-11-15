"""Typed loaders for the versioned files in `config/`.

Numbers live in config, never in code (CLAUDE.md rule 9). These models only
validate shape; they add no defaults for tolerances, weights or thresholds.
"""

from __future__ import annotations

import itertools
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.bodies import BodyName
from core.provenance import config_hash

REPO_ROOT = Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    return Path(os.environ.get("EAE_CONFIG_DIR", REPO_ROOT / "config"))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Loose(BaseModel):
    """Allows documentation-only keys we do not consume yet."""

    model_config = ConfigDict(extra="allow", frozen=True)


# ---------------------------------------------------------------- bbox


class BBox(_Strict):
    west: float
    south: float
    east: float
    north: float

    @model_validator(mode="after")
    def _ordered(self) -> BBox:
        if not (self.west < self.east and self.south < self.north):
            raise ValueError(f"bbox is not ordered west<east, south<north: {self}")
        return self


# ---------------------------------------------------------------- grids


class Laea(_Strict):
    lat_0: float
    lon_0: float
    proj: str


class Region(_Loose):
    id: str
    name: str
    role: Literal["benchmark", "discovery"]
    description: str = ""
    bbox: BBox
    laea: Laea
    scales_m: list[int]


class GridConfig(_Loose):
    version: str
    window_m: int
    stride_m: int
    alignment: str
    regions: list[Region]

    def region(self, region_id: str) -> Region:
        for r in self.regions:
            if r.id == region_id:
                return r
        raise KeyError(f"unknown region {region_id!r}")

    def region_ordinal(self, region_id: str) -> int:
        """1-based position of the region in the file. Part of the cell id (see core.grid)."""
        for i, r in enumerate(self.regions):
            if r.id == region_id:
                return i + 1
        raise KeyError(f"unknown region {region_id!r}")


# ---------------------------------------------------------------- targets


class Comparison(_Strict):
    center_lat: float
    center_lon: float
    footprint_m: int
    scale_m: int


class Preview(_Strict):
    bbox: BBox
    note: str = ""


class TargetConfig(_Strict):
    id: str
    body: BodyName
    name: str
    comparison: Comparison
    preview: Preview

    @model_validator(mode="after")
    def _not_earth(self) -> TargetConfig:
        if self.body == BodyName.EARTH:
            raise ValueError("targets are Moon or Mars locations")
        return self


# ---------------------------------------------------------------- scoring


class Tolerances(_Strict):
    slope_hist_deg: float
    slope_median_deg: float
    slope_p90_deg: float
    relief_fraction_of_target: float
    relief_floor_m: float
    roughness_fraction_of_target: float
    roughness_floor_m: float


class Eligibility(_Strict):
    valid_fraction_min: float
    water_fraction_max: float
    built_up_fraction_max: float
    snow_ice: Literal["flag_only", "exclude"]
    vegetation: Literal["flag_only", "exclude"]


class WorldCover(_Strict):
    water_classes: list[int]
    built_up_classes: list[int]
    snow_ice_classes: list[int]
    vegetation_classes: list[int]
    count_from: Literal["native_10m"]


class Retrieval(_Strict):
    top_k_default: int
    shortlist_multiplier: int
    standardize: Literal["zscore_eligible_windows_in_region"]


class Grouping(_Strict):
    nms_iou_above: float
    tie_break: list[str]
    merge: Literal["overlap_area_gt_0"]


class Novelty(_Strict):
    exclude_documented_from_candidates: bool
    documented_go_to: Literal["reference_matches"]


class NegativeControl(_Strict):
    eligible_relief_below_m: float


class ParquetContract(_Strict):
    columns: list[str]


class ScoringConfig(_Strict):
    version: str
    feature_schema_version: str
    purpose: str
    mandatory_features: list[str]
    retrieval_features: list[str]
    histogram_feature: str
    histogram_distance: Literal["wasserstein_1_degrees"]
    slope_hist_bins_deg: list[float]
    weights: dict[str, float]
    tolerances: Tolerances
    eligibility: Eligibility
    worldcover: WorldCover
    retrieval: Retrieval
    grouping: Grouping
    novelty: Novelty
    negative_control: NegativeControl
    parquet: ParquetContract

    @model_validator(mode="after")
    def _consistent(self) -> ScoringConfig:
        bins = self.slope_hist_bins_deg
        if bins[0] != 0 or bins[-1] != 90 or any(b2 <= b1 for b1, b2 in itertools.pairwise(bins)):
            raise ValueError("slope_hist_bins_deg must increase from 0 to 90")
        if set(self.weights) != set(self.mandatory_features):
            raise ValueError("weights must cover exactly the mandatory features")
        if not set(self.retrieval_features) <= set(self.mandatory_features):
            raise ValueError("retrieval features must be mandatory features")
        if self.histogram_feature in self.retrieval_features:
            raise ValueError("the histogram is rerank-only (D-020)")
        return self

    @property
    def n_hist_bins(self) -> int:
        return len(self.slope_hist_bins_deg) - 1


# ---------------------------------------------------------------- sources


class SourcesConfig(_Strict):
    version: str
    hosts: list[str]
    suffixes: list[str] = Field(default_factory=list)


class Product(_Strict):
    id: str
    body: BodyName
    provider: str
    kind: Literal["stac_collection", "url_cog", "s3_tiles"]
    url: str
    resolution_m: float
    version: str
    licence: str
    collection: str | None = None
    tile_template: str | None = None
    tile_size_deg: int | None = None
    notes: str = ""


class ProductsConfig(_Strict):
    version: str
    products: list[Product]

    def product(self, product_id: str) -> Product:
        for p in self.products:
            if p.id == product_id:
                return p
        raise KeyError(f"unknown product {product_id!r}")


# ---------------------------------------------------------------- loaders


def _read_yaml(path: Path) -> object:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def scoring_path(version: str = "terrain-v1") -> Path:
    return config_dir() / "scoring" / f"{version}.yaml"


def grid_path(version: str = "pilot-v1") -> Path:
    return config_dir() / "grids" / f"{version}.yaml"


def target_paths() -> list[Path]:
    return sorted((config_dir() / "targets").glob("*.yaml"))


@lru_cache(maxsize=8)
def load_scoring(version: str = "terrain-v1") -> ScoringConfig:
    cfg = ScoringConfig.model_validate(_read_yaml(scoring_path(version)))
    if cfg.version != version:
        raise ValueError(f"{scoring_path(version)} declares version {cfg.version!r}")
    return cfg


@lru_cache(maxsize=8)
def load_grid(version: str = "pilot-v1") -> GridConfig:
    cfg = GridConfig.model_validate(_read_yaml(grid_path(version)))
    if cfg.version != version:
        raise ValueError(f"{grid_path(version)} declares version {cfg.version!r}")
    return cfg


@lru_cache(maxsize=1)
def load_targets() -> dict[str, TargetConfig]:
    out: dict[str, TargetConfig] = {}
    for p in target_paths():
        t = TargetConfig.model_validate(_read_yaml(p))
        if t.id in out:
            raise ValueError(f"duplicate target id {t.id}")
        out[t.id] = t
    return out


def load_target(target_id: str) -> TargetConfig:
    try:
        return load_targets()[target_id]
    except KeyError as exc:
        raise KeyError(f"unknown target {target_id!r}") from exc


@lru_cache(maxsize=1)
def load_sources() -> SourcesConfig:
    return SourcesConfig.model_validate(_read_yaml(config_dir() / "sources.yaml"))


@lru_cache(maxsize=1)
def load_products(version: str = "products-v1") -> ProductsConfig:
    return ProductsConfig.model_validate(_read_yaml(config_dir() / f"{version}.yaml"))


def run_config_hash(scoring_version: str = "terrain-v1", grid_version: str = "pilot-v1") -> str:
    """Hash of every config file that can change a feature or a score."""
    paths = [scoring_path(scoring_version), grid_path(grid_version), *target_paths()]
    products = config_dir() / "products-v1.yaml"
    if products.exists():
        paths.append(products)
    return config_hash(paths)


class GazetteerFile(_Strict):
    body: BodyName
    url: str
    scale_m: int
    lat_min: float
    lat_max: float


class GazetteerConfig(_Strict):
    version: str
    footprint_m: int
    diameter_km_min: float
    diameter_km_max: float
    feature_types: list[str]
    bodies: list[GazetteerFile]


def gazetteer_path(version: str = "gazetteer-v1") -> Path:
    return config_dir() / f"{version}.yaml"


@lru_cache(maxsize=2)
def load_gazetteer(version: str = "gazetteer-v1") -> GazetteerConfig:
    cfg = GazetteerConfig.model_validate(_read_yaml(gazetteer_path(version)))
    if cfg.version != version:
        raise ValueError(f"{gazetteer_path(version)} declares version {cfg.version!r}")
    if cfg.diameter_km_min <= 0 or cfg.diameter_km_max < cfg.diameter_km_min:
        raise ValueError("gazetteer diameter bounds must be positive and ordered")
    return cfg


def clear_caches() -> None:
    for fn in (load_scoring, load_grid, load_targets, load_sources, load_products, load_gazetteer):
        fn.cache_clear()
