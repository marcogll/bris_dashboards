import os
import time
import logging
import pandas as pd
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://umzlwcdjxtbdoqiclolo.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
CACHE_TTL = int(os.getenv("DATA_CACHE_TTL", "300"))

RAW_DATA_PATH = os.path.join(os.path.dirname(__file__), "all-data.csv")

SUPABASE_TO_DASHBOARD = {
    "ref_cita": "ref_cita",
    "client_name": "cliente",
    "staff_name": "miembro_equipo",
    "resource": "recurso",
    "status": "estado",
    "created_at_source": "creada_el_dia",
    "scheduled_at": "fecha_programada",
    "cancelled_at": "fecha_cancelacion",
    "category": "categoria",
    "service": "servicio",
    "duration_original": "duracion_original",
    "time_slot": "franja_horaria",
    "created_by": "creada_por",
    "cancelled_by": "cancelado_por",
    "center_name": "centro",
    "net_sales": "ventas_netas",
    "cancellation_reason": "motivo_cancelacion",
    "surcharges": "recargos_aplicados",
    "prepayments": "pagos_adelantado",
    "duration_minutes": "tiempo_minutos",
    "branch_code": "centro_codigo",
    "staff_normalized_name": "miembro_equipo_normalizado",
}

CATEGORY_MAP = {
    "💅MANOS": "Manos",
    "🦶🌸  PIES": "Pies",
    "✨ PESTAÑAS": "Pestañas",
    "✨CEJAS Y ROSTRO": "Cejas Y Rostro",
    "💄 MAKEUP & HAIR": "Makeup & Hair",
    "💆‍♀️ HAIR TREATMENTS": "Hair Treatments",
    "Aniversario Cima": "Manos",
    "ANIVERSARIO CIMA": "Manos",
    "Microblading": "Cejas Y Rostro",
    "💎 BODY/RELAX": "Body/Relax",
}

SERVICE_MAP = {
    "GELISH PARTY": "Gelish",
    "GELISH PARTY  (open house)": "Gelish",
    "HAPPY MONDAY (gelish manos)": "Gelish",
    "HAPPY WEDNESDAY (retoque de acrílico)": "Nail Refill ",
    "Acrylic Allure (Retoque de Acrílico + Gel) - 10% OFF": "Nail Refill ",
    "POLYGEL POWER DUO (baño de polygel)": "Polygel Extensions",
    "BASE RUUBER + GELISH": "Base rubber ",
    "UÑAS ACRILICAS": " Acrylic Extensions",
    "PERFECT LOOK (lash lifting + serum)": "Lash Lifting",
    "EXTENSONES DE PESTAÑAS": "Extensión de Pestañas (Elegant Lashes)",
    "CORTE SPA + TRATAMIENTO": "Corte SPA",
    "MASAJE RELAJANTE PROMO": "Masaje Relajante ",
}

PROMOTION_SERVICE_CATEGORIES = {
    "MANI + PEDI DELUXE": "Pies",
    "MANI + PEDI CLASSIC": "Pies",
    "UÑAS PRESS ON": "Manos",
    "GELISH MANOS Y PIES": "Pies",
}

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

SEASONS = {
    1: "Invierno",
    2: "Invierno",
    3: "Primavera",
    4: "Primavera",
    5: "Primavera",
    6: "Verano",
    7: "Verano",
    8: "Verano",
    9: "Otoño",
    10: "Otoño",
    11: "Otoño",
    12: "Invierno",
}


