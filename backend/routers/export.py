"""Export endpoints: CSV time series and a PDF district report.

Both matplotlib and ReportLab are synchronous, CPU-bound libraries. The PDF
is therefore rendered via ``anyio.to_thread.run_sync`` so a report request
never stalls the event loop for other clients. The matplotlib backend is
forced to "Agg" *before* pyplot is imported -- on a server there is no
display, and the default backend selection can fail or leak GUI handles.
"""

import csv
import io
import re
from datetime import date
from functools import partial

import anyio
import matplotlib

matplotlib.use("Agg")  # must precede the pyplot import
import matplotlib.pyplot as plt  # noqa: E402
from dateutil.relativedelta import relativedelta  # noqa: E402
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status  # noqa: E402
from fastapi.responses import Response, StreamingResponse  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from core.database import get_db  # noqa: E402
from core.queries import (  # noqa: E402
    _DISTRICT_WEIGHTS_SQL,
    district_current_risk,
    district_exists,
    district_forecast,
    district_top_cells,
    latest_observed_month,
)
from core.ratelimit import EXPORT_RATE_LIMIT, limiter  # noqa: E402
from core.scoring import (  # noqa: E402
    EXPORT_HISTORY_MONTHS,
    FORECAST_HORIZON_MONTHS,
    risk_level,
)

router = APIRouter(prefix="/export", tags=["export"])

_CSV_SQL = text(f"""
    SELECT w.cell_code AS cell_code,
           c.centroid_lat AS centroid_lat,
           c.centroid_lon AS centroid_lon,
           rs.month AS month,
           rs.risk AS risk
    FROM ({_DISTRICT_WEIGHTS_SQL}) w
    JOIN grid_cells c ON c.id = w.cell_id
    JOIN risk_scores rs
      ON rs.cell_id = w.cell_id
     AND rs.score_type = 'observed'
     AND rs.month >= :cutoff
    ORDER BY w.cell_code, rs.month
""")


def _safe_filename(district: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", district).strip("_") or "district"


async def _require_district_and_month(
    db: AsyncSession, district_name: str
) -> date:
    if not await district_exists(db, district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {district_name}"
        )
    month = await latest_observed_month(db)
    if month is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No risk scores available yet -- run the monthly pipeline first.",
        )
    return month


