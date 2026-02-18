from datetime import datetime, timezone
from typing import Optional

from src.domain.interfaces.repositories.experiment_repository_interface import ExperimentsRepositoryInterface
from src.domain.interfaces.repositories.metrics_repository_interface import MetricsRepositoryInterface
from src.domain.interfaces.repositories.reports_repository_interface import ReportsRepositoryInterface
from src.models.metrics import MetricType
from src.schemas.reports import (
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

        # GUARDRAIL метрики не считаются
        bound_metrics = [m for m in experiment.metrics if m.type != MetricType.GUARDRAIL]

        full_metrics = {}
        for bm in bound_metrics:
            full_metrics[bm.metric_id] = await self.metrics_repository.get(bm.metric_id)

        variant_info = {v.id: v for v in experiment.variants if v.name != "default"}

        # Подсчет subject_rows по варианту
        subject_rows = await self.reports_repository.count_subjects_per_variant(
            experiment_id, date_from, date_to
        )
        subject_counts: dict[str, int] = {row.variant_id: row.count for row in subject_rows}

        variant_metrics: dict[str, list[VariantMetricValue]] = {vid: [] for vid in variant_info}

        # Store raw numerators/denominators per metric per variant for totals computation
        raw_numerators: dict[str, dict[str, float | None]] = {}
        raw_denominators: dict[str, dict[str, float | None] | None] = {}

        for bm in bound_metrics:
            metric = full_metrics[bm.metric_id]

            numerator_rows = await self.reports_repository.compute_metric_summary(
                experiment_id=experiment_id,
                event_type=metric.event_type,
                aggregation=metric.aggregation.value,
                payload_field=metric.payload_field,
                date_from=date_from,
                date_to=date_to,
            )
            numerator_map: dict[str, float | None] = {
                row.variant_id: float(row.value) if row.value is not None else None
                for row in numerator_rows
            }
            raw_numerators[bm.metric_key] = numerator_map

            denominator_map: dict[str, float | None] | None = None
            if metric.denominator_event_type:
                denom_rows = await self.reports_repository.compute_metric_summary(
                    experiment_id=experiment_id,
                    event_type=metric.denominator_event_type,
                    aggregation=metric.denominator_aggregation.value,
                    payload_field=None,
                    date_from=date_from,
                    date_to=date_to,
                )
                denominator_map = {
                    row.variant_id: float(row.value) if row.value is not None else None
                    for row in denom_rows
                }
            raw_denominators[bm.metric_key] = denominator_map

            for vid in variant_info:
                num = numerator_map.get(vid)
                if denominator_map is not None:
                    denom = denominator_map.get(vid)
                    value = (num / denom) if (num is not None and denom) else None
                else:
                    value = num

                variant_metrics[vid].append(
                    VariantMetricValue(
                        metric_key=bm.metric_key,
                        metric_name=bm.metric_name,
                        value=value,
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

        # Compute totals across all non-default variants
        non_control_vids = [vid for vid, v in variant_info.items() if not v.is_control]
        total_metrics: list[VariantMetricValue] = []
        for bm in bound_metrics:
            num_sum = 0.0
            has_any = False
            for vid in non_control_vids:
                n = raw_numerators[bm.metric_key].get(vid)
                if n is not None:
                    num_sum += n
                    has_any = True

            denom_map = raw_denominators[bm.metric_key]
            if denom_map is not None:
                denom_sum = 0.0
                for vid in non_control_vids:
                    d = denom_map.get(vid)
                    if d is not None:
                        denom_sum += d
                value = (num_sum / denom_sum) if (has_any and denom_sum) else None
            else:
                value = num_sum if has_any else None

            total_metrics.append(
                VariantMetricValue(
                    metric_key=bm.metric_key,
                    metric_name=bm.metric_name,
                    value=value,
                )
            )

        total_non_control_subjects = sum(
            subject_counts.get(vid, 0) for vid in non_control_vids
        )
        totals = VariantReport(
            variant_id="total",
            variant_name="total",
            variant_value="",
            is_control=False,
            subject_count=total_non_control_subjects,
            metrics=total_metrics,
        )

        return ExperimentReport(
            experiment_id=experiment.id,
            experiment_name=experiment.name,
            date_from=date_from,
            date_to=date_to,
            total_subjects=total_subjects,
            variants=variants,
            totals=totals,
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

        full_metrics = {}
        for bm in bound_metrics:
            full_metrics[bm.metric_id] = await self.metrics_repository.get(bm.metric_id)

        variant_info = {v.id: v for v in experiment.variants if v.name != "default"}

        metric_timeseries_list: list[MetricTimeseries] = []

        for bm in bound_metrics:
            metric = full_metrics[bm.metric_id]

            numerator_rows = await self.reports_repository.compute_metric_timeseries(
                experiment_id=experiment_id,
                event_type=metric.event_type,
                aggregation=metric.aggregation.value,
                payload_field=metric.payload_field,
                granularity=granularity.value,
                date_from=date_from,
                date_to=date_to,
            )

            numerator_by_variant: dict[str, list[tuple]] = {vid: [] for vid in variant_info}
            for row in numerator_rows:
                if row.variant_id in numerator_by_variant:
                    numerator_by_variant[row.variant_id].append((row.bucket, row.value))

            denominator_by_variant: dict[str, dict] | None = None
            if metric.denominator_event_type:
                denom_rows = await self.reports_repository.compute_metric_timeseries(
                    experiment_id=experiment_id,
                    event_type=metric.denominator_event_type,
                    aggregation=metric.denominator_aggregation.value,
                    payload_field=None,
                    granularity=granularity.value,
                    date_from=date_from,
                    date_to=date_to,
                )
                denominator_by_variant = {vid: {} for vid in variant_info}
                for row in denom_rows:
                    if row.variant_id in denominator_by_variant:
                        denominator_by_variant[row.variant_id][row.bucket] = row.value

            variant_ts_list: list[VariantTimeseries] = []
            for vid, vinfo in variant_info.items():
                points: list[TimeseriesPoint] = []
                for bucket, num_value in numerator_by_variant.get(vid, []):
                    if denominator_by_variant is not None:
                        denom = denominator_by_variant.get(vid, {}).get(bucket)
                        value = (float(num_value) / float(denom)) if (num_value is not None and denom) else None
                    else:
                        value = float(num_value) if num_value is not None else None
                    points.append(TimeseriesPoint(timestamp=bucket, value=value))

                variant_ts_list.append(
                    VariantTimeseries(
                        variant_id=vid,
                        variant_name=vinfo.name,
                        is_control=vinfo.is_control,
                        points=points,
                    )
                )

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
