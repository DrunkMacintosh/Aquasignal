"""AquaSignal data ingestion pipeline.

Ingests three free satellite data sources, aligns them onto a common
0.25-degree EPSG:4326 grid over Vietnam, and stores the result as
monthly-partitioned Parquet plus GeoJSON grid metadata.

Sources
-------
1. GRACE-FO mascon (NASA PO.DAAC via CMR) -- groundwater mass anomaly, cm LWE.
2. Sentinel-1 GRD VV (Google Earth Engine)  -- monthly backscatter composite.
   NOTE: GRD intensity is a *proxy* for subsidence. True mm displacement
   requires SLC interferometry, which GEE does not host. The variable is
   named ``sar_subsidence`` per the AquaSignal schema but holds VV dB.
3. ERA5-Land monthly (Google Earth Engine)  -- precipitation, PET, temperature.

Entry point: :func:`run_pipeline`, or ``python pipeline.py --start ... --end ...``.
"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import xarray as xr
from shapely.geometry import box

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BoundingBox:
    """Geographic bounding box in EPSG:4326 decimal degrees."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def to_ee_geometry(self) -> ee.Geometry:
        """Return the box as an Earth Engine rectangle geometry."""
        return ee.Geometry.Rectangle(
            [self.min_lon, self.min_lat, self.max_lon, self.max_lat],
            proj="EPSG:4326",
            geodesic=False,
        )


@dataclass(frozen=True)
class TargetGrid:
    """Canonical analysis grid: cell-center coordinates, EPSG:4326."""

    lats: np.ndarray
    lons: np.ndarray

    @property
    def n_cells(self) -> int:
        return len(self.lats) * len(self.lons)


# Vietnam pilot region (full national extent).
VIETNAM_BBOX = BoundingBox(min_lon=102.0, min_lat=8.5, max_lon=109.5, max_lat=23.5)

# Priority sub-regions with the most severe groundwater depletion. Used to tag
# grid cells in the GeoJSON metadata so downstream scoring can weight them.
PRIORITY_REGIONS: dict[str, BoundingBox] = {
    "mekong_delta": BoundingBox(104.5, 9.0, 106.8, 11.0),
    "red_river_delta": BoundingBox(105.5, 20.0, 107.0, 21.5),
}

GRID_RES_DEG = 0.25
GRID_SCALE_M = GRID_RES_DEG * 111_320.0  # ~27.8 km at the equator

CMR_GRANULE_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
# RL06.1_V3 was retired from CMR; RL06.3_V4 is the same CRI-filtered mascon
# grid product, current as of mid-2026.
GRACE_SHORT_NAME = "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"
GRACE_VARIABLE = "lwe_thickness"
# GRACE publishes ~60 days behind real time; forward-fill at most this many
# months so the stack stays dense without inventing data beyond the lag.
GRACE_FFILL_LIMIT_MONTHS = 2

GEE_S1_COLLECTION = "COPERNICUS/S1_GRD"
GEE_ERA5_COLLECTION = "ECMWF/ERA5_LAND/MONTHLY_AGGR"
ERA5_BANDS = ["total_precipitation_sum", "potential_evaporation_sum", "temperature_2m"]

DEFAULT_HISTORY_MONTHS = 24
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
MANIFEST_NAME = "data_manifest.json"
GRID_GEOJSON_NAME = "grid_cells.geojson"

HTTP_TIMEOUT_S = 120
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_S = 2.0

VARIABLE_ATTRS: dict[str, dict[str, str]] = {
    "grace_anomaly": {
        "units": "cm",
        "long_name": "Liquid water equivalent thickness anomaly (2004-2009 baseline)",
        "source": GRACE_SHORT_NAME,
    },
    "sar_subsidence": {
        "units": "dB",
        "long_name": "Sentinel-1 VV monthly mean backscatter (subsidence proxy)",
        "source": GEE_S1_COLLECTION,
    },
    "precipitation": {
        "units": "mm/month",
        "long_name": "Total precipitation",
        "source": GEE_ERA5_COLLECTION,
    },
    "evapotranspiration": {
        "units": "mm/month",
        "long_name": "Potential evaporation (ECMWF sign convention inverted to positive)",
        "source": GEE_ERA5_COLLECTION,
    },
    "temperature": {
        "units": "degC",
        "long_name": "2 m air temperature",
        "source": GEE_ERA5_COLLECTION,
    },
}