@router.get(
    "/csv/{district_name}",
    summary="CSV of the last 24 months of risk scores",
    description=(
        "Streams one row per (cell, month) for every grid cell intersecting "
        "the district: cell_id, centroid, month, well_failure_risk, "
        "risk_level. Covers the 24 months up to the latest scored month."
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
@limiter.limit(EXPORT_RATE_LIMIT)
async def export_csv(
    request: Request,  # required by slowapi to key the client IP
    district_name: str = Path(description="District name as stored in `districts`."),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    latest = await _require_district_and_month(db, district_name)
    cutoff = latest - relativedelta(months=EXPORT_HISTORY_MONTHS - 1)
    rows = (
        await db.execute(_CSV_SQL, {"district": district_name, "cutoff": cutoff})
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["cell_id", "centroid_lat", "centroid_lon", "month",
         "well_failure_risk", "risk_level"]
    )
    for row in rows:
        writer.writerow(
            [
                row.cell_code,
                row.centroid_lat,
                row.centroid_lon,
                row.month.strftime("%Y-%m"),
                f"{row.risk:.2f}",
                risk_level(row.risk),
            ]
        )
    buffer.seek(0)
    filename = f"aquasignal_{_safe_filename(district_name)}_{latest:%Y-%m}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_forecast_chart(
    months: list[str], predicted: list[float], lows: list[float], highs: list[float]
) -> bytes:
    """Matplotlib line chart with the ensemble CI band, as PNG bytes."""
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=150)
    try:
        ax.fill_between(
            months, lows, highs, alpha=0.25, color="#2b7bba",
            label="80% ensemble interval",
        )
        ax.plot(months, predicted, marker="o", color="#1b4f72", label="Predicted risk")
        ax.set_ylim(0, 100)
        ax.set_ylabel("Well-failure risk")
        ax.set_title("6-month forecast")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
        fig.tight_layout()
        png = io.BytesIO()
        fig.savefig(png, format="png")
        return png.getvalue()
    finally:
        plt.close(fig)  # matplotlib leaks figures that are never closed


def _build_pdf(
    district_name: str,
    month_label: str,
    avg_risk: float | None,
    forecast_rows: list[tuple[str, float, float, float]],
    top_cells: list[tuple[str, float, float, float]],
) -> bytes:
    """Compose the report with ReportLab platypus. Pure CPU -- run in a thread."""
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, title=f"AquaSignal report -- {district_name}"
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"AquaSignal groundwater risk report: {district_name}",
                  styles["Title"]),
        Paragraph(f"Reporting month: {month_label}", styles["Normal"]),
        Spacer(1, 0.4 * cm),
    ]

    if avg_risk is not None:
        story.append(
            Paragraph(
                f"Current district risk (area-weighted): <b>{avg_risk:.1f}/100</b> "
                f"({risk_level(avg_risk)})",
                styles["Heading2"],
            )
        )
    else:
        story.append(
            Paragraph("No current risk scores for this district.", styles["Heading2"])
        )
    story.append(Spacer(1, 0.4 * cm))

    if forecast_rows:
        months = [r[0] for r in forecast_rows]
        chart_png = _render_forecast_chart(
            months,
            [r[1] for r in forecast_rows],
            [r[2] for r in forecast_rows],
            [r[3] for r in forecast_rows],
        )
        story.append(Image(io.BytesIO(chart_png), width=16 * cm, height=7.5 * cm))
    else:
        story.append(Paragraph("No forecast available.", styles["Normal"]))
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Highest-risk grid cells", styles["Heading2"]))
    if top_cells:
        table_data = [["Cell", "Centroid (lat, lon)", "Risk", "Level"]] + [
            [code, f"{lat:.3f}, {lon:.3f}", f"{risk:.1f}", risk_level(risk)]
            for code, lat, lon, risk in top_cells
        ]
        table = Table(table_data, colWidths=[4.5 * cm, 5 * cm, 2.5 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4f72")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#eef3f7")]),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No scored cells in this district.", styles["Normal"]))

    doc.build(story)
    return output.getvalue()


@router.get(
    "/pdf/{district_name}",
    summary="PDF district report",
    description=(
        "One-page report: current area-weighted district risk, the 6-month "
        "forecast chart with confidence band, and the three highest-risk "
        "cells. Rendered with ReportLab + matplotlib in a worker thread."
    ),
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
@limiter.limit(EXPORT_RATE_LIMIT)
async def export_pdf(
    request: Request,  # required by slowapi to key the client IP
    district_name: str = Path(description="District name as stored in `districts`."),
    db: AsyncSession = Depends(get_db),
) -> Response:
    latest = await _require_district_and_month(db, district_name)

    avg_risk = await district_current_risk(db, district_name, latest)
    forecast = await district_forecast(
        db, district_name, after_month=latest, limit=FORECAST_HORIZON_MONTHS
    )
    top = await district_top_cells(db, district_name, latest, limit=3)

    forecast_rows = [
        (r.month.strftime("%Y-%m"), float(r.predicted_risk),
         float(r.ci_low), float(r.ci_high))
        for r in forecast
    ]
    top_cells = [
        (r.cell_code, float(r.centroid_lat), float(r.centroid_lon), float(r.risk))
        for r in top
    ]

    pdf_bytes = await anyio.to_thread.run_sync(
        partial(
            _build_pdf,
            district_name,
            latest.strftime("%Y-%m"),
            avg_risk,
            forecast_rows,
            top_cells,
        )
    )
    filename = f"aquasignal_{_safe_filename(district_name)}_{latest:%Y-%m}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