class SupabaseDataLoader:
    def __init__(self, url=None, key=None, ttl=None):
        self.url = url or SUPABASE_URL
        self.key = key or SUPABASE_ANON_KEY
        self.ttl = ttl if ttl is not None else CACHE_TTL
        self._client = None
        self._cache = None
        self._cache_ts = 0.0

    @property
    def client(self) -> Client:
        if self._client is None:
            if not self.key:
                raise ValueError("SUPABASE_ANON_KEY is required")
            self._client = create_client(self.url, self.key)
        return self._client

    def _fetch_all(self, table: str) -> list[dict]:
        rows = []
        offset = 0
        page_size = 1000
        while True:
            resp = (
                self.client.table(table)
                .select("*")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            data = resp.data or []
            rows.extend(data)
            if len(data) < page_size:
                break
            offset += page_size
        return rows

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = {sb: dash for sb, dash in SUPABASE_TO_DASHBOARD.items() if sb in df.columns}
        return df.rename(columns=mapping)

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        dt_cols = ["creada_el_dia", "fecha_programada", "fecha_cancelacion"]
        for c in dt_cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")

        if "categoria" in df.columns:
            df["categoria"] = df["categoria"].replace(CATEGORY_MAP)
        if "servicio" in df.columns:
            df["servicio"] = df["servicio"].replace(SERVICE_MAP)

        if "servicio" in df.columns and "categoria" in df.columns:
            df["categoria"] = (
                df["servicio"]
                .str.strip()
                .map(PROMOTION_SERVICE_CATEGORIES)
                .fillna(df["categoria"])
            )
            promo_mask = df["servicio"].str.contains("promo|paquete", case=False, na=False)
            df.loc[promo_mask, "categoria"] = df["servicio"].map({
                "Gelish": "Manos",
                "Nail Refill ": "Manos",
                "Polygel Extensions": "Manos",
                "Base rubber ": "Manos",
                " Acrylic Extensions": "Manos",
                "Lash Lifting": "Pestañas",
                "Extensión de Pestañas (Elegant Lashes)": "Pestañas",
                "Corte SPA": "Hair Treatments",
                "Masaje Relajante ": "Body/Relax",
            }).fillna(df["categoria"])
            df.loc[
                df["servicio"].str.contains(r"^Retiro de uñas", case=False, na=False),
                "categoria",
            ] = "Retiros"

        if "ventas_netas" in df.columns:
            df["ventas_netas"] = pd.to_numeric(df["ventas_netas"], errors="coerce").fillna(0)
        if "recargos_aplicados" in df.columns:
            df["recargos_aplicados"] = pd.to_numeric(df["recargos_aplicados"], errors="coerce").fillna(0)
        if "pagos_adelantado" in df.columns:
            df["pagos_adelantado"] = pd.to_numeric(df["pagos_adelantado"], errors="coerce").fillna(0)

        if "tiempo_minutos" not in df.columns and "duracion_original" in df.columns:
            df["tiempo_minutos"] = pd.to_numeric(df["duracion_original"], errors="coerce").fillna(0)
        elif "tiempo_minutos" in df.columns:
            df["tiempo_minutos"] = pd.to_numeric(df["tiempo_minutos"], errors="coerce").fillna(0)

        scheduled = df.get("fecha_programada")
        if scheduled is not None:
            df["tiempo_anio"] = scheduled.dt.year.astype("Int64")
            df["tiempo_mes_num"] = scheduled.dt.month.astype("Int64")
            df["tiempo_mes"] = df["tiempo_mes_num"].map(MONTH_NAMES)
            df["tiempo_semana"] = scheduled.dt.isocalendar().week.astype("Int64")
            df["tiempo_temporada"] = df["tiempo_mes_num"].map(SEASONS)

        return df

    def load_sales(self) -> pd.DataFrame:
        if self._cache is not None and (time.time() - self._cache_ts) < self.ttl:
            return self._cache

        try:
            rows = self._fetch_all("sales_appointments")
            df = pd.DataFrame(rows)
            df = self._rename_columns(df)
            df = self._normalize(df)
            self._cache = df
            self._cache_ts = time.time()
            logger.info("Loaded %d rows from Supabase", len(df))
            return df
        except Exception:
            logger.warning("Supabase unreachable, falling back to CSV", exc_info=True)
            return self._fallback_csv()

    def _fallback_csv(self) -> pd.DataFrame:
        from app import normalize_sales_data
        return normalize_sales_data(RAW_DATA_PATH)

    def invalidate(self):
        self._cache = None
        self._cache_ts = 0.0


_loader: SupabaseDataLoader | None = None


def _get_loader() -> SupabaseDataLoader:
    global _loader
    if _loader is None:
        _loader = SupabaseDataLoader()
    return _loader


def get_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _get_loader().load_sales()
    status_col = "estado" if "estado" in df.columns else "status"
    latest = df[df[status_col].str.lower().isin(["completadas", "completed"])] if status_col in df.columns else df
    return df, latest