# --------------------------------------------------------------------------- #
# Logging                                                                      #
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=sys.stdout,
)
LOG = logging.getLogger("aquasignal.pipeline")

F = TypeVar("F", bound=Callable[..., Any])

# --------------------------------------------------------------------------- #
# Retry decorator                                                              #
# --------------------------------------------------------------------------- #


def retry(
    max_attempts: int = RETRY_ATTEMPTS,
    base_delay_s: float = RETRY_BASE_DELAY_S,
    exceptions: tuple[type[Exception], ...] = (requests.RequestException, ee.EEException),
) -> Callable[[F], F]:
    """Retry a callable with exponential backoff (2s, 4s, 8s by default).

    Args:
        max_attempts: Total attempts before the last exception is re-raised.
        base_delay_s: Delay before the first retry; doubles each attempt.
        exceptions: Exception types that trigger a retry.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        LOG.error("%s failed after %d attempts: %s", fn.__name__, attempt, exc)
                        raise
                    delay = base_delay_s * 2 ** (attempt - 1)
                    LOG.warning(
                        "%s attempt %d/%d failed (%s); retrying in %.1fs",
                        fn.__name__, attempt, max_attempts, exc, delay,
                    )
                    time.sleep(delay)
            raise RuntimeError("unreachable")  # pragma: no cover

        return wrapper  # type: ignore[return-value]

    return decorator


# --------------------------------------------------------------------------- #
# NASA Earthdata: auth, CMR search, GRACE download                             #
# --------------------------------------------------------------------------- #


class EarthdataSession(requests.Session):
    """Session that keeps Basic-auth credentials across the URS redirect chain.

    NASA Earthdata downloads bounce through ``urs.earthdata.nasa.gov``;
    a vanilla ``requests.Session`` strips the Authorization header when the
    host changes, so authentication silently fails. This override (NASA's
    documented pattern) re-attaches credentials only for the URS host or the
    originally requested host.
    """

    URS_HOST = "urs.earthdata.nasa.gov"

    def __init__(self, username: str, password: str) -> None:
        super().__init__()
        self.auth = (username, password)

    def rebuild_auth(self, prepared_request: Any, response: Any) -> None:
        headers = prepared_request.headers
        url = prepared_request.url or ""
        if "Authorization" in headers:
            original = requests.utils.urlparse(response.request.url).hostname
            redirect = requests.utils.urlparse(url).hostname
            if redirect not in (original, self.URS_HOST) and original != self.URS_HOST:
                del headers["Authorization"]


def build_earthdata_session() -> EarthdataSession:
    """Create an authenticated Earthdata session from environment variables.

    Raises:
        EnvironmentError: If EARTHDATA_USER or EARTHDATA_PASS is missing.
    """
    user = os.environ.get("EARTHDATA_USER")
    password = os.environ.get("EARTHDATA_PASS")
    if not user or not password:
        raise EnvironmentError(
            "EARTHDATA_USER and EARTHDATA_PASS must be set. "
            "Register at https://urs.earthdata.nasa.gov/."
        )
    LOG.info("Earthdata session created for user '%s'", user)
    return EarthdataSession(user, password)


@retry()
def find_latest_grace_granule_url() -> str:
    """Query CMR for the newest GRACE-FO mascon granule and return its data URL.

    The JPL mascon product ships the *entire* time series in a single NetCDF
    that is re-issued each month, so "latest 24 months" means downloading the
    newest granule and subsetting in xarray.

    CMR search is anonymous and must NOT receive the Earthdata Basic-auth
    header: CMR tries to validate any Authorization header as an EDL token
    and returns 401. Credentials are only needed for the download itself.

    Returns:
        Direct HTTPS download URL for the newest ``.nc`` granule.

    Raises:
        RuntimeError: If CMR returns no granules or no downloadable .nc link.
    """
    params = {"short_name": GRACE_SHORT_NAME, "sort_key": "-start_date", "page_size": 5}
    resp = requests.get(CMR_GRANULE_URL, params=params, timeout=HTTP_TIMEOUT_S)
    resp.raise_for_status()
    entries = resp.json().get("feed", {}).get("entry", [])
    if not entries:
        raise RuntimeError(f"CMR returned no granules for {GRACE_SHORT_NAME}")

    for entry in entries:
        for link in entry.get("links", []):
            href = link.get("href", "")
            if link.get("rel", "").endswith("/data#") and href.endswith(".nc"):
                LOG.info("Latest GRACE granule: %s", entry.get("title", href))
                return href
    raise RuntimeError("No downloadable .nc link found in CMR granule entries")


@retry()
def download_grace_netcdf(session: requests.Session, url: str, raw_dir: Path) -> Path:
    """Download the GRACE NetCDF to ``raw_dir`` unless it is already cached.

    Writes to a ``.part`` temp file and renames on success so an interrupted
    download never leaves a truncated file that poisons later runs.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / url.rsplit("/", 1)[-1]
    if dest.exists():
        LOG.info("GRACE file already cached, skipping download: %s", dest.name)
        return dest

    LOG.info("Downloading GRACE granule to %s", dest)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with session.get(url, stream=True, timeout=HTTP_TIMEOUT_S) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    tmp.rename(dest)
    LOG.info("GRACE download complete (%.1f MB)", dest.stat().st_size / 1e6)
    return dest


