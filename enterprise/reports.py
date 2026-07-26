"""
Report Generator for Enterprise Predictive Maintenance Platform

Generates daily, weekly, monthly, machine, category, maintenance, and prediction reports.
Reuses analytics engine and existing data.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, time
from dataclasses import asdict

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
for path in (str(PACKAGE_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from models import (
    MachineInfo, MachineStatus, MachineType, Report,
    MaintenanceLog, MaintenanceType, Alert, AlertSeverity,
    WorkOrder, WorkOrderStatus
)
from analytics import AnalyticsEngine, get_analytics_engine
from services import get_data_store


class ReportGenerator:
    """
    Generates comprehensive reports for the enterprise platform.
    All reports are generated from in-memory data and analytics.
    """

    def __init__(self):
        self.analytics = get_analytics_engine()
        self.data_store = get_data_store()
        self._report_counter = 0

    def _generate_id(self, report_type: str) -> str:
        """Generate a unique report ID."""
        self._report_counter += 1
        return f"RPT-{report_type.upper()}-{self._report_counter:04d}"

    def _get_simulator(self):
        """Get simulator instance."""
        from simulation import EnterpriseSimulator
        return EnterpriseSimulator()

    def _report_from_dict(self, data: Dict[str, Any]) -> Report:
        """Rehydrate a stored report dictionary."""
        generated_at = data.get("generated_at", datetime.now().isoformat())
        return Report(
            report_id=data.get("report_id", ""),
            report_type=data.get("report_type", ""),
            title=data.get("title", "Report"),
            generated_at=datetime.fromisoformat(generated_at),
            data=data.get("data", {}),
            generated_by=data.get("generated_by", "AI System")
        )

    def _save_report_once(self, report: Report) -> Report:
        """Save a report only once per report type/title."""
        for existing in self.data_store.generated_reports:
            if (
                existing.get("report_type") == report.report_type and
                existing.get("title") == report.title
            ):
                return self._report_from_dict(existing)
        self.data_store.generated_reports.append(report.to_dict())
        return report

    def _machine_recommendation(self, machine: MachineInfo) -> str:
        """Generate a concise maintenance recommendation."""
        if machine.status == MachineStatus.CRITICAL:
            return "Immediate corrective maintenance required."
        if machine.status == MachineStatus.WARNING:
            return "Schedule preventive maintenance and monitor closely."
        if machine.failure_probability > 0.5:
            return "Review predictive maintenance plan due to elevated failure risk."
        return "Continue routine monitoring."

    def _top_risk_machines(self, machines: List[MachineInfo], limit: int = 10) -> List[Dict[str, Any]]:
        """Return highest-risk machines in a report-friendly shape."""
        rows = []
        for machine in sorted(machines, key=lambda m: m.failure_probability, reverse=True)[:limit]:
            rows.append({
                "machine_id": machine.machine_id,
                "machine_name": machine.name,
                "category": machine.machine_category,
                "health_score": machine.health_score,
                "status": machine.status.value,
                "failure_probability": round(machine.failure_probability * 100, 1),
                "recommendation": self._machine_recommendation(machine)
            })
        return rows

    def _category_summary(self, simulator, days: int = 30) -> List[Dict[str, Any]]:
        """Return readable category-level analytics rows."""
        rows = []
        for fid, info in simulator.get_all_factories().items():
            machines = simulator.get_factory_machines(fid)
            analytics = self.analytics.get_factory_analytics(fid, days=days)
            rows.append({
                "category": info.get("name", fid),
                "machine_count": len(machines),
                "healthy": sum(1 for m in machines if m.status == MachineStatus.NORMAL),
                "warning": sum(1 for m in machines if m.status == MachineStatus.WARNING),
                "critical": sum(1 for m in machines if m.status == MachineStatus.CRITICAL),
                "average_health": round(sum(m.health_score for m in machines) / len(machines), 1) if machines else 0,
                "average_failure_probability": round(sum(m.failure_probability for m in machines) / len(machines) * 100, 1) if machines else 0,
                "availability": analytics.get("availability", analytics.get("availability_percent", 0)),
                "failure_rate": analytics.get("failure_rate", 0),
                "utilization": analytics.get("utilization", analytics.get("utilization_percent", 0)),
                "mtbf": analytics.get("mtbf", analytics.get("mtbf_hours", 0)),
                "mttr": analytics.get("mttr", analytics.get("mttr_hours", 0))
            })
        return rows

    def _fleet_summary(self, simulator) -> Dict[str, Any]:
        """Generate fleet summary data."""
        all_machines = simulator.get_all_machines()
        critical = sum(1 for m in all_machines if m.status == MachineStatus.CRITICAL)
        warning = sum(1 for m in all_machines if m.status == MachineStatus.WARNING)
        normal = sum(1 for m in all_machines if m.status == MachineStatus.NORMAL)
        return {
            "total_machines": len(all_machines),
            "healthy": normal,
            "warning": warning,
            "critical": critical,
            "average_health": round(
                sum(m.health_score for m in all_machines) / len(all_machines), 1
            ) if all_machines else 0,
            "average_failure_probability": round(
                sum(m.failure_probability for m in all_machines) / len(all_machines) * 100, 1
            ) if all_machines else 0,
            "total_categories": len(simulator.get_all_factories())
        }

    def _maintenance_statistics(self, logs: List[MaintenanceLog]) -> Dict[str, Any]:
        """Generate maintenance statistics from logs."""
        if not logs:
            return {
                "total_events": 0,
                "total_cost": 0,
                "total_downtime": 0,
                "average_duration": 0,
                "by_type": {}
            }
        by_type = {}
        for log in logs:
            mtype = log.maintenance_type.value
            if mtype not in by_type:
                by_type[mtype] = {"count": 0, "cost": 0, "hours": 0}
            by_type[mtype]["count"] += 1
            by_type[mtype]["cost"] += log.cost
            by_type[mtype]["hours"] += log.duration_hours
        return {
            "total_events": len(logs),
            "total_cost": round(sum(log.cost for log in logs), 2),
            "total_downtime": round(sum(log.duration_hours for log in logs), 1),
            "average_duration": round(
                sum(log.duration_hours for log in logs) / len(logs), 1
            ) if logs else 0,
            "by_type": by_type
        }

    def _work_order_statistics(self, work_orders: List[WorkOrder]) -> Dict[str, Any]:
        """Generate work order statistics."""
        if not work_orders:
            return {
                "total": 0,
                "open": 0,
                "in_progress": 0,
                "completed": 0,
                "cancelled": 0,
                "by_priority": {}
            }
        by_priority = {}
        for wo in work_orders:
            p = wo.priority
            if p not in by_priority:
                by_priority[p] = 0
            by_priority[p] += 1
        return {
            "total": len(work_orders),
            "open": sum(1 for wo in work_orders if wo.status == WorkOrderStatus.OPEN),
            "in_progress": sum(1 for wo in work_orders if wo.status == WorkOrderStatus.IN_PROGRESS),
            "completed": sum(1 for wo in work_orders if wo.status == WorkOrderStatus.COMPLETED),
            "cancelled": sum(1 for wo in work_orders if wo.status == WorkOrderStatus.CANCELLED),
            "by_priority": by_priority
        }

    def _alert_statistics(self, alerts: List[Alert]) -> Dict[str, Any]:
        """
        Generate mathematically consistent alert statistics.
        
        Rules:
        - total:     All alerts in the provided list
        - open:      Alerts where status == 'Open'
        - closed:    Alerts where status == 'Closed' or 'Resolved'
        - critical:  OPEN alerts where severity == CRITICAL
        - warning:   OPEN alerts where severity == WARNING
        - info:      OPEN alerts where severity == INFO
        
        Invariants:
        - open == critical + warning + info
        - total == open + closed
        """
        total = len(alerts)
        open_alerts = [a for a in alerts if a.status == "Open"]
        closed_alerts = [a for a in alerts if a.status in ("Closed", "Resolved")]
        
        return {
            "total": total,
            "open": len(open_alerts),
            "closed": len(closed_alerts),
            "critical": sum(1 for a in open_alerts if a.severity == AlertSeverity.CRITICAL),
            "warning": sum(1 for a in open_alerts if a.severity == AlertSeverity.WARNING),
            "info": sum(1 for a in open_alerts if a.severity == AlertSeverity.INFO)
        }

    def _technician_statistics(self, logs: List[MaintenanceLog]) -> List[Dict[str, Any]]:
        """Generate technician performance statistics."""
        tech_stats = {}
        for log in logs:
            tech = log.technician
            if tech not in tech_stats:
                tech_stats[tech] = {"jobs": 0, "total_hours": 0, "total_cost": 0}
            tech_stats[tech]["jobs"] += 1
            tech_stats[tech]["total_hours"] += log.duration_hours
            tech_stats[tech]["total_cost"] += log.cost
        return [
            {
                "technician": tech,
                "jobs_completed": stats["jobs"],
                "total_hours": round(stats["total_hours"], 1),
                "total_cost": round(stats["total_cost"], 2),
                "avg_job_hours": round(stats["total_hours"] / stats["jobs"], 1) if stats["jobs"] else 0
            }
            for tech, stats in sorted(tech_stats.items(), key=lambda x: x[1]["jobs"], reverse=True)
        ]

    def _manufacturer_performance(self, simulator) -> List[Dict[str, Any]]:
        """Generate manufacturer performance data."""
        all_machines = simulator.get_all_machines()
        manufacturers = {}
        for m in all_machines:
            man = m.manufacturer
            if man not in manufacturers:
                manufacturers[man] = {"machines": [], "total_health": 0, "total_failure_prob": 0}
            manufacturers[man]["machines"].append(m)
            manufacturers[man]["total_health"] += m.health_score
            manufacturers[man]["total_failure_prob"] += m.failure_probability

        return [
            {
                "manufacturer": man,
                "machine_count": len(data["machines"]),
                "average_health": round(data["total_health"] / len(data["machines"]), 1),
                "average_failure_probability": round(
                    data["total_failure_prob"] / len(data["machines"]) * 100, 1
                ),
                "critical_count": sum(1 for m in data["machines"] if m.status == MachineStatus.CRITICAL),
                "warning_count": sum(1 for m in data["machines"] if m.status == MachineStatus.WARNING)
            }
            for man, data in sorted(manufacturers.items(), key=lambda x: x[1]["total_health"] / len(x[1]["machines"]), reverse=True)
        ]

    def _recommendations(self, simulator) -> List[str]:
        """Generate AI recommendations based on current fleet state."""
        all_machines = simulator.get_all_machines()
        critical = [m for m in all_machines if m.status == MachineStatus.CRITICAL]
        warning = [m for m in all_machines if m.status == MachineStatus.WARNING]
        high_risk = [m for m in all_machines if m.failure_probability > 0.5]

        recs = []
        if critical:
            recs.append(f"Immediate corrective maintenance required for {len(critical)} critical machines.")
        if warning:
            recs.append(f"Schedule preventive maintenance for {len(warning)} warning machines.")
        if high_risk:
            recs.append(f"Review {len(high_risk)} high-risk machines with elevated failure probability.")
        
        # Category-level recommendations
        for fid, info in simulator.get_all_factories().items():
            machines = simulator.get_factory_machines(fid)
            if machines:
                avg_health = sum(m.health_score for m in machines) / len(machines)
                if avg_health < 60:
                    recs.append(f"Prioritize {info.get('name', fid)} category with average health of {avg_health:.1f}%.")
        
        if not recs:
            recs.append("Fleet condition is stable. Continue routine monitoring and scheduled maintenance.")
        
        # Add general recommendations
        recs.append("Monitor sensor trends for early anomaly detection.")
        recs.append("Ensure spare parts inventory is adequate for critical machines.")
        
        return recs

    def _ai_summary(self, simulator) -> str:
        """Generate an AI summary of fleet status."""
        all_machines = simulator.get_all_machines()
        critical = sum(1 for m in all_machines if m.status == MachineStatus.CRITICAL)
        warning = sum(1 for m in all_machines if m.status == MachineStatus.WARNING)
        avg_health = round(
            sum(m.health_score for m in all_machines) / len(all_machines), 1
        ) if all_machines else 0

        if critical:
            condition = "requires immediate attention"
        elif warning:
            condition = "is stable but needs preventive follow-up"
        else:
            condition = "is operating normally"

        return (
            f"The fleet {condition}. Average health is {avg_health}%, with "
            f"{critical} critical machines and {warning} warning machines. "
            f"Total fleet size is {len(all_machines)} machines across "
            f"{len(simulator.get_all_factories())} equipment categories."
        )

    # ==================== DAILY REPORT ====================

    def generate_daily_report(self) -> Report:
        """Generate a comprehensive daily summary report."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        simulator = self._get_simulator()
        
        # Today's alerts
        today_alerts = [
            a for a in self.data_store.alert_service.get_all_alerts()
            if a.timestamp >= today
        ]
        
        # Today's work orders
        today_work_orders = [
            wo for wo in self.data_store.work_order_service.get_all_work_orders()
            if wo.created_date >= today
        ]
        
        # Today's maintenance
        today_logs = [
            log for log in self.data_store.maintenance_log_service.get_all_logs()
            if log.maintenance_date >= today
        ]

        # Machine status counts
        all_machines = simulator.get_all_machines()
        critical = sum(1 for m in all_machines if m.status == MachineStatus.CRITICAL)
        warning = sum(1 for m in all_machines if m.status == MachineStatus.WARNING)
        normal = sum(1 for m in all_machines if m.status == MachineStatus.NORMAL)
        
        # Fleet Summary
        fleet_summary = self._fleet_summary(simulator)
        
        # Category Summary
        category_summary = self._category_summary(simulator, days=1)
        
        # Machine Health Summary
        machine_health_summary = [
            {
                "machine_id": m.machine_id,
                "machine_name": m.name,
                "category": m.machine_category,
                "health_score": m.health_score,
                "status": m.status.value,
                "failure_probability": round(m.failure_probability * 100, 1)
            }
            for m in all_machines
        ]
        
        # Open Alerts
        open_alerts = [
            {
                "alert_id": a.alert_id,
                "machine_id": a.machine_id,
                "severity": a.severity.value,
                "reason": a.reason,
                "timestamp": a.timestamp.isoformat(),
                "recommended_action": a.recommended_action
            }
            for a in today_alerts if a.status == "Open"
        ]
        
        # Warning Machines
        warning_machines = self._top_risk_machines(
            [m for m in all_machines if m.status == MachineStatus.WARNING],
            limit=50
        )
        
        # Critical Machines
        critical_machines = self._top_risk_machines(
            [m for m in all_machines if m.status == MachineStatus.CRITICAL],
            limit=50
        )
        
        # Work Orders
        work_orders = [
            {
                "work_order_id": wo.work_order_id,
                "machine_id": wo.machine_id,
                "title": wo.title,
                "status": wo.status.value,
                "priority": wo.priority,
                "assigned_technician": wo.assigned_technician,
                "created_date": wo.created_date.isoformat()
            }
            for wo in today_work_orders
        ]
        
        # Maintenance Statistics
        maintenance_stats = self._maintenance_statistics(today_logs)
        
        # Downtime
        downtime = round(sum(log.duration_hours for log in today_logs), 1)
        
        # Maintenance Cost
        maintenance_cost = round(sum(log.cost for log in today_logs), 2)
        
        # AI Summary
        ai_summary = self._ai_summary(simulator)
        
        # Recommendations
        recommendations = self._recommendations(simulator)
        
        data = {
            "report_date": today.date().isoformat(),
            "fleet_summary": fleet_summary,
            "category_summary": category_summary,
            "machine_health_summary": machine_health_summary,
            "open_alerts": open_alerts,
            "warning_machines": warning_machines,
            "critical_machines": critical_machines,
            "work_orders": work_orders,
            "maintenance_statistics": maintenance_stats,
            "downtime": downtime,
            "maintenance_cost": maintenance_cost,
            "ai_summary": ai_summary,
            "recommendations": recommendations,
            # Legacy fields for backward compatibility
            "total_machines": len(all_machines),
            "critical_count": critical,
            "warning_count": warning,
            "normal_count": normal,
            "average_health": round(
                sum(m.health_score for m in all_machines) / len(all_machines), 1
            ) if all_machines else 0,
            "new_alerts": len(today_alerts),
            "new_work_orders": len(today_work_orders),
            "maintenance_events": len(today_logs),
            "total_maintenance_cost": maintenance_cost,
            "alerts_by_severity": {
                "critical": len([a for a in today_alerts if a.severity == AlertSeverity.CRITICAL]),
                "warning": len([a for a in today_alerts if a.severity == AlertSeverity.WARNING]),
                "info": len([a for a in today_alerts if a.severity == AlertSeverity.INFO])
            },
            "work_orders_by_status": self.data_store.work_order_service.get_work_order_summary(),
            "maintenance_completed": len([
                wo for wo in today_work_orders if wo.status == WorkOrderStatus.COMPLETED
            ]),
            "enterprise_analytics": self.analytics.get_enterprise_analytics(days=1)
        }

        report = Report(
            report_id=self._generate_id("daily"),
            report_type="daily",
            title=f"Daily Maintenance Report - {today.date().isoformat()}",
            data=data
        )
        return self._save_report_once(report)

    # ==================== WEEKLY REPORT ====================

    def generate_weekly_report(self) -> Report:
        """Generate a comprehensive weekly summary report."""
        week_ago = datetime.now() - timedelta(days=7)
        simulator = self._get_simulator()

        weekly_alerts = [
            a for a in self.data_store.alert_service.get_all_alerts()
            if a.timestamp >= week_ago
        ]
        weekly_work_orders = [
            wo for wo in self.data_store.work_order_service.get_all_work_orders()
            if wo.created_date >= week_ago
        ]
        weekly_logs = [
            log for log in self.data_store.maintenance_log_service.get_all_logs()
            if log.maintenance_date >= week_ago
        ]

        all_machines = simulator.get_all_machines()
        active_types = sorted({m.machine_type for m in all_machines}, key=lambda t: t.value)
        
        # Fleet Performance
        fleet_performance = self._fleet_summary(simulator)
        
        # Weekly Health Trend
        health_trend = []
        for i in range(7):
            day = week_ago + timedelta(days=i)
            day_logs = [
                log for log in weekly_logs
                if log.maintenance_date.date() == day.date()
            ]
            day_alerts = [
                a for a in weekly_alerts
                if a.timestamp.date() == day.date()
            ]
            health_trend.append({
                "date": day.date().isoformat(),
                "average_health": fleet_performance["average_health"],
                "alerts": len(day_alerts),
                "maintenance_events": len(day_logs)
            })
        
        # Alert Statistics
        alert_stats = self._alert_statistics(weekly_alerts)
        
        # Work Order Statistics
        wo_stats = self._work_order_statistics(weekly_work_orders)
        
        # Maintenance Statistics
        maintenance_stats = self._maintenance_statistics(weekly_logs)
        
        # Category Comparison
        category_comparison = self._category_summary(simulator, days=7)
        
        # Top Risk Machines
        top_risk = self._top_risk_machines(all_machines, limit=10)
        
        # Availability, Utilization, Downtime, MTBF, MTTR
        enterprise_analytics = self.analytics.get_enterprise_analytics(days=7)
        
        # Recommendations
        recommendations = self._recommendations(simulator)
        
        data = {
            "report_period": f"{week_ago.date().isoformat()} to {datetime.now().date().isoformat()}",
            "fleet_performance": fleet_performance,
            "weekly_health_trend": health_trend,
            "alert_statistics": alert_stats,
            "work_order_statistics": wo_stats,
            "maintenance_statistics": maintenance_stats,
            "category_comparison": category_comparison,
            "top_risk_machines": top_risk,
            "availability": enterprise_analytics.get("average_availability", 0),
            "utilization": enterprise_analytics.get("average_utilization", 0),
            "downtime": enterprise_analytics.get("total_downtime", 0),
            "mtbf": enterprise_analytics.get("average_mtbf", 0),
            "mttr": enterprise_analytics.get("average_mttr", 0),
            "recommendations": recommendations,
            # Legacy fields for backward compatibility
            "total_machines": len(all_machines),
            "total_alerts": len(weekly_alerts),
            "resolved_alerts": len([a for a in weekly_alerts if a.status == "Resolved"]),
            "new_work_orders": len(weekly_work_orders),
            "completed_work_orders": len([
                wo for wo in weekly_work_orders 
                if wo.status == WorkOrderStatus.COMPLETED
            ]),
            "maintenance_events": len(weekly_logs),
            "total_maintenance_cost": round(
                sum(log.cost for log in weekly_logs), 2
            ),
            "total_downtime": round(
                sum(log.duration_hours for log in weekly_logs), 1
            ),
            "machine_type_breakdown": {
                mtype.value: len(simulator.get_machines_by_type(mtype))
                for mtype in active_types
            },
            "enterprise_analytics": enterprise_analytics,
            "category_analytics": {
                fid: self.analytics.get_factory_analytics(fid, days=7)
                for fid in simulator.get_all_factories()
            }
        }

        report = Report(
            report_id=self._generate_id("weekly"),
            report_type="weekly",
            title=f"Weekly Maintenance Report - Week of {week_ago.date().isoformat()}",
            data=data
        )
        return self._save_report_once(report)

    # ==================== MONTHLY REPORT ====================

    def generate_monthly_report(self) -> Report:
        """Generate a comprehensive monthly summary report."""
        month_ago = datetime.now() - timedelta(days=30)
        simulator = self._get_simulator()

        monthly_alerts = [
            a for a in self.data_store.alert_service.get_all_alerts()
            if a.timestamp >= month_ago
        ]
        monthly_work_orders = [
            wo for wo in self.data_store.work_order_service.get_all_work_orders()
            if wo.created_date >= month_ago
        ]
        monthly_logs = [
            log for log in self.data_store.maintenance_log_service.get_all_logs()
            if log.maintenance_date >= month_ago
        ]

        all_machines = simulator.get_all_machines()

        # MTBF & MTTR by machine type
        mtbf_by_type = {}
        mttr_by_type = {}
        active_types = sorted({m.machine_type for m in all_machines}, key=lambda t: t.value)
        for mtype in active_types:
            type_machines = simulator.get_machines_by_type(mtype)
            if type_machines:
                mtbfs = []
                mttrs = []
                for m in type_machines:
                    mtbfs.append(self.analytics.calculate_mtbf(m.machine_id))
                    mttrs.append(self.analytics.calculate_mttr(m.machine_id))
                mtbf_by_type[mtype.value] = round(
                    sum(mtbfs) / len(mtbfs), 1
                ) if mtbfs else 0
                mttr_by_type[mtype.value] = round(
                    sum(mttrs) / len(mttrs), 1
                ) if mttrs else 0

        # Fleet Health
        fleet_health = self._fleet_summary(simulator)
        
        # Category Performance
        category_performance = self._category_summary(simulator, days=30)
        
        # Alert Trends
        alert_trends = []
        for i in range(4):
            week_start = month_ago + timedelta(weeks=i)
            week_end = week_start + timedelta(days=7)
            week_alerts = [
                a for a in monthly_alerts
                if week_start <= a.timestamp < week_end
            ]
            alert_trends.append({
                "week": f"Week {i+1}",
                "period": f"{week_start.date().isoformat()} to {week_end.date().isoformat()}",
                "total": len(week_alerts),
                "critical": sum(1 for a in week_alerts if a.severity == AlertSeverity.CRITICAL),
                "warning": sum(1 for a in week_alerts if a.severity == AlertSeverity.WARNING),
                "info": sum(1 for a in week_alerts if a.severity == AlertSeverity.INFO)
            })
        
        # Work Order Trends
        wo_trends = []
        for i in range(4):
            week_start = month_ago + timedelta(weeks=i)
            week_end = week_start + timedelta(days=7)
            week_wos = [
                wo for wo in monthly_work_orders
                if week_start <= wo.created_date < week_end
            ]
            wo_trends.append({
                "week": f"Week {i+1}",
                "period": f"{week_start.date().isoformat()} to {week_end.date().isoformat()}",
                "total": len(week_wos),
                "open": sum(1 for wo in week_wos if wo.status == WorkOrderStatus.OPEN),
                "completed": sum(1 for wo in week_wos if wo.status == WorkOrderStatus.COMPLETED)
            })
        
        # Maintenance Trends
        maint_trends = []
        for i in range(4):
            week_start = month_ago + timedelta(weeks=i)
            week_end = week_start + timedelta(days=7)
            week_logs = [
                log for log in monthly_logs
                if week_start <= log.maintenance_date < week_end
            ]
            maint_trends.append({
                "week": f"Week {i+1}",
                "period": f"{week_start.date().isoformat()} to {week_end.date().isoformat()}",
                "total": len(week_logs),
                "cost": round(sum(log.cost for log in week_logs), 2),
                "hours": round(sum(log.duration_hours for log in week_logs), 1)
            })
        
        # Maintenance Cost
        maintenance_cost = round(sum(log.cost for log in monthly_logs), 2)
        
        # Downtime
        downtime = round(sum(log.duration_hours for log in monthly_logs), 1)
        
        # Availability, Utilization, MTBF, MTTR
        enterprise_analytics = self.analytics.get_enterprise_analytics(days=30)
        
        # Manufacturer Performance
        manufacturer_performance = self._manufacturer_performance(simulator)
        
        # Recommendations
        recommendations = self._recommendations(simulator)
        
        data = {
            "report_period": f"{month_ago.date().isoformat()} to {datetime.now().date().isoformat()}",
            "fleet_health": fleet_health,
            "category_performance": category_performance,
            "alert_trends": alert_trends,
            "work_order_trends": wo_trends,
            "maintenance_trends": maint_trends,
            "maintenance_cost": maintenance_cost,
            "downtime": downtime,
            "availability": enterprise_analytics.get("average_availability", 0),
            "utilization": enterprise_analytics.get("average_utilization", 0),
            "mtbf": enterprise_analytics.get("average_mtbf", 0),
            "mttr": enterprise_analytics.get("average_mttr", 0),
            "mtbf_by_type": mtbf_by_type,
            "mttr_by_type": mttr_by_type,
            "manufacturer_performance": manufacturer_performance,
            "recommendations": recommendations,
            # Legacy fields for backward compatibility
            "total_machines": len(all_machines),
            "total_categories": len(simulator.get_all_factories()),
            "total_maintenance_events": len(monthly_logs),
            "total_maintenance_cost": maintenance_cost,
            "predictive_maintenance": len([
                log for log in monthly_logs 
                if log.maintenance_type == MaintenanceType.PREDICTIVE
            ]),
            "corrective_maintenance": len([
                log for log in monthly_logs 
                if log.maintenance_type == MaintenanceType.CORRECTIVE
            ]),
            "preventive_maintenance": len([
                log for log in monthly_logs 
                if log.maintenance_type == MaintenanceType.PREVENTIVE
            ]),
            "emergency_maintenance": len([
                log for log in monthly_logs 
                if log.maintenance_type == MaintenanceType.EMERGENCY
            ]),
            "average_health_score": round(
                sum(m.health_score for m in all_machines) / len(all_machines), 1
            ) if all_machines else 0,
            "enterprise_analytics": enterprise_analytics,
            "trend_data": self._generate_trend_data(days=30)
        }

        report = Report(
            report_id=self._generate_id("monthly"),
            report_type="monthly",
            title=f"Monthly Maintenance Report - {datetime.now().strftime('%B %Y')}",
            data=data
        )
        return self._save_report_once(report)

    # ==================== MACHINE REPORT ====================

    def generate_machine_report(self, machine_id: str) -> Report:
        """Generate a comprehensive detailed report for a specific machine."""
        simulator = self._get_simulator()
        machine = simulator.get_machine(machine_id)
        if not machine:
            return Report(
                report_id=self._generate_id("machine"),
                report_type="machine",
                title=f"Machine Report - {machine_id} (Not Found)",
                data={"error": f"Machine {machine_id} not found"}
            )

        logs = self.data_store.maintenance_log_service.get_logs_by_machine(machine_id)
        alerts = self.data_store.alert_service.get_alerts_by_machine(machine_id)
        work_orders = self.data_store.work_order_service.get_work_orders_by_machine(machine_id)
        analytics = self.analytics.get_machine_analytics(machine_id, days=365)
        
        # Latest Sensor Readings
        latest_readings = simulator.get_latest_readings(machine_id)
        sensor_readings = {}
        for sensor_name, reading in latest_readings.items():
            sensor_readings[sensor_name] = {
                "value": reading.get("sensor_value", 0),
                "status": reading.get("status", "normal"),
                "unit": reading.get("unit", ""),
                "timestamp": reading.get("timestamp", datetime.now()).isoformat() if isinstance(reading.get("timestamp"), datetime) else reading.get("timestamp", "")
            }
        
        # Prediction
        prediction = {
            "health_score": machine.health_score,
            "failure_probability": round(machine.failure_probability * 100, 1),
            "status": machine.status.value,
            "prediction_accuracy": self.analytics.calculate_prediction_accuracy(machine.machine_id),
            "mtbf": analytics.mtbf_hours,
            "mttr": analytics.mttr_hours
        }
        
        # Alert History
        alert_history = [
            {
                "alert_id": a.alert_id,
                "severity": a.severity.value,
                "reason": a.reason,
                "timestamp": a.timestamp.isoformat(),
                "status": a.status,
                "recommended_action": a.recommended_action
            }
            for a in alerts[:20]
        ]
        
        # Work Order History
        work_order_history = [
            {
                "work_order_id": wo.work_order_id,
                "title": wo.title,
                "status": wo.status.value,
                "priority": wo.priority,
                "assigned_technician": wo.assigned_technician,
                "created_date": wo.created_date.isoformat(),
                "completed_date": wo.completed_date.isoformat() if wo.completed_date else None
            }
            for wo in work_orders[:20]
        ]
        
        # Maintenance History
        maintenance_history = [
            {
                "log_id": log.log_id,
                "maintenance_date": log.maintenance_date.isoformat(),
                "technician": log.technician,
                "maintenance_type": log.maintenance_type.value,
                "issue": log.issue,
                "action_taken": log.action_taken,
                "cost": log.cost,
                "duration_hours": log.duration_hours,
                "parts_replaced": log.parts_replaced
            }
            for log in logs[:20]
        ]
        
        # Recommendations
        recommendations = [
            self._machine_recommendation(machine)
        ]
        if machine.status == MachineStatus.CRITICAL:
            recommendations.append("Schedule immediate corrective maintenance.")
            recommendations.append("Inspect all critical subsystems and sensors.")
        elif machine.status == MachineStatus.WARNING:
            recommendations.append("Schedule preventive maintenance within 48 hours.")
            recommendations.append("Monitor sensor readings for abnormal patterns.")
        else:
            recommendations.append("Continue routine monitoring.")
            if machine.next_maintenance_date:
                days_to_maint = (machine.next_maintenance_date - datetime.now()).days
                if days_to_maint <= 7:
                    recommendations.append(f"Upcoming maintenance due in {days_to_maint} days.")
        
        data = {
            "machine_information": {
                "machine_id": machine.machine_id,
                "name": machine.name,
                "manufacturer": machine.manufacturer,
                "model": machine.model_number,
                "category": machine.machine_category,
                "type": machine.machine_type.value,
                "installation_date": machine.installation_date.isoformat() if machine.installation_date else None,
                "operating_hours": machine.operating_hours,
                "last_maintenance_date": machine.last_maintenance_date.isoformat() if machine.last_maintenance_date else None,
                "next_maintenance_date": machine.next_maintenance_date.isoformat() if machine.next_maintenance_date else None
            },
            "health": machine.health_score,
            "failure_probability": round(machine.failure_probability * 100, 1),
            "status": machine.status.value,
            "latest_sensor_readings": sensor_readings,
            "prediction": prediction,
            "alert_history": alert_history,
            "work_order_history": work_order_history,
            "maintenance_history": maintenance_history,
            "recommendations": recommendations,
            # Legacy fields for backward compatibility
            "machine_id": machine.machine_id,
            "name": machine.name,
            "type": machine.machine_type.value,
            "category": machine.machine_category,
            "manufacturer": machine.manufacturer,
            "model": machine.model_number,
            "installation_date": machine.installation_date.isoformat(),
            "operating_hours": machine.operating_hours,
            "current_status": machine.status.value,
            "health_score": machine.health_score,
            "failure_probability": machine.failure_probability,
            "analytics": analytics.to_dict(),
            "maintenance_history_legacy": [log.to_dict() for log in logs[:20]],
            "recent_alerts": [a.to_dict() for a in alerts[:20]],
            "work_orders_legacy": [wo.to_dict() for wo in work_orders[:20]],
            "total_maintenance_cost": round(sum(log.cost for log in logs), 2),
            "total_downtime": round(sum(log.duration_hours for log in logs), 1)
        }

        report = Report(
            report_id=self._generate_id("machine"),
            report_type="machine",
            title=f"Machine Report - {machine.name} ({machine_id})",
            data=data
        )
        return self._save_report_once(report)

    # ==================== CATEGORY REPORT ====================

    def generate_factory_report(self, factory_id: str) -> Report:
        """Generate a comprehensive report for an equipment category."""
        simulator = self._get_simulator()
        factory_info = simulator.get_all_factories().get(factory_id)
        if not factory_info:
            return Report(
                report_id=self._generate_id("category"),
                report_type="category",
                title=f"Equipment Report - {factory_id} (Not Found)",
                data={"error": f"Category {factory_id} not found"}
            )

        machines = simulator.get_factory_machines(factory_id)
        factory_analytics = self.analytics.get_factory_analytics(factory_id, days=30)
        
        # Get all alerts, work orders, and maintenance logs for this category
        machine_ids = {m.machine_id for m in machines}
        all_alerts = self.data_store.alert_service.get_all_alerts()
        all_work_orders = self.data_store.work_order_service.get_all_work_orders()
        all_logs = self.data_store.maintenance_log_service.get_all_logs()
        
        category_alerts = [a for a in all_alerts if a.machine_id in machine_ids]
        category_work_orders = [wo for wo in all_work_orders if wo.machine_id in machine_ids]
        category_logs = [log for log in all_logs if log.machine_id in machine_ids]
        
        # Machine Count breakdown
        healthy = sum(1 for m in machines if m.status == MachineStatus.NORMAL)
        warning = sum(1 for m in machines if m.status == MachineStatus.WARNING)
        critical = sum(1 for m in machines if m.status == MachineStatus.CRITICAL)
        
        # Average Health
        avg_health = round(
            sum(m.health_score for m in machines) / len(machines), 1
        ) if machines else 0
        
        # Average Availability
        avg_availability = factory_analytics.get("average_availability", 0)
        
        # Average Failure Probability
        avg_failure_prob = round(
            sum(m.failure_probability for m in machines) / len(machines) * 100, 1
        ) if machines else 0
        
        # Alerts
        alerts_data = [
            {
                "alert_id": a.alert_id,
                "machine_id": a.machine_id,
                "severity": a.severity.value,
                "reason": a.reason,
                "timestamp": a.timestamp.isoformat(),
                "status": a.status
            }
            for a in category_alerts[:20]
        ]
        
        # Work Orders
        work_orders_data = [
            {
                "work_order_id": wo.work_order_id,
                "machine_id": wo.machine_id,
                "title": wo.title,
                "status": wo.status.value,
                "priority": wo.priority,
                "assigned_technician": wo.assigned_technician
            }
            for wo in category_work_orders[:20]
        ]
        
        # Maintenance Logs
        maintenance_logs_data = [
            {
                "log_id": log.log_id,
                "machine_id": log.machine_id,
                "maintenance_date": log.maintenance_date.isoformat(),
                "technician": log.technician,
                "maintenance_type": log.maintenance_type.value,
                "cost": log.cost,
                "duration_hours": log.duration_hours
            }
            for log in category_logs[:20]
        ]
        
        # Top Risk Machines
        top_risk = self._top_risk_machines(machines, limit=10)
        
        # Recommendations
        recommendations = []
        if critical > 0:
            recommendations.append(f"Immediate attention required for {critical} critical machines in this category.")
        if warning > 0:
            recommendations.append(f"Schedule preventive maintenance for {warning} warning machines.")
        if avg_health < 60:
            recommendations.append(f"Category average health is low ({avg_health}%). Consider comprehensive inspection.")
        if avg_failure_prob > 30:
            recommendations.append(f"Elevated failure probability ({avg_failure_prob}%). Increase monitoring frequency.")
        if not recommendations:
            recommendations.append("Category is operating within normal parameters. Continue routine monitoring.")
        
        # Machine breakdown
        machine_breakdown = {}
        for m in machines:
            group = m.machine_id
            if group not in machine_breakdown:
                machine_breakdown[group] = {
                    "total": 0, "critical": 0, "warning": 0,
                    "avg_health": 0,
                    "manufacturer": m.manufacturer,
                    "model": m.model_number
                }
            machine_breakdown[group]["total"] += 1
            if m.status == MachineStatus.CRITICAL:
                machine_breakdown[group]["critical"] += 1
            elif m.status == MachineStatus.WARNING:
                machine_breakdown[group]["warning"] += 1

        for machine_id in machine_breakdown:
            entry_machines = [m for m in machines if m.machine_id == machine_id]
            machine_breakdown[machine_id]["avg_health"] = round(
                sum(m.health_score for m in entry_machines) / len(entry_machines), 1
            ) if entry_machines else 0

        data = {
            "category_id": factory_id,
            "category": factory_info["name"],
            "machine_count": len(machines),
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "average_health": avg_health,
            "average_availability": avg_availability,
            "average_failure_probability": avg_failure_prob,
            "alerts": alerts_data,
            "work_orders": work_orders_data,
            "maintenance_logs": maintenance_logs_data,
            "top_risk_machines": top_risk,
            "recommendations": recommendations,
            # Legacy fields for backward compatibility
            "total_machines": len(machines),
            "machine_breakdown": machine_breakdown,
            "analytics": factory_analytics,
            "machine_types": {
                mtype.value: len([
                    m for m in machines if m.machine_type == mtype
                ])
                for mtype in sorted({m.machine_type for m in machines}, key=lambda t: t.value)
            }
        }

        report = Report(
            report_id=self._generate_id("category"),
            report_type="category",
            title=f"Equipment Report - {factory_info['name']}",
            data=data
        )
        return self._save_report_once(report)

    # ==================== MAINTENANCE REPORT ====================

    def generate_maintenance_report(self, days: int = 30) -> Report:
        """Generate a comprehensive maintenance activity report."""
        cutoff = datetime.now() - timedelta(days=days)
        simulator = self._get_simulator()

        logs = [
            log for log in self.data_store.maintenance_log_service.get_all_logs()
            if log.maintenance_date >= cutoff
        ]
        
        all_work_orders = self.data_store.work_order_service.get_all_work_orders()
        recent_work_orders = [wo for wo in all_work_orders if wo.created_date >= cutoff]

        # Maintenance Summary
        maintenance_summary = self._maintenance_statistics(logs)
        
        # Completed Jobs
        completed_jobs = [
            log.to_dict() for log in logs
            if log.status == "Completed"
        ]
        
        # Pending Jobs
        pending_jobs = [
            {
                "work_order_id": wo.work_order_id,
                "machine_id": wo.machine_id,
                "title": wo.title,
                "priority": wo.priority,
                "assigned_technician": wo.assigned_technician,
                "created_date": wo.created_date.isoformat(),
                "scheduled_date": wo.scheduled_date.isoformat() if wo.scheduled_date else None
            }
            for wo in recent_work_orders
            if wo.status in (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)
        ]
        
        # Average Repair Time
        durations = [log.duration_hours for log in logs if log.duration_hours > 0]
        avg_repair_time = round(sum(durations) / len(durations), 1) if durations else 0
        
        # Downtime
        downtime = round(sum(log.duration_hours for log in logs), 1)
        
        # Maintenance Cost
        maintenance_cost = round(sum(log.cost for log in logs), 2)
        
        # Technician Statistics
        technician_stats = self._technician_statistics(logs)
        
        # Recommendations
        recommendations = []
        if pending_jobs:
            recommendations.append(f"Complete {len(pending_jobs)} pending maintenance jobs.")
        if avg_repair_time > 4:
            recommendations.append(f"Average repair time is {avg_repair_time}h. Consider process optimization.")
        if maintenance_cost > 100000:
            recommendations.append(f"Maintenance cost is ₹{maintenance_cost:,.2f}. Review cost reduction opportunities.")
        recommendations.append("Ensure all maintenance logs are properly documented.")
        recommendations.append("Review preventive maintenance schedule for optimization.")

        # Group by maintenance type
        by_type = {}
        for log in logs:
            mtype = log.maintenance_type.value
            if mtype not in by_type:
                by_type[mtype] = {"count": 0, "cost": 0, "hours": 0}
            by_type[mtype]["count"] += 1
            by_type[mtype]["cost"] += log.cost
            by_type[mtype]["hours"] += log.duration_hours

        # Top machines by maintenance
        machine_maintenance = {}
        for log in logs:
            if log.machine_id not in machine_maintenance:
                machine_maintenance[log.machine_id] = {
                    "count": 0, "cost": 0, "hours": 0
                }
            machine_maintenance[log.machine_id]["count"] += 1
            machine_maintenance[log.machine_id]["cost"] += log.cost
            machine_maintenance[log.machine_id]["hours"] += log.duration_hours

        for mid in machine_maintenance:
            machine = simulator.get_machine(mid)
            machine_maintenance[mid]["name"] = machine.name if machine else mid
            machine_maintenance[mid]["type"] = machine.machine_type.value if machine else "Unknown"

        data = {
            "period_days": days,
            "maintenance_summary": maintenance_summary,
            "completed_jobs": completed_jobs[-50:],
            "pending_jobs": pending_jobs,
            "average_repair_time": avg_repair_time,
            "downtime": downtime,
            "maintenance_cost": maintenance_cost,
            "technician_statistics": technician_stats,
            "recommendations": recommendations,
            # Legacy fields for backward compatibility
            "total_events": len(logs),
            "total_cost": maintenance_cost,
            "total_hours": downtime,
            "by_type": by_type,
            "top_machines": dict(
                sorted(
                    machine_maintenance.items(),
                    key=lambda x: x[1]["count"],
                    reverse=True
                )[:10]
            ),
            "maintenance_logs": [log.to_dict() for log in logs[-50:]]
        }

        report = Report(
            report_id=self._generate_id("maintenance"),
            report_type="maintenance",
            title=f"Maintenance Activity Report - Last {days} Days",
            data=data
        )
        return self._save_report_once(report)

    # ==================== PREDICTION REPORT ====================

    def generate_prediction_report(self) -> Report:
        """Generate a comprehensive AI prediction performance report."""
        simulator = self._get_simulator()
        all_machines = simulator.get_all_machines()

        predictions = []
        for m in all_machines:
            # Determine predicted failure window
            if m.failure_probability > 0.7:
                failure_window = "Within 24 hours"
            elif m.failure_probability > 0.5:
                failure_window = "Within 7 days"
            elif m.failure_probability > 0.3:
                failure_window = "Within 30 days"
            elif m.failure_probability > 0.1:
                failure_window = "Within 90 days"
            else:
                failure_window = "Low risk"
            
            # Determine recommended action
            if m.status == MachineStatus.CRITICAL:
                recommended_action = "Immediate corrective maintenance required"
            elif m.status == MachineStatus.WARNING:
                recommended_action = "Schedule preventive maintenance within 48 hours"
            elif m.failure_probability > 0.5:
                recommended_action = "Schedule predictive maintenance within 7 days"
            elif m.failure_probability > 0.3:
                recommended_action = "Increase monitoring frequency"
            else:
                recommended_action = "Continue routine monitoring"
            
            predictions.append({
                "machine_id": m.machine_id,
                "name": m.name,
                "type": m.machine_type.value,
                "category": m.machine_category,
                "health_score": m.health_score,
                "failure_probability": round(m.failure_probability * 100, 1),
                "confidence": round(self.analytics.calculate_prediction_accuracy(m.machine_id), 1),
                "predicted_failure_window": failure_window,
                "recommended_action": recommended_action,
                "status": m.status.value,
                "prediction_accuracy": self.analytics.calculate_prediction_accuracy(m.machine_id)
            })

        # Sort by failure probability (highest first)
        predictions.sort(key=lambda x: x["failure_probability"], reverse=True)

        # High Risk Machines
        high_risk_machines = [p for p in predictions if p["failure_probability"] > 50]
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_predictions": len(predictions),
            "high_risk_machines": high_risk_machines[:20],
            "failure_probability_distribution": {
                "high_risk": len([p for p in predictions if p["failure_probability"] > 50]),
                "medium_risk": len([p for p in predictions if 20 < p["failure_probability"] <= 50]),
                "low_risk": len([p for p in predictions if p["failure_probability"] <= 20])
            },
            "confidence": round(
                sum(p["confidence"] for p in predictions) / len(predictions), 1
            ) if predictions else 0,
            "average_accuracy": round(
                sum(p["prediction_accuracy"] for p in predictions) / len(predictions), 1
            ) if predictions else 0,
            # Legacy fields for backward compatibility
            "high_risk_count": len([p for p in predictions if p["failure_probability"] > 50]),
            "medium_risk_count": len([p for p in predictions if 20 < p["failure_probability"] <= 50]),
            "low_risk_count": len([p for p in predictions if p["failure_probability"] <= 20]),
            "predictions": predictions[:20]
        }

        report = Report(
            report_id=self._generate_id("prediction"),
            report_type="prediction",
            title=f"AI Prediction Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            data=data
        )
        return self._save_report_once(report)

    # ==================== TREND DATA ====================

    def _generate_trend_data(self, days: int = 30) -> Dict[str, List]:
        """Generate trend data for charts over a period."""
        simulator = self._get_simulator()
        
        # Daily health snapshots
        daily_health = []
        for i in range(days):
            day = datetime.now() - timedelta(days=days - i)
            all_machines = simulator.get_all_machines()
            if all_machines:
                avg_health = sum(m.health_score for m in all_machines) / len(all_machines)
                daily_health.append({
                    "date": day.date().isoformat(),
                    "average_health": round(avg_health, 1),
                    "critical": sum(1 for m in all_machines if m.status == MachineStatus.CRITICAL),
                    "warning": sum(1 for m in all_machines if m.status == MachineStatus.WARNING)
                })
            # Simulate health degradation for realistic trend
            simulator.simulate_health_degradation()

        return {
            "health_trend": daily_health
        }

    # ==================== REPORT LISTING ====================

    def get_recent_reports(self, limit: int = 10) -> List[Dict]:
        """Get most recent generated reports (no duplicates)."""
        seen = set()
        unique_reports = []
        for r in reversed(self.data_store.generated_reports):
            key = (r.get("report_type", ""), r.get("title", ""))
            if key not in seen:
                seen.add(key)
                unique_reports.append(r)
            if len(unique_reports) >= limit:
                break
        return unique_reports

    def get_reports_by_type(self, report_type: str) -> List[Dict]:
        """Get reports filtered by type (no duplicates)."""
        seen = set()
        result = []
        for r in self.data_store.generated_reports:
            if r["report_type"] == report_type:
                key = (r.get("report_type", ""), r.get("title", ""))
                if key not in seen:
                    seen.add(key)
                    result.append(r)
        return result


# Singleton accessor
def get_report_generator() -> ReportGenerator:
    """Get the report generator singleton."""
    return ReportGenerator()