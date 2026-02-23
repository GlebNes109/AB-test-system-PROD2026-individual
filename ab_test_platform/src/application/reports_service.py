from datetime import datetime, timezone
from typing import Optional

from ab_test_platform.src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.metrics_repository_interface import MetricsRepositoryInterface
from ab_test_platform.src.domain.interfaces.repositories.reports_repository_interface import ReportsRepositoryInterface
from ab_test_platform.src.models.metrics import MetricType
from ab_test_platform.src.schemas.reports import (
    ExperimentReport,
    VariantReport,
    VariantMetricValue,
    ExperimentTimeseriesReport,
    MetricTimeseries,
    VariantTimeseries,
    TimeseriesPoint,
    Granularity,
)


class ReportsService:
    def __init__(
        self,
        reports_repository: ReportsRepositoryInterface,
        experiment_repository: ExperimentsRepositoryInterface,
        metrics_repository: MetricsRepositoryInterface,
    ):
        self.reports_repository = reports_repository
        self.experiment_repository = experiment_repository
        self.metrics_repository = metrics_repository

    async def get_summary_report(
        self,
        experiment_id: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> ExperimentReport:
        experiment = await self.experiment_repository.get(experiment_id)

        if date_from is None:
            date_from = experiment.started_at or experiment.created_at
        if date_to is None:
            date_to = datetime.now(timezone.utc)

        # GUARDRAIL метрики не считаются в отчёте
        bound_metrics = [m for m in experiment.metrics if m.type != MetricType.GUARDRAIL]

        variant_info = {v.id: v for v in experiment.variants}

        subject_rows = await self.reports_repository.count_subjects_per_variant(
            experiment_id, date_from, date_to
        )
        subject_counts: dict[str, int] = {row.variant_id: row.count for row in subject_rows}

        variant_metrics: dict[str, list[VariantMetricValue]] = {vid: [] for vid in variant_info}

        # value_num/value_denom per metric key - для подсчёта корректных итогов по ratio-метрикам
        totals_num: dict[str, float] = {}
        totals_denom: dict[str, Optional[float]] = {}
        totals_has_denom: dict[str, bool] = {}

        for bm in bound_metrics:
            rows = await self.reports_repository.compute_metric_summary(
                experiment_id=experiment_id,
                metric_key=bm.metric_key,
                date_from=date_from,
                date_to=date_to,
            )

            values_by_variant: dict[str, Optional[float]] = {
                row.variant_id: (float(row.value) if row.value is not None else None)
                for row in rows
            }
            num_by_variant: dict[str, Optional[float]] = {
                row.variant_id: (float(row.value_num) if row.value_num is not None else None)
                for row in rows
            }
            denom_by_variant: dict[str, Optional[float]] = {
                row.variant_id: (float(row.value_denom) if row.value_denom is not None else None)
                for row in rows
            }

            has_denom = any(v is not None for v in denom_by_variant.values())
            totals_has_denom[bm.metric_key] = has_denom

            total_num = sum(v for v in num_by_variant.values() if v is not None)
            totals_num[bm.metric_key] = total_num

            if has_denom:
                total_denom = sum(v for v in denom_by_variant.values() if v is not None)
                totals_denom[bm.metric_key] = total_denom
            else:
                totals_denom[bm.metric_key] = None

            for vid in variant_info:
                variant_metrics[vid].append(
                    VariantMetricValue(
                        metric_key=bm.metric_key,
                        metric_name=bm.metric_name,
                        value=values_by_variant.get(vid),
                    )
                )

        total_subjects = sum(subject_counts.get(vid, 0) for vid in variant_info)

        variants = [
            VariantReport(
                variant_id=v.id,
                variant_name=v.name,
                variant_value=v.value,
                is_control=v.is_control,
                subject_count=subject_counts.get(v.id, 0),
                metrics=variant_metrics.get(v.id, []),
            )
            for v in variant_info.values()
        ]

        total_metrics: list[VariantMetricValue] = []
        for bm in bound_metrics:
            num = totals_num.get(bm.metric_key, 0.0)
            denom = totals_denom.get(bm.metric_key)
            if totals_has_denom.get(bm.metric_key):
                value = (num / denom) if denom else None
            else:
                value = num if num else None

            total_metrics.append(
                VariantMetricValue(
                    metric_key=bm.metric_key,
                    metric_name=bm.metric_name,
                    value=value,
                )
            )

        return ExperimentReport(
            experiment_id=experiment.id,
            experiment_name=experiment.name,
            date_from=date_from,
            date_to=date_to,
            total_subjects=total_subjects,
            variants=variants,
            total_metrics=total_metrics,
        )

    async def get_timeseries_report(
        self,
        experiment_id: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        granularity: Granularity,
    ) -> ExperimentTimeseriesReport:
        experiment = await self.experiment_repository.get(experiment_id)

        if date_from is None:
            date_from = experiment.started_at or experiment.created_at
        if date_to is None:
            date_to = datetime.now(timezone.utc)

        bound_metrics = [m for m in experiment.metrics if m.type != MetricType.GUARDRAIL]

        variant_info = {v.id: v for v in experiment.variants if v.name != "default"}

        metric_timeseries_list: list[MetricTimeseries] = []

        for bm in bound_metrics:
            rows = await self.reports_repository.compute_metric_timeseries(
                experiment_id=experiment_id,
                metric_key=bm.metric_key,
                granularity=granularity.value,
                date_from=date_from,
                date_to=date_to,
            )

            # Группируем строки по variant_id
            points_by_variant: dict[str, list[TimeseriesPoint]] = {vid: [] for vid in variant_info}
            for row in rows:
                if row.variant_id not in points_by_variant:
                    continue
                points_by_variant[row.variant_id].append(
                    TimeseriesPoint(
                        bucket_start=row.bucket_start,
                        bucket_end=row.bucket_end,
                        value=float(row.value) if row.value is not None else None,
                    )
                )

            variant_ts_list: list[VariantTimeseries] = [
                VariantTimeseries(
                    variant_id=vid,
                    variant_name=vinfo.name,
                    is_control=vinfo.is_control,
                    points=points_by_variant.get(vid, []),
                )
                for vid, vinfo in variant_info.items()
            ]

            metric_timeseries_list.append(
                MetricTimeseries(
                    metric_key=bm.metric_key,
                    metric_name=bm.metric_name,
                    variants=variant_ts_list,
                )
            )

        return ExperimentTimeseriesReport(
            experiment_id=experiment.id,
            experiment_name=experiment.name,
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
            metrics=metric_timeseries_list,
        )
