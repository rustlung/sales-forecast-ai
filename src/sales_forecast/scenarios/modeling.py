from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from sales_forecast.database.models import SalesRecord

NUMERIC = ["price", "discount_pct", "ad_spend", "weekday", "month"]
CATEGORICAL = ["product", "category", "promo"]
FEATURES = [*NUMERIC, *CATEGORICAL]


class ScenarioValidationError(Exception): pass


@dataclass(frozen=True)
class ScenarioInput:
    product: str
    category: str
    date: date
    price: float
    discount_pct: float
    ad_spend: float
    promo: bool

    def validate(self, frame: pd.DataFrame) -> None:
        if self.price <= 0: raise ScenarioValidationError("price must be greater than 0")
        if not 0 <= self.discount_pct <= 100: raise ScenarioValidationError("discount_pct must be between 0 and 100")
        if self.ad_spend < 0: raise ScenarioValidationError("ad_spend must be non-negative")
        pairs = set(zip(frame["product"], frame["category"], strict=True))
        if (self.product, self.category) not in pairs:
            raise ScenarioValidationError("product/category pair is not present in this dataset")

    def row(self) -> dict[str, object]:
        return {"product": self.product, "category": self.category, "price": self.price, "discount_pct": self.discount_pct,
                "ad_spend": self.ad_spend, "promo": self.promo, "weekday": self.date.weekday(), "month": self.date.month, "date": self.date.isoformat()}


def prepare_ml_frame(records: list[SalesRecord]) -> pd.DataFrame:
    frame = pd.DataFrame([{"date": r.date, "product": r.product, "category": r.category, "price": float(r.price),
        "discount_pct": float(r.discount_pct), "ad_spend": float(r.ad_spend), "promo": bool(r.promo), "revenue": float(r.revenue)} for r in records])
    if frame.empty: raise ScenarioValidationError("dataset has no sales records")
    frame["date"] = pd.to_datetime(frame["date"])
    frame["weekday"] = frame.date.dt.weekday
    frame["month"] = frame.date.dt.month
    return frame.sort_values("date").reset_index(drop=True)


def chronological_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(frame.date.unique())
    cut = max(1, math.floor(len(dates) * 0.8))
    if len(dates) - cut < 1: raise ScenarioValidationError("not enough distinct dates for chronological test split")
    boundary = dates[cut]
    return frame[frame.date < boundary].copy(), frame[frame.date >= boundary].copy()


def build_pipeline() -> Pipeline:
    preprocessing = ColumnTransformer([("numeric", "passthrough", NUMERIC), ("category", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL)])
    return Pipeline([("preprocess", preprocessing), ("model", RandomForestRegressor(n_estimators=200, random_state=42, min_samples_leaf=2, n_jobs=1))])


def train_and_evaluate(frame: pd.DataFrame) -> tuple[Pipeline, dict[str, float | None], dict[str, str], pd.DataFrame, pd.DataFrame]:
    train, test = chronological_split(frame)
    pipeline = build_pipeline().fit(train[FEATURES], train.revenue)
    predicted = pipeline.predict(test[FEATURES]).clip(min=0)
    metrics = {"mae": float(mean_absolute_error(test.revenue, predicted)), "rmse": float(mean_squared_error(test.revenue, predicted) ** 0.5), "r2": _finite(r2_score(test.revenue, predicted))}
    names = pipeline.named_steps["preprocess"].get_feature_names_out()
    importances = pipeline.named_steps["model"].feature_importances_
    importance = {str(name): float(value) for name, value in sorted(zip(names, importances, strict=True), key=lambda item: item[1], reverse=True)}
    return pipeline, metrics, importance, train, test


def baseline_for(frame: pd.DataFrame, scenario: ScenarioInput) -> ScenarioInput:
    rows = frame[(frame["product"] == scenario.product) & (frame["category"] == scenario.category)].sort_values("date")
    latest = rows.iloc[-1]
    return ScenarioInput(scenario.product, scenario.category, scenario.date, float(latest.price), float(latest.discount_pct), float(latest.ad_spend), bool(latest.promo))


def predict(pipeline: Pipeline, scenario: ScenarioInput) -> float:
    return max(0.0, float(pipeline.predict(pd.DataFrame([scenario.row()])[FEATURES])[0]))


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None