def load_grace_anomaly(nc_path: Path, bbox: BoundingBox, grid: TargetGrid) -> xr.DataArray:
    """Load GRACE LWE anomaly, regrid to the canonical grid, snap to months.

    Steps: normalise 0-360 longitudes to -180..180, subset with a 1-degree
    buffer (bilinear needs neighbours beyond the edge cells), stamp EPSG:4326,
    bilinearly interpolate to cell centers, then snap each mid-month epoch to
    the first day of its calendar month.

    Returns:
        DataArray ``grace_anomaly`` with dims (time, lat, lon).
    """
    LOG.info("Loading GRACE mascon NetCDF: %s", nc_path.name)
    with xr.open_dataset(nc_path) as ds:
        da = ds[GRACE_VARIABLE].load()

    da = da.assign_coords(lon=(((da.lon + 180) % 360) - 180)).sortby("lon").sortby("lat")
    da = da.sel(
        lon=slice(bbox.min_lon - 1.0, bbox.max_lon + 1.0),
        lat=slice(bbox.min_lat - 1.0, bbox.max_lat + 1.0),
    )
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat").rio.write_crs("EPSG:4326")
    da = da.interp(lat=grid.lats, lon=grid.lons, method="linear")

    month_starts = pd.DatetimeIndex(da.time.values).to_period("M").to_timestamp()
    da = da.assign_coords(time=month_starts)
    # GRACE gaps occasionally produce two solutions snapping to one month.
    da = da.groupby("time").first()

    da.name = "grace_anomaly"
    da.attrs.update(VARIABLE_ATTRS["grace_anomaly"])
    LOG.info(
        "GRACE regridded: %d epochs, %s to %s",
        da.sizes["time"],
        pd.Timestamp(da.time.values[0]).date(),
        pd.Timestamp(da.time.values[-1]).date(),
    )
    return da


# --------------------------------------------------------------------------- #
# Google Earth Engine: init, grid sampling, monthly fetch                      #
# --------------------------------------------------------------------------- #


def init_earth_engine() -> None:
    """Initialise the Earth Engine client.

    Uses a service account when EE_SERVICE_ACCOUNT / EE_PRIVATE_KEY_FILE are
    set (CI / production); otherwise falls back to locally stored credentials
    from ``earthengine authenticate`` with an optional GEE_PROJECT.
    """
    service_account = os.environ.get("EE_SERVICE_ACCOUNT")
    key_file = os.environ.get("EE_PRIVATE_KEY_FILE")
    project = os.environ.get("GEE_PROJECT")
    if service_account and key_file:
        credentials = ee.ServiceAccountCredentials(service_account, key_file)
        ee.Initialize(credentials, project=project)
        LOG.info("Earth Engine initialised with service account %s", service_account)
    else:
        ee.Initialize(project=project)
        LOG.info("Earth Engine initialised with user credentials (project=%s)", project)


