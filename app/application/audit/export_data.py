import csv
import io
from datetime import datetime
from uuid import UUID

import structlog

from app.domain.audit.repository import IAuditRepository

logger = structlog.get_logger()


class ExportData:
    def __init__(self, audit_repository: IAuditRepository) -> None:
        self.audit_repository = audit_repository

    async def execute(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "csv",
    ) -> tuple[str, str]:
        logs = await self.audit_repository.list_by_date_range(
            start_date=start_date,
            end_date=end_date,
            skip=0,
            limit=10000,
        )

        if format == "csv":
            content = self._export_csv(logs)
            content_type = "text/csv"
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(
            "audit_data_exported",
            count=len(logs),
            format=format,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        return content, content_type

    def _export_csv(self, logs) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "ID",
            "User ID",
            "Action Type",
            "Resource Type",
            "Resource ID",
            "Details",
            "IP Address",
            "User Agent",
            "Timestamp",
        ])

        for log in logs:
            writer.writerow([
                str(log.id),
                str(log.user_id) if log.user_id else "",
                log.action_type.value,
                log.resource_type,
                str(log.resource_id) if log.resource_id else "",
                str(log.details),
                log.ip_address or "",
                log.user_agent or "",
                log.timestamp.isoformat(),
            ])

        return output.getvalue()
