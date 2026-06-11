# AquaSignal — Data Ingestion Pipeline

Groundwater risk forecasting for Vietnam, built on three free satellite data
sources fused onto a common 0.25° grid:

| Variable             | Source                                              | Native res. | Units    |
|----------------------|-----------------------------------------------------|-------------|----------|
| `grace_anomaly`      | GRACE-FO mascon (NASA PO.DAAC, RL06.3 v4)           | ~450 km     | cm LWE   |
| `sar_subsidence`     | Sentinel-1 GRD VV composite (GEE) — *proxy, see note* | 10 m      | dB       |
| `precipitation`      | ERA5-Land monthly (GEE)                             | ~9 km       | mm/month |
| `evapotranspiration` | ERA5-Land potential evaporation (GEE, sign-inverted)| ~9 km       | mm/month |
| `temperature`        | ERA5-Land 2 m temperature (GEE)                     | ~9 km       | °C       |

> **Note on `sar_subsidence`:** Sentinel-1 *GRD* provides backscatter
> intensity, not interferometric phase. True millimetre-scale displacement
> requires SLC InSAR processing (PSI/SBAS), which Google Earth Engine does not
> host. This variable holds the monthly mean VV backscatter (dB) as a
> surface-change *proxy feature*; treat it accordingly in downstream models.

## Prerequisites

- **Python 3.11**
- **NASA Earthdata account** — free registration at
  <https://urs.earthdata.nasa.gov/>. You must also approve the *PO.DAAC*
  application once in your Earthdata profile (Applications → Authorized Apps).
- **Google Earth Engine access** — register a cloud project at
  <https://console.cloud.google.com/earth-engine>.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # PowerShell; use .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
```

### Credentials (environment variables)

| Variable              | Required | Purpose                                              |
|-----------------------|----------|------------------------------------------------------|
| `EARTHDATA_USER`      | yes      | NASA Earthdata username (GRACE-FO download)          |
| `EARTHDATA_PASS`      | yes      | NASA Earthdata password                              |
| `GEE_PROJECT`         | yes*     | Google Cloud project registered for Earth Engine     |
| `EE_SERVICE_ACCOUNT`  | no       | Service-account email for headless/CI runs           |
| `EE_PRIVATE_KEY_FILE` | no       | Path to the service-account JSON key                 |

\* Required unless your locally stored Earth Engine credentials carry a
default project.

For **interactive use**, authenticate Earth Engine once:

```powershell
earthengine authenticate
```

For **CI / production**, set `EE_SERVICE_ACCOUNT` + `EE_PRIVATE_KEY_FILE`
instead — no browser flow needed. Never commit credentials; set them in the
environment or a secret manager:

```powershell
$env:EARTHDATA_USER = "your_username"
$env:EARTHDATA_PASS = "your_password"
$env:GEE_PROJECT    = "your-gee-project-id"
```

## Running

```powershell
# Default: latest 24 complete months over Vietnam
python pipeline.py

# Explicit range
python pipeline.py --start 2024-07-01 --end 2026-05-31

# Custom region (future expansion) and data directory
python pipeline.py --bbox 99.0,5.0,110.0,24.0 --data-dir D:\aquasignal-data
```

Or from Python:

```python
from pipeline import run_pipeline, BoundingBox

run_pipeline(start_date="2024-07-01", end_date="2026-05-31")            # Vietnam default
run_pipeline(bbox=BoundingBox(99.0, 5.0, 110.0, 24.0))                  # override region
```

## Outputs

```
data/
├── raw/grace/                      # cached GRACE-FO NetCDF (skipped if present)
└── processed/
    ├── aquasignal_YYYY-MM.parquet  # one partition per month: time, lat, lon + 5 variables
    ├── grid_cells.geojson          # every 0.25° cell as a polygon, with centroid
    │                               #   lat/lon and priority_region tag
    │                               #   (mekong_delta / red_river_delta / null)
    └── data_manifest.json          # months available, write timestamps, bbox,
                                    #   variable units, GRACE forward-fill flags
```

## Behaviour notes

- **Idempotent.** Re-running skips any month whose Parquet partition already
  exists; only missing months are fetched. Delete a partition (or
  `grid_cells.geojson`) to force regeneration.
- **GRACE publication lag (~60 days).** The time axis is anchored to ERA5
  calendar months. GRACE mid-month epochs are snapped to their calendar month
  and missing trailing months are forward-filled up to 2 months; filled months
  are flagged `grace_forward_filled: true` in the manifest so models can
  discount them.
- **Months ERA5 hasn't published yet** are skipped with a warning and picked
  up automatically on the next run.
- **Retries.** All HTTP and Earth Engine calls retry 3 times with exponential
  backoff (2 s → 4 s → 8 s).
- **Resampling.** GRACE (coarse → fine) is bilinearly interpolated in xarray;
  GEE sources (fine → coarse) are bilinear-resampled server-side and
  pyramid-aggregated to the 0.25° cell scale, so no native-resolution rasters
  are ever downloaded.