def build_target_grid(bbox: BoundingBox, res_deg: float = GRID_RES_DEG) -> TargetGrid:
    """Build the canonical grid of cell-center coordinates.

    Centers sit at ``min + res/2 + k*res`` -- integer cell counts avoid the
    float drift of ``np.arange`` and keep edges exactly on the bbox.
    """
    n_lon = int(round((bbox.max_lon - bbox.min_lon) / res_deg))
    n_lat = int(round((bbox.max_lat - bbox.min_lat) / res_deg))
    lons = bbox.min_lon + res_deg / 2 + res_deg * np.arange(n_lon)
    lats = bbox.min_lat + res_deg / 2 + res_deg * np.arange(n_lat)
    LOG.info("Target grid: %d lat x %d lon = %d cells at %.2f deg", n_lat, n_lon, n_lat * n_lon, res_deg)
    return TargetGrid(lats=lats, lons=lons)


def build_grid_points(grid: TargetGrid) -> ee.FeatureCollection:
    """Build an EE FeatureCollection of cell-centroid points keyed by ``idx``.

    The flat index (``idx = i * n_lon + j``) is the only reliable way to map
    sampled values back to grid positions: ``sampleRegions`` drops points
    where the image is masked, so positional order cannot be trusted.
    """
    n_lon = len(grid.lons)
    features = [
        ee.Feature(ee.Geometry.Point([float(lon), float(lat)]), {"idx": i * n_lon + j})
        for i, lat in enumerate(grid.lats)
        for j, lon in enumerate(grid.lons)
    ]
    return ee.FeatureCollection(features)


@retry()
def sample_image_at_grid(image: ee.Image, points: ee.FeatureCollection, bands: list[str]) -> list[dict]:
    """Sample an EE image at the grid centroids at 0.25-degree scale.

    Sampling at ``GRID_SCALE_M`` makes Earth Engine aggregate native pixels
    through its image pyramid (area mean), which is the correct operation when
    *downsampling* 10 m / 9 km sources to ~28 km cells. Inputs are additionally
    bilinear-resampled upstream (see fetchers) per the alignment contract.

    Returns:
        Raw GeoJSON feature dicts (properties contain ``idx`` plus band values).
    """
    sampled = image.select(bands).sampleRegions(
        collection=points,
        scale=GRID_SCALE_M,
        projection="EPSG:4326",
        geometries=False,
        tileScale=4,
    )
    return sampled.getInfo()["features"]


def features_to_grid_arrays(
    features: list[dict], bands: list[str], grid: TargetGrid
) -> dict[str, np.ndarray]:
    """Scatter sampled feature values into (lat, lon) arrays, NaN where masked."""
    n_lon = len(grid.lons)
    arrays = {b: np.full((len(grid.lats), n_lon), np.nan) for b in bands}
    for feature in features:
        props = feature["properties"]
        i, j = divmod(int(props["idx"]), n_lon)
        for band in bands:
            value = props.get(band)
            if value is not None:
                arrays[band][i, j] = float(value)
    return arrays


