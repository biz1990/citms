import pandas as pd
import io
import os
from datetime import datetime
from typing import List, Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.reports.repositories import ReportRepository
from backend.src.contexts.reports.schemas import ReportFilter
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from backend.src.core.i18n import get_language, get_dir, get_report_labels

class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReportRepository(db)

    async def generate_asset_inventory_report(self, filters: ReportFilter, data_scope: Any):
        """Generate asset inventory report and export to requested format."""
        data = await self.repo.get_asset_inventory(filters.dict(), data_scope)
        df = pd.DataFrame([
            {
                "Hostname": d.hostname,
                "Serial": d.serial_number,
                "Type": d.device_type,
                "Status": d.status,
                "Last Seen": d.last_seen.isoformat() if d.last_seen else "Never"
            } for d in data
        ])
        return self._export_dataframe(df, filters.format, "Asset_Inventory")

    async def generate_depreciation_report(self, filters: ReportFilter):
        """Generate asset depreciation report from Materialized View."""
        data = await self.repo.get_asset_depreciation_from_mv()
        df = pd.DataFrame([dict(r) for r in data])
        return self._export_dataframe(df, filters.format, "Asset_Depreciation")

    async def generate_software_usage_report(self, filters: ReportFilter):
        """Generate software usage report from Materialized View."""
        data = await self.repo.get_software_usage_top10_from_mv()
        df = pd.DataFrame([dict(r) for r in data])
        return self._export_dataframe(df, filters.format, "Software_Usage_Top10")

    async def generate_sla_performance_report(self, filters: ReportFilter, data_scope: Any):
        """Generate SLA performance report from Materialized View."""
        data = await self.repo.get_ticket_sla_stats_from_mv(data_scope)
        df = pd.DataFrame([dict(r) for r in data])
        return self._export_dataframe(df, filters.format, "Ticket_SLA_Stats")

    async def generate_offline_missing_report(self, filters: ReportFilter):
        """Generate offline/missing devices report from Materialized View."""
        data = await self.repo.get_offline_missing_devices_from_mv()
        df = pd.DataFrame([dict(r) for r in data])
        return self._export_dataframe(df, filters.format, "Offline_Missing_Devices")

    async def generate_license_expiration_report(self, filters: ReportFilter):
        """Generate license expiration report."""
        data = await self.repo.get_license_expiration_report()
        df = pd.DataFrame([dict(r) for r in data])
        return self._export_dataframe(df, filters.format, "License_Expiration")

    async def generate_audit_log_report(self, filters: ReportFilter):
        """Generate audit log report."""
        data = await self.repo.get_audit_log_report(filters.dict())
        df = pd.DataFrame([
            {
                "Timestamp": r.AuditLog.created_at.isoformat(),
                "User": r.full_name or "System",
                "Action": r.AuditLog.action,
                "Resource": r.AuditLog.resource_type,
                "Status": r.AuditLog.status
            } for r in data
        ])
        return self._export_dataframe(df, filters.format, "Audit_Log")

    async def generate_procurement_report(self, filters: ReportFilter):
        """Generate procurement report."""
        data = await self.repo.get_procurement_report(filters.dict())
        df = pd.DataFrame([
            {
                "PO Number": d.po_number,
                "Status": d.status,
                "Total Amount": d.total_amount,
                "Requested At": d.created_at.isoformat()
            } for d in data
        ])
        return self._export_dataframe(df, filters.format, "Procurement")

    async def generate_workflow_report(self, filters: ReportFilter):
        """Generate workflow report."""
        data = await self.repo.get_workflow_report(filters.dict())
        df = pd.DataFrame([
            {
                "Type": d.type,
                "Status": d.status,
                "Effective Date": d.effective_date.isoformat(),
                "Requested At": d.created_at.isoformat()
            } for d in data
        ])
        return self._export_dataframe(df, filters.format, "Workflow")

    async def generate_remote_session_report(self, filters: ReportFilter):
        """Generate remote session report."""
        data = await self.repo.get_remote_session_report(filters.dict())
        df = pd.DataFrame([
            {
                "Timestamp": r.AuditLog.created_at.isoformat(),
                "User": r.full_name,
                "Device ID": r.AuditLog.resource_id,
                "Status": r.AuditLog.status
            } for r in data
        ])
        return self._export_dataframe(df, filters.format, "Remote_Session")

    def _export_dataframe(self, df: pd.DataFrame, format: str, filename: str):
        """Export pandas DataFrame to requested format."""
        if format == "json":
            return df.to_dict(orient="records")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"{filename}_{timestamp}.{format}"
        
        if format == "csv":
            stream = io.StringIO()
            df.to_csv(stream, index=False)
            return StreamingResponse(
                io.BytesIO(stream.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={full_filename}"}
            )
            
        elif format == "xlsx":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Report')
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={full_filename}"}
            )
            
        elif format == "pdf":
            return self._render_pdf(df, filename, full_filename)
            
        raise HTTPException(status_code=400, detail="Unsupported export format")

    def _render_pdf(self, df: pd.DataFrame, title: str, filename: str):
        """Render DataFrame to PDF using WeasyPrint and Jinja2."""
        try:
            # Setup Jinja2 Environment
            template_dir = os.path.join(os.path.dirname(__file__), "../../templates/reports")
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template("base_report.html")
            
            # Prepare context data
            columns = df.columns.tolist()
            rows = df.values.tolist()
            
            # Render HTML string using Jinja2
            lang = get_language()
            layout_dir = get_dir()
            labels = get_report_labels()
            
            html_content = template.render(
                title=title.replace('_', ' ') + f" {labels['report']}",
                columns=columns,
                rows=rows,
                current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                lang=lang,
                dir=layout_dir,
                labels=labels
            )
            
            # Generate PDF using WeasyPrint
            pdf_file = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_file)
            pdf_file.seek(0)
            
            return StreamingResponse(
                pdf_file,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")
