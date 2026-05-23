import csv
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, Response, flash, redirect, render_template, request, send_file, url_for


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(os.getenv("DATA_FILE", BASE_DIR / "data" / "stations.csv"))
AVAILABLE_SECONDS = float(os.getenv("AVAILABLE_SECONDS", "39900"))
TAKT_SECONDS = float(os.getenv("TAKT_SECONDS", "2216.666667"))
APP_TITLE = os.getenv("APP_TITLE", "Rack Assembly Dashboard")
UPLOAD_SECRET = os.getenv("UPLOAD_SECRET", "")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "local-dev-change-me")


@dataclass
class Station:
    station_id: str
    station_name: str
    time_seconds: float
    operators: float
    observations: str
    action: str

    @property
    def capacity_per_hour(self) -> float:
        if self.time_seconds <= 0:
            return 0
        return self.operators * 3600 / self.time_seconds

    @property
    def work_minutes(self) -> float:
        return self.time_seconds / 60

    @property
    def effective_cycle_seconds(self) -> float:
        if self.operators <= 0:
            return self.time_seconds
        return self.time_seconds / self.operators


def as_float(value: str, default: float = 0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def read_stations() -> list[Station]:
    if not DATA_FILE.exists():
        return []

    with DATA_FILE.open(newline="", encoding="utf-8-sig") as file:
        rows = csv.DictReader(file)
        stations = []
        for row in rows:
            station_name = (row.get("station_name") or row.get("station") or "").strip()
            if not station_name:
                continue
            stations.append(
                Station(
                    station_id=(row.get("station_id") or str(len(stations) + 1)).strip(),
                    station_name=station_name,
                    time_seconds=as_float(row.get("time_seconds")),
                    operators=as_float(row.get("operators"), 1),
                    observations=(row.get("observations") or "").strip(),
                    action=(row.get("action") or "").strip(),
                )
            )
    return stations


def build_metrics(stations: list[Station]) -> dict[str, Any]:
    if not stations:
        return {
            "stations": [],
            "bottleneck": None,
            "total_work_seconds": 0,
            "target_units": AVAILABLE_SECONDS / TAKT_SECONDS,
            "actual_units": 0,
            "gap_units": 0,
            "scenario": None,
            "max_capacity": 0,
        }

    total_work_seconds = sum(station.time_seconds for station in stations)
    target_units = AVAILABLE_SECONDS / TAKT_SECONDS if TAKT_SECONDS else 0
    bottleneck = min(stations, key=lambda station: station.capacity_per_hour)
    actual_units = bottleneck.capacity_per_hour * AVAILABLE_SECONDS / 3600
    gap_units = target_units - actual_units
    max_capacity = max(station.capacity_per_hour for station in stations)

    enriched = []
    for station in stations:
        work_share = station.time_seconds / total_work_seconds * 100 if total_work_seconds else 0
        takt_gap = station.time_seconds - TAKT_SECONDS
        status = "critical" if station == bottleneck else "warning" if takt_gap > 0 else "ok"
        enriched.append(
            {
                "raw": station,
                "work_share": work_share,
                "takt_gap": takt_gap,
                "status": status,
                "bar_width": station.capacity_per_hour / max_capacity * 100 if max_capacity else 0,
            }
        )

    scenario = best_one_operator_rebalance(stations)

    return {
        "stations": enriched,
        "bottleneck": bottleneck,
        "total_work_seconds": total_work_seconds,
        "target_units": target_units,
        "actual_units": actual_units,
        "gap_units": gap_units,
        "scenario": scenario,
        "max_capacity": max_capacity,
    }


def best_one_operator_rebalance(stations: list[Station]) -> dict[str, Any] | None:
    if len(stations) < 2:
        return None

    current_bottleneck = min(stations, key=lambda station: station.capacity_per_hour)
    current_units = current_bottleneck.capacity_per_hour * AVAILABLE_SECONDS / 3600
    best = None

    for donor in stations:
        if donor.station_id == current_bottleneck.station_id or donor.operators <= 1:
            continue

        simulated = []
        for station in stations:
            operators = station.operators
            if station.station_id == donor.station_id:
                operators -= 1
            if station.station_id == current_bottleneck.station_id:
                operators += 1
            capacity = operators * 3600 / station.time_seconds if station.time_seconds > 0 else 0
            simulated.append((station, operators, capacity))

        new_bottleneck, _, new_capacity = min(simulated, key=lambda item: item[2])
        new_units = new_capacity * AVAILABLE_SECONDS / 3600
        improvement = new_units - current_units
        if improvement > 0 and (best is None or improvement > best["improvement_units"]):
            best = {
                "from_station": donor,
                "to_station": current_bottleneck,
                "new_bottleneck": new_bottleneck,
                "new_units": new_units,
                "improvement_units": improvement,
                "new_capacity": new_capacity,
            }

    return best


@app.template_filter("num")
def format_number(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}"


@app.route("/")
def dashboard() -> str:
    stations = read_stations()
    metrics = build_metrics(stations)
    return render_template(
        "dashboard.html",
        title=APP_TITLE,
        data_file=DATA_FILE,
        available_seconds=AVAILABLE_SECONDS,
        takt_seconds=TAKT_SECONDS,
        metrics=metrics,
    )


@app.route("/data.csv")
def download_csv() -> Response:
    if not DATA_FILE.exists():
        return Response("CSV no encontrado\n", status=404, mimetype="text/plain")
    return send_file(DATA_FILE, as_attachment=True, download_name="stations.csv")


@app.route("/upload", methods=["POST"])
def upload_csv() -> Response:
    if UPLOAD_SECRET and request.form.get("upload_secret") != UPLOAD_SECRET:
        flash("Clave de actualización inválida.", "danger")
        return redirect(url_for("dashboard"))

    uploaded = request.files.get("csv_file")
    if not uploaded or not uploaded.filename.endswith(".csv"):
        flash("Sube un archivo CSV válido.", "danger")
        return redirect(url_for("dashboard"))

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup = DATA_FILE.with_suffix(".backup.csv")
    if DATA_FILE.exists():
        shutil.copyfile(DATA_FILE, backup)
    uploaded.save(DATA_FILE)
    flash("CSV actualizado. El dashboard ya está usando la nueva data.", "success")
    return redirect(url_for("dashboard"))


@app.route("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