def build_s1_monthly_image(month: pd.Timestamp, region: ee.Geometry) -> ee.Image:
    """Build the Sentinel-1 VV monthly mean composite for one month.

    Filters to IW mode with VV polarisation, bilinear-resamples each scene,
    then takes the temporal mean. Returns a fully-masked placeholder when no
    scenes exist so the combined sampling image keeps a stable band layout.
    """
    start = month.strftime("%Y-%m-%d")
    end = (month + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")
    collection = (
        ee.ImageCollection(GEE_S1_COLLECTION)
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .select("VV")
        .map(lambda img: img.resample("bilinear"))
    )
    placeholder = ee.Image.constant(0).updateMask(ee.Image.constant(0)).rename("VV")
    return ee.Image(
        ee.Algorithms.If(collection.size().gt(0), collection.mean(), placeholder)
    ).rename("VV")


def fetch_gee_month(
    month: pd.Timestamp, bbox: BoundingBox, points: ee.FeatureCollection, grid: TargetGrid
) -> dict[str, np.ndarray] | None:
    """Fetch ERA5 + Sentinel-1 values for one month on the canonical grid.

    Returns:
        Mapping of variable name to (lat, lon) array with units converted
        (precip/PET m -> mm, PET sign inverted, temperature K -> degC),
        or None when ERA5 has not yet published this month (caller skips it).
    """
    start = month.strftime("%Y-%m-%d")
    end = (month + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")
    era5_collection = ee.ImageCollection(GEE_ERA5_COLLECTION).filterDate(start, end)

    if int(era5_collection.size().getInfo()) == 0:
        LOG.warning("ERA5 month %s not yet published; skipping month", month.strftime("%Y-%m"))
        return None

    era5_image = ee.Image(era5_collection.first()).select(ERA5_BANDS).resample("bilinear")
    s1_image = build_s1_monthly_image(month, bbox.to_ee_geometry())
    combined = era5_image.addBands(s1_image)

    features = sample_image_at_grid(combined, points, ERA5_BANDS + ["VV"])
    raw = features_to_grid_arrays(features, ERA5_BANDS + ["VV"], grid)

    return {
        "precipitation": raw["total_precipitation_sum"] * 1000.0,  # m -> mm
        # ECMWF convention: evaporation is negative downward; invert to positive mm.
        "evapotranspiration": raw["potential_evaporation_sum"] * -1000.0,
        "temperature": raw["temperature_2m"] - 273.15,  # K -> degC
        "sar_subsidence": raw["VV"],
    }


# --------------------------------------------------------------------------- #
# Alignment and stacking                                                       #
# --------------------------------------------------------------------------- #


def align_grace_to_months(
    grace: xr.DataArray, months: pd.DatetimeIndex
) -> tuple[xr.DataArray, list[str]]:
    """Reindex GRACE onto the master month axis and bound-fill the lag.

    GRACE publishes ~60 days behind ERA5/Sentinel and has occasional gap
    months. Missing months are forward-filled up to
    ``GRACE_FFILL_LIMIT_MONTHS`` so the trailing edge of the stack stays
    usable, and every filled month is reported so the manifest can flag it.

    Returns:
        The aligned DataArray and the list of 'YYYY-MM' months that were filled.
    """
    reindexed = grace.reindex(time=months)
    missing_before = reindexed.isnull().all(dim=["lat", "lon"])
    filled = reindexed.ffill(dim="time", limit=GRACE_FFILL_LIMIT_MONTHS)
    present_after = filled.notnull().any(dim=["lat", "lon"])

    filled_months = [
        pd.Timestamp(t).strftime("%Y-%m")
        for t, was_missing, now_present in zip(
            months, missing_before.values, present_after.values
        )
        if was_missing and now_present
    ]
    if filled_months:
        LOG.info("GRACE forward-filled (publication lag) for: %s", ", ".join(filled_months))
    return filled, filled_months


def assemble_dataset(
    grace: xr.DataArray,
    gee_months: dict[pd.Timestamp, dict[str, np.ndarray]],
    grid: TargetGrid,
) -> xr.Dataset:
    """Stack all variables into one (time, lat, lon) Dataset on EPSG:4326."""
    months = pd.DatetimeIndex(sorted(gee_months))
    gee_vars = ["sar_subsidence", "precipitation", "evapotranspiration", "temperature"]
    data_vars = {
        var: (
            ("time", "lat", "lon"),
            np.stack([gee_months[m][var] for m in months]),
        )
        for var in gee_vars
    }
    ds = xr.Dataset(
        data_vars,
        coords={"time": months, "lat": grid.lats, "lon": grid.lons},
    )
    ds["grace_anomaly"] = grace.sel(time=months)
    for var, attrs in VARIABLE_ATTRS.items():
        ds[var].attrs.update(attrs)
    ds = ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat").rio.write_crs("EPSG:4326")
    ds.attrs.update({"crs": "EPSG:4326", "grid_res_deg": GRID_RES_DEG})
    LOG.info("Assembled dataset: %d months x %d cells, %d variables",
             ds.sizes["time"], grid.n_cells, len(ds.data_vars))
    return ds


# --------------------------------------------------------------------------- #
# Storage: Parquet, GeoJSON, manifest                                          #
# --------------------------------------------------------------------------- #


def month_parquet_path(processed_dir: Path, month: pd.Timestamp) -> Path:
    """Return the partition path for one month, e.g. aquasignal_2026-04.parquet."""
    return processed_dir / f"aquasignal_{month.strftime('%Y-%m')}.parquet"


def write_month_parquet(ds: xr.Dataset, month: pd.Timestamp, processed_dir: Path) -> Path:
    """Write one month of the aligned dataset to a Parquet partition."""
    path = month_parquet_path(processed_dir, month)
    df = ds.sel(time=month).to_dataframe().reset_index()
    # Select the schema columns explicitly: this drops rioxarray's CRS
    # coordinate (named 'spatial_ref' or 'WGS84' depending on version) and
    # keeps the scalar 'time' coordinate that survives sel() as a column.
    df = df[["time", "lat", "lon"] + [v for v in VARIABLE_ATTRS if v in df.columns]]
    df.to_parquet(path, engine="pyarrow", index=False)
    LOG.info("Wrote %s (%d rows)", path.name, len(df))
    return path


def classify_priority_region(lat: float, lon: float) -> str | None:
    """Return the priority region containing a cell centroid, if any."""
    for name, region in PRIORITY_REGIONS.items():
        if region.min_lat <= lat <= region.max_lat and region.min_lon <= lon <= region.max_lon:
            return name
    return None


def write_grid_geojson(grid: TargetGrid, processed_dir: Path) -> Path:
    """Write each 0.25-degree cell as a polygon feature with centroid metadata.

    Idempotent: skipped when the file already exists (the grid is static for
    a given bbox; deleting the file forces regeneration).
    """
    path = processed_dir / GRID_GEOJSON_NAME
    if path.exists():
        LOG.info("Grid GeoJSON already exists, skipping: %s", path.name)
        return path

    half = GRID_RES_DEG / 2
    records = [
        {
            "cell_id": f"{lat:.3f}_{lon:.3f}",
            "centroid_lat": float(lat),
            "centroid_lon": float(lon),
            "priority_region": classify_priority_region(float(lat), float(lon)),
            "geometry": box(lon - half, lat - half, lon + half, lat + half),
        }
        for lat in grid.lats
        for lon in grid.lons
    ]
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf.to_file(path, driver="GeoJSON")
    LOG.info("Wrote grid metadata: %s (%d cells)", path.name, len(gdf))
    return path


def load_manifest(processed_dir: Path) -> dict[str, Any]:
    """Load the data manifest, or return a fresh skeleton if absent."""
    path = processed_dir / MANIFEST_NAME
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"dataset": "aquasignal_aligned_v1", "months": {}}


def update_manifest(
    processed_dir: Path,
    bbox: BoundingBox,
    written_months: list[pd.Timestamp],
    grace_filled_months: list[str],
) -> Path:
    """Record newly written months and pipeline metadata in data_manifest.json."""
    manifest = load_manifest(processed_dir)
    now_iso = datetime.now(timezone.utc).isoformat()
    for month in written_months:
        key = month.strftime("%Y-%m")
        manifest["months"][key] = {
            "file": month_parquet_path(processed_dir, month).name,
            "written_at": now_iso,
            "grace_forward_filled": key in grace_filled_months,
        }
    manifest.update(
        {
            "crs": "EPSG:4326",
            "grid_res_deg": GRID_RES_DEG,
            "bbox": asdict(bbox),
            "variables": VARIABLE_ATTRS,
            "updated_at": now_iso,
        }
    )
    path = processed_dir / MANIFEST_NAME
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    LOG.info("Manifest updated: %d total months tracked", len(manifest["months"]))
    return path


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #


def resolve_month_range(start_date: str | None, end_date: str | None) -> pd.DatetimeIndex:
    """Resolve ISO date strings to a month-start index (default: last 24 full months)."""
    if end_date:
        end = pd.Timestamp(end_date).to_period("M").to_timestamp()
    else:
        end = (pd.Timestamp.today().to_period("M") - 1).to_timestamp()
    if start_date:
        start = pd.Timestamp(start_date).to_period("M").to_timestamp()
    else:
        start = (end.to_period("M") - (DEFAULT_HISTORY_MONTHS - 1)).to_timestamp()
    if start > end:
        raise ValueError(f"start_date {start.date()} is after end_date {end.date()}")
    return pd.date_range(start, end, freq="MS")


def find_pending_months(months: pd.DatetimeIndex, processed_dir: Path) -> list[pd.Timestamp]:
    """Idempotency gate: return only months without an existing Parquet partition."""
    pending = [m for m in months if not month_parquet_path(processed_dir, m).exists()]
    skipped = len(months) - len(pending)
    if skipped:
        LOG.info("Idempotency: %d month(s) already processed, skipping", skipped)
    return pending


def run_pipeline(
    start_date: str | None = None,
    end_date: str | None = None,
    bbox: BoundingBox = VIETNAM_BBOX,
    data_dir: str | Path = DEFAULT_DATA_DIR,
) -> Path:
    """Run the full AquaSignal ingestion pipeline.

    Args:
        start_date: ISO date ('YYYY-MM-DD'); defaults to 24 months before end.
        end_date: ISO date; defaults to the last complete calendar month.
        bbox: Region of interest; defaults to the Vietnam pilot bounding box.
        data_dir: Root data directory (raw/ and processed/ live underneath).

    Returns:
        Path to the updated data_manifest.json.
    """
    data_dir = Path(data_dir)
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    LOG.info("=== AquaSignal pipeline start ===")
    months = resolve_month_range(start_date, end_date)
    LOG.info(
        "Step 1/7: range %s to %s (%d months), bbox=%s",
        months[0].date(), months[-1].date(), len(months), asdict(bbox),
    )

    grid = build_target_grid(bbox)
    write_grid_geojson(grid, processed_dir)

    pending = find_pending_months(months, processed_dir)
    if not pending:
        LOG.info("Step 2/7: nothing to do -- all requested months already processed")
        return update_manifest(processed_dir, bbox, [], [])
    LOG.info("Step 2/7: %d month(s) pending: %s",
             len(pending), ", ".join(m.strftime("%Y-%m") for m in pending))

    LOG.info("Step 3/7: GRACE-FO ingestion via NASA Earthdata/CMR")
    session = build_earthdata_session()
    granule_url = find_latest_grace_granule_url()
    nc_path = download_grace_netcdf(session, granule_url, data_dir / "raw" / "grace")
    grace = load_grace_anomaly(nc_path, bbox, grid)

    LOG.info("Step 4/7: Google Earth Engine ingestion (Sentinel-1 + ERA5)")
    init_earth_engine()
    points = build_grid_points(grid)
    gee_months: dict[pd.Timestamp, dict[str, np.ndarray]] = {}
    for month in pending:
        LOG.info("Fetching GEE composites for %s", month.strftime("%Y-%m"))
        arrays = fetch_gee_month(month, bbox, points, grid)
        if arrays is not None:
            gee_months[month] = arrays
    if not gee_months:
        LOG.warning("No pending month has published ERA5 data yet; nothing written")
        return update_manifest(processed_dir, bbox, [], [])

    LOG.info("Step 5/7: temporal alignment (GRACE lag handling)")
    grace_aligned, grace_filled = align_grace_to_months(grace, months)

    LOG.info("Step 6/7: stacking variables onto common (time, lat, lon) grid")
    ds = assemble_dataset(grace_aligned, gee_months, grid)

    LOG.info("Step 7/7: writing monthly Parquet partitions + manifest")
    written = [
        month for month in sorted(gee_months)
        if write_month_parquet(ds, month, processed_dir)
    ]
    manifest_path = update_manifest(processed_dir, bbox, written, grace_filled)
    LOG.info("=== AquaSignal pipeline complete: %d month(s) written ===", len(written))
    return manifest_path


def main() -> None:
    """CLI entry point: ``python pipeline.py --start 2024-07-01 --end 2026-05-31``."""
    parser = argparse.ArgumentParser(description="AquaSignal satellite data ingestion pipeline")
    parser.add_argument("--start", help="ISO start date (default: 24 months before end)")
    parser.add_argument("--end", help="ISO end date (default: last complete month)")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Root data directory")
    parser.add_argument(
        "--bbox",
        help="Override bbox as 'min_lon,min_lat,max_lon,max_lat' (default: Vietnam)",
    )
    args = parser.parse_args()

    bbox = VIETNAM_BBOX
    if args.bbox:
        parts = [float(p) for p in args.bbox.split(",")]
        if len(parts) != 4:
            parser.error("--bbox requires exactly 4 comma-separated numbers")
        bbox = BoundingBox(*parts)

    run_pipeline(start_date=args.start, end_date=args.end, bbox=bbox, data_dir=args.data_dir)


if __name__ == "__main__":
    main()
