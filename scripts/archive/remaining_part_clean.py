                    "monitoring": {
                        "severity": machine.status.value,
                        "issues": []
                    },
                    "sensor_history": []
                }
                
                response = copilot.answer(prompt, analysis)
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})


def render_machine_alerts_tab(machine: MachineInfo):
    """Render alerts for a machine.
    
    Shows "Alert History" section with all alerts (historical + active).
    Active alerts are highlighted.
    """
    alerts = data_store.alert_service.get_alerts_by_machine(machine.machine_id)
    active_alerts = [a for a in alerts if a.status == "Open"]

    if not alerts:
        st.info("No alerts for this machine.")
        return

    # Show active alerts first if any
    if active_alerts:
        st.markdown("### 🚨 Active Alerts")
        for alert in sorted(active_alerts, key=lambda a: a.timestamp, reverse=True):
            severity_color = {"CRITICAL": "#FF4444", "WARNING": "#FFAA00", "INFO": "#4488FF"}.get(alert.severity.value, "#888")
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border-radius: 8px; padding: 10px; margin: 5px 0;
                        border-left: 4px solid {severity_color};'>
                <span style='color:{severity_color};font-weight:bold;'>{alert.severity.value}</span>
                <span style='color:#aaa;margin-left:10px;'>{alert.timestamp.strftime('%Y-%m-%d %H:%M')}</span>
                <p style='margin:5px 0;color:#ccc;'>{alert.reason}</p>
                <p style='margin:2px 0;color:#888;font-size:0.85rem;'>{alert.recommended_action}</p>
            </div>
            """, unsafe_allow_html=True)

    # Show historical alerts section
    st.markdown("### 📜 Alert History")
    alert_rows = []
    for alert in sorted(alerts, key=lambda a: a.timestamp, reverse=True):
        alert_rows.append({
            "Time": alert.timestamp.strftime("%Y-%m-%d %H:%M"),
            "Severity": alert.severity.value,
            "Reason": alert.reason,
            "Status": alert.status,
            "Recommended Action": alert.recommended_action
        })

    df = pd.DataFrame(alert_rows)

    def color_severity(val):
        colors = {"CRITICAL": "#FF4444", "WARNING": "#FFAA00", "INFO": "#4488FF"}
        return f"background-color: {colors.get(val, '#888')}; color: white;"

    st.dataframe(
        df.style.applymap(color_severity, subset=["Severity"]),
        use_container_width=True,
        hide_index=True
    )


# ==================== ANALYTICS PAGE ====================

def render_analytics():
    """Render analytics page with business-focused fleet insights."""
    st.markdown("""
    <style>
        .stApp {
            background: #F8FAFC;
            font-family: 'Inter', sans-serif;
        }
        .main-header {
            font-family: 'Inter', sans-serif;
            font-size: 36px;
            font-weight: 700;
            color: #111827;
        }
        .analytics-section-title {
            font-family: 'Inter', sans-serif;
            font-size: 34px;
            font-weight: 700;
            color: #111827;
            margin: 8px 0 18px 0;
        }
        .analytics-card-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 20px;
            align-items: stretch;
        }
        .analytics-category-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-left: 6px solid var(--health-border);
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            transition: 0.25s ease;
            min-height: 245px;
            height: 100%;
            font-family: 'Inter', sans-serif;
        }
        .analytics-category-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 32px rgba(0,0,0,0.12);
        }
        .analytics-card-title {
            font-size: 24px;
            line-height: 1.2;
            font-weight: 700;
            color: #1F2937;
            margin: 0 0 10px 0;
        }
        .analytics-card-subtitle {
            font-size: 16px;
            color: #6B7280;
            margin: 0 0 18px 0;
        }
        .analytics-badge-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .analytics-stat-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 15px;
            font-weight: 600;
            color: #1F2937;
            background: #F3F4F6;
            border: 1px solid #E5E7EB;
            white-space: nowrap;
        }
        .analytics-stat-badge.healthy { background: #DCFCE7; color: #166534; border-color: #BBF7D0; }
        .analytics-stat-badge.warning { background: #FEF3C7; color: #92400E; border-color: #FDE68A; }
        .analytics-stat-badge.critical { background: #FEE2E2; color: #991B1B; border-color: #FECACA; }
        .analytics-stat-badge.health { background: #FCE7F3; color: #9D174D; border-color: #FBCFE8; }
        .analytics-stat-badge.alerts { background: #E0F2FE; color: #075985; border-color: #BAE6FD; }
        .analytics-stat-badge.maintenance { background: #EDE9FE; color: #5B21B6; border-color: #DDD6FE; }
        @media (max-width: 1024px) {
            .analytics-card-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 640px) {
            .analytics-card-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("<h1 class='main-header'>Equipment Analytics</h1>", unsafe_allow_html=True)
    st.markdown("---")

    all_machines = simulator.get_all_machines()
    all_alerts = data_store.alert_service.get_all_alerts()
    open_alerts = [a for a in all_alerts if a.status == "Open"]
    today = datetime.now()

    machines_by_category = {
        finfo.get("name", fid): simulator.get_factory_machines(fid)
        for fid, finfo in simulator.get_all_factories().items()
    }

    category_rows = []
    for category, machines in machines_by_category.items():
        machine_ids = {m.machine_id for m in machines}
        category_open_alerts = [a for a in open_alerts if a.machine_id in machine_ids]
        maintenance_due = [
            m for m in machines
            if m.next_maintenance_date and (m.next_maintenance_date - today).days <= 7
        ]
        category_rows.append({
            "Category": category,
            "Machines": len(machines),
            "Healthy": sum(1 for m in machines if m.status == MachineStatus.NORMAL),
            "Warning": sum(1 for m in machines if m.status == MachineStatus.WARNING),
            "Critical": sum(1 for m in machines if m.status == MachineStatus.CRITICAL),
            "Average Health": round(sum(m.health_score for m in machines) / len(machines), 1) if machines else 0,
            "Open Alerts": len(category_open_alerts),
            "Maintenance Due": len(maintenance_due),
            "Average Failure Probability": round(sum(m.failure_probability for m in machines) / len(machines) * 100, 1) if machines else 0,
        })

    category_icons = {
        "Refrigerator": "&#129482;",
        "Washing Machine": "&#129530;",
        "Air Conditioner": "&#10052;&#65039;",
        "Generator": "&#9889;",
        "Car Engine": "&#128663;",
    }
    st.markdown("<div class='analytics-section-title'>Category Summary</div>", unsafe_allow_html=True)
    card_html = ["<div class='analytics-card-grid'>"]
    for idx, row in enumerate(category_rows):
        status_color = "#EF4444" if row["Critical"] else "#F59E0B" if row["Warning"] else "#22C55E"
        icon = category_icons.get(row["Category"], "&#9881;&#65039;")
        card_html.append(f"""
<div class='analytics-category-card' style='--health-border: {status_color};'>
<div class='analytics-card-title'>{icon} {row["Category"]}</div>
<div class='analytics-card-subtitle'>Machines: {row["Machines"]}</div>
<div class='analytics-badge-wrap'>
<span class='analytics-stat-badge healthy'>&#128994; Healthy {row["Healthy"]}</span>
<span class='analytics-stat-badge warning'>&#128993; Warning {row["Warning"]}</span>
<span class='analytics-stat-badge critical'>&#128308; Critical {row["Critical"]}</span>
<span class='analytics-stat-badge health'>&#10084;&#65039; Avg Health {row["Average Health"]}%</span>
<span class='analytics-stat-badge alerts'>&#128680; Alerts {row["Open Alerts"]}</span>
<span class='analytics-stat-badge maintenance'>&#128295; Maintenance {row["Maintenance Due"]}</span>
</div>
</div>
""")
    card_html.append("</div>")
    st.markdown("".join(card_html), unsafe_allow_html=True)

    st.markdown("---")

    avg_health = sum(m.health_score for m in all_machines) / len(all_machines) if all_machines else 0
    avg_risk = sum(m.failure_probability for m in all_machines) / len(all_machines) if all_machines else 0
    trend_rows = []
    for days_back in range(29, -1, -1):
        drift = (days_back / 29) * (avg_risk * 18) if avg_risk else 0
        trend_rows.append({
            "Date": (today - timedelta(days=days_back)).date().isoformat(),
            "Average Health": round(max(0, min(100, avg_health - drift)), 1),
        })

    col1, col2 = st.columns(2)
    with col1:
        fig = px.line(pd.DataFrame(trend_rows), x="Date", y="Average Health", title="Fleet Health Trend", markers=True)
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        failure_df = pd.DataFrame(category_rows)
        fig = px.bar(
            failure_df,
            x="Category",
            y="Average Failure Probability",
            title="Failure Probability by Category",
            color="Category",
            color_discrete_map=MACHINE_TYPE_COLORS,
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        high_risk = sorted(all_machines, key=lambda m: (m.failure_probability, 100 - m.health_score), reverse=True)[:10]
        for m in high_risk:
            col_m1, col_m2, col_m3 = st.columns([2, 2, 1])
            with col_m1:
                st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{m.machine_id}</span> - <span style='color:#666;'>{m.name}</span>", unsafe_allow_html=True)
            with col_m2:
                st.markdown(f"<span style='color:#666;'>{m.machine_category} | Health: {m.health_score:.1f}% | Failure: {m.failure_probability*100:.1f}%</span>", unsafe_allow_html=True)
            with col_m3:
                if st.button("View", key=f"analytics_view_{m.machine_id}", use_container_width=True):
                    navigate_to_machine(m.machine_id)
                    st.rerun()

    with col2:
        forecast_buckets = {"Overdue": 0, "Next 7 Days": 0, "8-30 Days": 0, "31+ Days": 0, "Not Scheduled": 0}
        for machine in all_machines:
            if not machine.next_maintenance_date:
                forecast_buckets["Not Scheduled"] += 1
                continue
            days_to_maintenance = (machine.next_maintenance_date - today).days
            if days_to_maintenance < 0:
                forecast_buckets["Overdue"] += 1
            elif days_to_maintenance <= 7:
                forecast_buckets["Next 7 Days"] += 1
            elif days_to_maintenance <= 30:
                forecast_buckets["8-30 Days"] += 1
            else:
                forecast_buckets["31+ Days"] += 1

        forecast_df = pd.DataFrame([{"Window": window, "Machines": count} for window, count in forecast_buckets.items()])
        fig = px.bar(forecast_df, x="Window", y="Machines", title="Maintenance Forecast", color="Window")
        fig.update_layout(height=430, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        alert_df = pd.DataFrame([{"Category": row["Category"], "Open Alerts": row["Open Alerts"]} for row in category_rows])
        fig = px.bar(
            alert_df,
            x="Category",
            y="Open Alerts",
            title="Alerts by Category",
            color="Category",
            color_discrete_map=MACHINE_TYPE_COLORS,
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        manufacturer_rows = []
        for manufacturer in sorted({m.manufacturer for m in all_machines}):
            manufacturer_machines = [m for m in all_machines if m.manufacturer == manufacturer]
            manufacturer_rows.append({
                "Manufacturer": manufacturer,
                "Machines": len(manufacturer_machines),
                "Average Health": round(sum(m.health_score for m in manufacturer_machines) / len(manufacturer_machines), 1) if manufacturer_machines else 0,
                "Average Failure Probability": round(sum(m.failure_probability for m in manufacturer_machines) / len(manufacturer_machines) * 100, 1) if manufacturer_machines else 0,
            })
        manufacturer_df = pd.DataFrame(manufacturer_rows).sort_values("Average Health", ascending=False)
        fig = px.scatter(
            manufacturer_df,
            x="Average Failure Probability",
            y="Average Health",
            size="Machines",
            color="Manufacturer",
            title="Manufacturer Performance",
            hover_data=["Machines"],
        )
        fig.update_layout(height=360, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        health_rows = []
        for category, machines in machines_by_category.items():
            for machine in machines:
                health_rows.append({"Category": category, "Health Score": machine.health_score, "Machine": machine.machine_id})
        fig = px.box(
            pd.DataFrame(health_rows),
            x="Category",
            y="Health Score",
            color="Category",
            title="Equipment Health Distribution",
            points="all",
            color_discrete_map=MACHINE_TYPE_COLORS,
        )
        fig.update_layout(height=390, paper_bgcolor='rgba(0,0,0,0)', font_color='#ccc', showlegend=False, yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("AI Recommendations")
        recommendations = []
        critical_machines = [m for m in all_machines if m.status == MachineStatus.CRITICAL]
        warning_machines = [m for m in all_machines if m.status == MachineStatus.WARNING]
        due_soon = [m for m in all_machines if m.next_maintenance_date and (m.next_maintenance_date - today).days <= 7]
        if critical_machines:
            recommendations.append(f"Immediate inspection needed for {len(critical_machines)} critical machines.")
        if warning_machines:
            recommendations.append(f"Plan preventive maintenance for {len(warning_machines)} warning machines.")
        if due_soon:
            recommendations.append(f"Schedule maintenance capacity for {len(due_soon)} machines due within 7 days.")
        if open_alerts:
            recommendations.append(f"Review and close {len(open_alerts)} open alerts before the next operating cycle.")
        weakest_category = min(category_rows, key=lambda row: row["Average Health"], default=None)
        if weakest_category:
            recommendations.append(f"Prioritize {weakest_category['Category']} because it has the lowest average health at {weakest_category['Average Health']}%.")
        if not recommendations:
            recommendations.append("Fleet condition is stable. Continue routine monitoring and scheduled maintenance.")

        for recommendation in recommendations:
            st.info(recommendation)

    # === HIGH RISK MACHINES DETAIL ===
    st.markdown("---")
    st.subheader("Top 10 High-Risk Machines")
    high_risk = sorted(all_machines, key=lambda m: (m.failure_probability, 100 - m.health_score), reverse=True)[:10]
    for m in high_risk:
        col_a, col_b, col_c = st.columns([1.5, 4, 1])
        with col_a:
            st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{m.machine_id}</span>", unsafe_allow_html=True)
        with col_b:
            st.markdown(f"<span style='color:#666;'>{m.name} | {m.machine_category} | Health: {m.health_score:.1f}% | Failure Prob: {m.failure_probability*100:.1f}%</span>", unsafe_allow_html=True)
        with col_c:
            if st.button("View", key=f"analytics_risk_view_{m.machine_id}", use_container_width=True):
                navigate_to_machine(m.machine_id)
                st.rerun()


# ==================== ALERTS PAGE ====================

def render_alerts():
    """Render alert center - shows ONLY active (Open) alerts."""
    st.markdown("<h1 class='main-header'>🚨 Alert Center</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Showing only active alerts. Resolved alerts are moved to history.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Summary: only active alerts (Open) with Warning and Critical breakdown
    col1, col2, col3 = st.columns(3)
    summary = data_store.alert_service.get_alert_summary()
    open_count = summary.get("open", 0)
    critical_count = summary.get("critical", 0)
    warning_count = summary.get("warning", 0)
    
    col1.metric("Active Alerts", open_count)
    col2.metric("Warning", warning_count)
    col3.metric("Critical", critical_count)
    
    st.markdown("---")
    
    # Filter by severity - only for active alerts
    severity_filter = st.selectbox("Filter by Severity", ["All", "CRITICAL", "WARNING", "INFO"])
    
    # Get ONLY open alerts (active alerts only)
    alerts = data_store.alert_service.get_open_alerts()
    if severity_filter != "All":
        alerts = [a for a in alerts if a.severity.value == severity_filter]
    
    # Sort by timestamp descending (newest first)
    alerts.sort(key=lambda a: a.timestamp, reverse=True)
    
    if not alerts:
        st.success("✅ No active alerts. All systems normal.")
    else:
        st.caption(f"Showing {len(alerts)} active alert(s)")
        for a in alerts:
            machine = simulator.get_machine(a.machine_id)
            severity_color = {"CRITICAL": "#FF4444", "WARNING": "#FFAA00", "INFO": "#4488FF"}.get(a.severity.value, "#888")
            col_a, col_b, col_c, col_d, col_e, col_f = st.columns([1.2, 1.2, 1.5, 2.5, 1, 1])
            with col_a:
                st.markdown(f"<span style='color:#aaa;font-size:0.8rem;'>{a.alert_id[:12]}</span>", unsafe_allow_html=True)
            with col_b:
                st.markdown(f"<span style='color:{severity_color};font-weight:bold;'>{a.severity.value}</span>", unsafe_allow_html=True)
            with col_c:
                machine_name = machine.name if machine else "N/A"
                st.markdown(f"<span style='color:#ccc;'>{machine_name}</span>", unsafe_allow_html=True)
            with col_d:
                st.markdown(f"<span style='color:#aaa;font-size:0.85rem;'>{a.reason[:60]}</span>", unsafe_allow_html=True)
            with col_e:
                st.markdown(f"<span style='color:#888;font-size:0.8rem;'>{a.timestamp.strftime('%Y-%m-%d %H:%M')}</span>", unsafe_allow_html=True)
            with col_f:
                if st.button(f"🔍 {a.machine_id}", key=f"alert_{a.alert_id}", use_container_width=True):
                    navigate_to_machine(a.machine_id)
                    st.rerun()


# ==================== WORK ORDERS PAGE ====================

def render_work_orders():
    """Render work orders page - shows ONLY Open and In Progress work orders.
    Completed/Cancelled work orders are moved to Maintenance Logs."""
    st.markdown("<h1 class='main-header'>📋 Work Orders</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Showing only active work orders (Open / In Progress). Completed work orders are in Maintenance Logs.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Show only Open and In Progress counts
    col1, col2 = st.columns(2)
    summary = data_store.work_order_service.get_work_order_summary()
    col1.metric("Open", summary.get("Open", 0))
    col2.metric("In Progress", summary.get("In Progress", 0))
    
    st.markdown("---")
    
    # Filter by status - only active statuses
    status_filter = st.selectbox("Filter by Status", ["All", "Open", "In Progress"])
    
    # Get only open and in-progress work orders (active only)
    all_work_orders = data_store.work_order_service.get_all_work_orders()
    work_orders = [wo for wo in all_work_orders if wo.status.value in ("Open", "In Progress")]
    if status_filter != "All":
        work_orders = [wo for wo in work_orders if wo.status.value == status_filter]
    
    work_orders.sort(key=lambda wo: wo.created_date, reverse=True)
    
    if not work_orders:
        st.success("✅ No active work orders. All machines are operating normally.")
    else:
        st.caption(f"Showing {len(work_orders)} active work order(s)")
        for wo in work_orders:
            col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns([1.2, 2, 1.2, 1, 0.8, 1, 0.8])
            with col_a:
                st.markdown(f"<span style='color:#aaa;font-size:0.8rem;'>{wo.work_order_id[:12]}</span>", unsafe_allow_html=True)
            with col_b:
                st.markdown(f"<span style='color:#ccc;'>{wo.title[:40]}</span>", unsafe_allow_html=True)
            with col_c:
                st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{wo.machine_id}</span>", unsafe_allow_html=True)
            with col_d:
                status_colors = {"Open": "#FF4444", "In Progress": "#FFAA00", "Completed": "#44CC44", "Cancelled": "#888"}
                wo_color = status_colors.get(wo.status.value, "#888")
                st.markdown(f"<span style='color:{wo_color};'>{wo.status.value}</span>", unsafe_allow_html=True)
            with col_e:
                st.markdown(f"<span style='color:#ddd;'>{wo.priority}</span>", unsafe_allow_html=True)
            with col_f:
                st.markdown(f"<span style='color:#888;font-size:0.8rem;'>{wo.assigned_technician}</span>", unsafe_allow_html=True)
            with col_g:
                if st.button("🔍", key=f"wo_view_{wo.work_order_id}", use_container_width=True):
                    navigate_to_machine(wo.machine_id)
                    st.rerun()


# ==================== REPORTS PAGE ====================

def _get_report_parts(report: Any) -> Dict[str, Any]:
    """Normalize Report objects and stored report dictionaries for display."""
    if isinstance(report, dict):
        return {
            "title": report.get("title", "Report"),
            "report_type": report.get("report_type", ""),
            "generated_at": report.get("generated_at", datetime.now().isoformat()),
            "data": report.get("data", {})
        }
    return {
        "title": getattr(report, "title", "Report"),
        "report_type": getattr(report, "report_type", ""),
        "generated_at": getattr(report, "generated_at", datetime.now()).isoformat(),
        "data": getattr(report, "data", {})
    }


def _attention_rows() -> List[Dict[str, Any]]:
    rows = []
    for machine in simulator.get_all_machines():
        if machine.status not in (MachineStatus.WARNING, MachineStatus.CRITICAL):
            continue
        recommendation = (
            "Immediate corrective maintenance required"
            if machine.status == MachineStatus.CRITICAL
            else "Schedule preventive maintenance"
        )
        rows.append({
            "Machine ID": machine.machine_id,
            "Machine Name": machine.name,
            "Category": machine.machine_category,
            "Health Score": f"{machine.health_score:.1f}%",
            "Status": machine.status.value,
            "Failure Probability": f"{machine.failure_probability * 100:.1f}%",
            "Recommendation": recommendation
        })
    return rows


def _daily_report_tables(data: Dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Count open alerts from the data's open_alerts list
    open_alerts_list = data.get("open_alerts", [])
    open_alerts_count = len(open_alerts_list) if isinstance(open_alerts_list, list) else data.get("new_alerts", 0)
    
    fleet_summary = pd.DataFrame([{
        "Total Machines": data.get("total_machines", 0),
        "Healthy": data.get("normal_count", 0),
        "Warning": data.get("warning_count", 0),
        "Critical": data.get("critical_count", 0),
        "Average Health": f"{data.get('average_health', 0)}%",
        "Open Alerts": open_alerts_count,
        "New Work Orders": data.get("new_work_orders", 0)
    }])
    attention = pd.DataFrame(_attention_rows())
    return fleet_summary, attention


def _daily_ai_summary(data: Dict[str, Any], attention_count: int) -> str:
    critical = data.get("critical_count", 0)
    warning = data.get("warning_count", 0)
    avg_health = data.get("average_health", 0)
    if critical:
        condition = "requires immediate attention"
    elif warning:
        condition = "is stable but needs preventive follow-up"
    else:
        condition = "is operating normally"
    return (
        f"The fleet {condition}. Average health is {avg_health}%, with "
        f"{critical} critical machines and {warning} warning machines. "
        f"{attention_count} machines currently require maintenance review."
    )


def _csv_bytes(title: str, fleet_summary: pd.DataFrame, attention: pd.DataFrame, summary: str) -> bytes:
    output = io.StringIO()
    output.write(f"{title}\n\n")
    output.write("Fleet Summary\n")
    fleet_summary.to_csv(output, index=False)
    output.write("\nMachines Requiring Attention\n")
    if attention.empty:
        output.write("No warning or critical machines\n")
    else:
        attention.to_csv(output, index=False)
    output.write("\nAI Summary\n")
    output.write(summary)
    return output.getvalue().encode("utf-8")


def _excel_bytes(title: str, fleet_summary: pd.DataFrame, attention: pd.DataFrame, summary: str) -> bytes:
    def xml_escape(value: Any) -> str:
        import html
        return html.escape(str(value), quote=True)

    rows = [f"<Row><Cell><Data ss:Type='String'>{xml_escape(title)}</Data></Cell></Row>"]
    rows.append("<Row></Row>")
    rows.append("<Row><Cell><Data ss:Type='String'>Fleet Summary</Data></Cell></Row>")
    rows.append("<Row>" + "".join(
        f"<Cell><Data ss:Type='String'>{xml_escape(col)}</Data></Cell>"
        for col in fleet_summary.columns
    ) + "</Row>")
    for _, row in fleet_summary.iterrows():
        rows.append("<Row>" + "".join(
            f"<Cell><Data ss:Type='String'>{xml_escape(row[col])}</Data></Cell>"
            for col in fleet_summary.columns
        ) + "</Row>")
    rows.append("<Row></Row>")
    rows.append("<Row><Cell><Data ss:Type='String'>Machines Requiring Attention</Data></Cell></Row>")
    if attention.empty:
        rows.append("<Row><Cell><Data ss:Type='String'>No warning or critical machines</Data></Cell></Row>")
    else:
        rows.append("<Row>" + "".join(
            f"<Cell><Data ss:Type='String'>{xml_escape(col)}</Data></Cell>"
            for col in attention.columns
        ) + "</Row>")
        for _, row in attention.iterrows():
            rows.append("<Row>" + "".join(
                f"<Cell><Data ss:Type='String'>{xml_escape(row[col])}</Data></Cell>"
                for col in attention.columns
            ) + "</Row>")
    rows.append("<Row></Row>")
    rows.append(f"<Row><Cell><Data ss:Type='String'>AI Summary</Data></Cell><Cell><Data ss:Type='String'>{xml_escape(summary)}</Data></Cell></Row>")
    workbook = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Report"><Table>
""" + "\n".join(rows) + """
</Table></Worksheet></Workbook>
"""
    return workbook.encode("utf-8")


def _pdf_bytes(title: str, report_date: str, fleet_summary: pd.DataFrame, attention: pd.DataFrame, summary: str) -> bytes:
    def clean(value: Any) -> str:
        return str(value).encode("latin-1", "replace").decode("latin-1")

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        usable_width = max(1, pdf.w - pdf.l_margin - pdf.r_margin)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, clean(title), ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 8, clean(f"Report Date: {report_date}"), ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Fleet Summary", ln=True)
        pdf.set_font("Arial", "", 10)
        for col, value in fleet_summary.iloc[0].items():
            pdf.cell(65, 7, clean(col), border=1)
            pdf.cell(0, 7, clean(value), border=1, ln=True)
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Machines Requiring Attention", ln=True)
        pdf.set_font("Arial", "", 9)
        if attention.empty:
            pdf.cell(0, 7, "No warning or critical machines", ln=True)
        else:
            for _, row in attention.iterrows():
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(usable_width, 6, clean(
                    f"{row['Machine ID']} | {row['Machine Name']} | {row['Category']} | "
                    f"{row['Health Score']} | {row['Status']} | {row['Failure Probability']} | "
                    f"{row['Recommendation']}"
                ), border=1)
        pdf.ln(4)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "AI Summary", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(usable_width, 6, clean(summary))
        output = pdf.output(dest="S")
        return bytes(output) if isinstance(output, bytearray) else output.encode("latin-1")
    except ImportError:
        lines = [title, f"Report Date: {report_date}", "", "Fleet Summary"]
        lines.extend(f"{col}: {value}" for col, value in fleet_summary.iloc[0].items())
        lines.extend(["", "Machines Requiring Attention"])
        if attention.empty:
            lines.append("No warning or critical machines")
        else:
            for _, row in attention.iterrows():
                lines.append(
                    f"{row['Machine ID']} | {row['Machine Name']} | {row['Category']} | "
                    f"{row['Health Score']} | {row['Status']} | {row['Failure Probability']} | "
                    f"{row['Recommendation']}"
                )
        lines.extend(["", "AI Summary", summary])
        text_commands = ["BT", "/F1 10 Tf", "50 780 Td"]
        for idx, line in enumerate(lines[:80]):
            escaped = clean(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if idx:
                text_commands.append("0 -14 Td")
            text_commands.append(f"({escaped}) Tj")
        text_commands.append("ET")
        stream = "\n".join(text_commands).encode("latin-1")
        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
            b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj",
        ]
        pdf = b"%PDF-1.4\n"
        offsets = []
        for obj in objects:
            offsets.append(len(pdf))
            pdf += obj + b"\n"
        xref = len(pdf)
        pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
        for offset in offsets:
            pdf += f"{offset:010d} 00000 n \n".encode("ascii")
        pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
        return pdf


def _download_report_buttons(title: str, report_date: str, fleet_summary: pd.DataFrame,
                             attention: pd.DataFrame, summary: str, key_context: str = ""):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_").lower() or "report"
    key_suffix = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{key_context}_{safe_name}_{report_date}").strip("_")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download PDF",
            data=_pdf_bytes(title, report_date, fleet_summary, attention, summary),
            file_name=f"{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"pdf_{key_suffix}"
        )
    with col2:
        st.download_button(
            "Download Excel",
            data=_excel_bytes(title, report_date, fleet_summary, attention, summary),
            file_name=f"{safe_name}.xls",
            mime="application/vnd.ms-excel",
            use_container_width=True,
            key=f"excel_{key_suffix}"
        )
    with col3:
        st.download_button(
            "Download CSV",
            data=_csv_bytes(title, report_date, fleet_summary, attention, summary),
            file_name=f"{safe_name}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"csv_{key_suffix}"
        )


def _report_data_rows(data: Any, prefix: str = "") -> List[Dict[str, str]]:
    rows = []
    if isinstance(data, dict):
        for key, value in data.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                rows.extend(_report_data_rows(value, label))
            else:
                rows.append({"Field": label.replace("_", " ").title(), "Value": str(value)})
    elif isinstance(data, list):
        if not data:
            rows.append({"Field": prefix.replace("_", " ").title(), "Value": ""})
        for idx, item in enumerate(data, start=1):
            label = f"{prefix} {idx}" if prefix else f"Item {idx}"
            if isinstance(item, (dict, list)):
                rows.extend(_report_data_rows(item, label))
            else:
                rows.append({"Field": label.replace("_", " ").title(), "Value": str(item)})
    else:
        rows.append({"Field": prefix.replace("_", " ").title() or "Value", "Value": str(data)})
    return rows


def _generic_csv_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    output = io.StringIO()
    output.write(f"{title}\n")
    output.write(f"Generated,{generated_at[:19].replace('T', ' ')}\n\n")
    pd.DataFrame(_report_data_rows(data)).to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


def _generic_excel_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    def xml_escape(value: Any) -> str:
        import html
        return html.escape(str(value), quote=True)

    rows = [
        f"<Row><Cell><Data ss:Type='String'>{xml_escape(title)}</Data></Cell></Row>",
        f"<Row><Cell><Data ss:Type='String'>Generated</Data></Cell><Cell><Data ss:Type='String'>{xml_escape(generated_at[:19].replace('T', ' '))}</Data></Cell></Row>",
        "<Row></Row>",
        "<Row><Cell><Data ss:Type='String'>Field</Data></Cell><Cell><Data ss:Type='String'>Value</Data></Cell></Row>"
    ]
    for row in _report_data_rows(data):
        rows.append(
            f"<Row><Cell><Data ss:Type='String'>{xml_escape(row['Field'])}</Data></Cell>"
            f"<Cell><Data ss:Type='String'>{xml_escape(row['Value'])}</Data></Cell></Row>"
        )
    workbook = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<Worksheet ss:Name="Report"><Table>
""" + "\n".join(rows) + """
</Table></Worksheet></Workbook>
"""
    return workbook.encode("utf-8")


def _text_pdf_bytes(lines: List[str]) -> bytes:
    def clean(value: Any) -> str:
        return str(value).encode("latin-1", "replace").decode("latin-1")

    text_commands = ["BT", "/F1 10 Tf", "50 780 Td"]
    for idx, line in enumerate(lines[:80]):
        escaped = clean(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx:
            text_commands.append("0 -14 Td")
        text_commands.append(f"({escaped}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + b"\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    return pdf


def _generic_pdf_bytes(title: str, generated_at: str, data: Dict[str, Any]) -> bytes:
    lines = [title, f"Generated: {generated_at[:19].replace('T', ' ')}", ""]
    lines.extend(f"{row['Field']}: {row['Value']}" for row in _report_data_rows(data))
    return _text_pdf_bytes(lines)


def _download_generic_report_buttons(title: str, generated_at: str, data: Dict[str, Any], key_context: str = ""):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_").lower() or "report"
    key_suffix = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{key_context}_{safe_name}_{generated_at}").strip("_")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download PDF",
            data=_generic_pdf_bytes(title, generated_at, data),
            file_name=f"{safe_name}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"pdf_{key_suffix}"
        )
    with col2:
        st.download_button(
            "Download Excel",
            data=_generic_excel_bytes(title, generated_at, data),
            file_name=f"{safe_name}.xls",
            mime="application/vnd.ms-excel",
            use_container_width=True,
            key=f"excel_{key_suffix}"
        )
    with col3:
        st.download_button(
            "Download CSV",
            data=_generic_csv_bytes(title, generated_at, data),
            file_name=f"{safe_name}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"csv_{key_suffix}"
        )


def _render_daily_report(report: Any, key_context: str = ""):
    parts = _get_report_parts(report)
    data = parts["data"]
    report_date = data.get("report_date", parts["generated_at"][:10])
    fleet_summary, attention = _daily_report_tables(data)
    summary = _daily_ai_summary(data, len(attention))

    st.subheader(parts["title"])
    st.caption(f"Report Date: {report_date}")
    st.markdown("#### Fleet Summary")
    st.dataframe(fleet_summary, use_container_width=True, hide_index=True)
    st.markdown("#### Machines Requiring Attention")
    if attention.empty:
        st.info("No warning or critical machines.")
    else:
        for _, row in attention.iterrows():
            col_a, col_b, col_c, col_d, col_e = st.columns([1.2, 2, 1.5, 1.5, 0.8])
            with col_a:
                st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{row['Machine ID']}</span>", unsafe_allow_html=True)
            with col_b:
                st.markdown(f"<span style='color:#ccc;'>{row['Machine Name']}</span>", unsafe_allow_html=True)
            with col_c:
                st.markdown(f"<span style='color:#888;'>{row['Category']} | {row['Health Score']}</span>", unsafe_allow_html=True)
            with col_d:
                status_color = STATUS_COLORS.get(row['Status'], "#888")
                st.markdown(f"<span style='color:{status_color};font-weight:bold;'>{row['Status']}</span>", unsafe_allow_html=True)
            with col_e:
                if st.button("View", key=f"report_attention_{key_context}_{row['Machine ID']}", use_container_width=True):
                    navigate_to_machine(row['Machine ID'])
                    st.rerun()
    st.markdown("#### AI Summary")
    st.write(summary)
    _download_report_buttons(parts["title"], report_date, fleet_summary, attention, summary, key_context)


def _render_business_report(report: Any, key_context: str = ""):
    parts = _get_report_parts(report)
    data = parts["data"]
    if parts["report_type"] == "daily" or "report_date" in data:
        _render_daily_report(report, key_context)
        return

    st.subheader(parts["title"])
    st.caption(f"Generated: {parts['generated_at'][:19].replace('T', ' ')}")
    scalar_rows = [
        {"Metric": key.replace("_", " ").title(), "Value": value}
        for key, value in data.items()
        if not isinstance(value, (dict, list))
    ]
    if scalar_rows:
        st.dataframe(pd.DataFrame(scalar_rows), use_container_width=True, hide_index=True)
    for key, value in data.items():
        if isinstance(value, list):
            st.markdown(f"#### {key.replace('_', ' ').title()}")
            st.dataframe(pd.DataFrame(value if value and isinstance(value[0], dict) else {key: value}), use_container_width=True, hide_index=True)
        elif isinstance(value, dict):
            st.markdown(f"#### {key.replace('_', ' ').title()}")
            st.dataframe(pd.DataFrame(_report_data_rows(value)), use_container_width=True, hide_index=True)
    _download_generic_report_buttons(parts["title"], parts["generated_at"], data, key_context)


def render_reports():
    """Render reports page."""
    st.markdown("<h1 class='main-header'>📈 Reports</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📅 Generate Daily Report", use_container_width=True):
            report = report_generator.generate_daily_report()
            st.success(f"✅ {report.title}")
            _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")
    
    with col2:
        if st.button("📆 Generate Weekly Report", use_container_width=True):
            report = report_generator.generate_weekly_report()
            st.success(f"✅ {report.title}")
            _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")
    
    with col3:
        if st.button("📊 Generate Monthly Report", use_container_width=True):
            report = report_generator.generate_monthly_report()
            st.success(f"✅ {report.title}")
            _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        factories = simulator.get_all_factories()
        category_options = list(factories.keys())
        selected_category = st.selectbox(
            "Category",
            category_options,
            format_func=lambda fid: factories[fid].get("name", fid),
            key="machine_report_category"
        )
        category_machines = simulator.get_factory_machines(selected_category) if selected_category else []
        machine_lookup = {machine.machine_id: machine for machine in category_machines}
        machine_options = [""] + list(machine_lookup.keys())
        selected_machine_id = st.selectbox(
            "Machine",
            machine_options,
            format_func=lambda mid: (
                "Select Machine" if not mid
                else f"{mid} - {machine_lookup[mid].name}"
            ),
            key="machine_report_machine"
        )
        if st.button("⚙️ Machine Report", use_container_width=True):
            if not selected_machine_id:
                st.warning("Select a machine to generate a machine report.")
            else:
                with st.spinner("Generating..."):
                    report = report_generator.generate_machine_report(selected_machine_id)
                    _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")
    
    with col2:
        if st.button("🏷️ Category Report", use_container_width=True):
            factory_id = st.text_input("Enter Category ID:", "REFRIGERATOR")
            with st.spinner("Generating..."):
                report = report_generator.generate_factory_report(factory_id)
                _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")
    
    with col3:
        if st.button("🔮 Prediction Report", use_container_width=True):
            with st.spinner("Generating..."):
                report = report_generator.generate_prediction_report()
                _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")

        if st.button("Maintenance Report", use_container_width=True):
            with st.spinner("Generating..."):
                report = report_generator.generate_maintenance_report()
                _render_business_report(report, key_context=f"current_{report.report_type}_{report.report_id}")
    
    st.markdown("---")
    
    # Recent reports
    st.subheader("📋 Recent Reports")
    recent = report_generator.get_recent_reports(5)
    if recent:
        for idx, r in enumerate(recent):
            with st.expander(f"{r['title']} ({r['generated_at'][:10]})"):
                _render_business_report(r, key_context=f"history_{r.get('report_type', 'report')}_{r.get('report_id', idx)}_{idx}")
    else:
        st.info("No reports generated yet.")


# ==================== COPILOT PAGE ====================

def render_copilot():
    """Render AI Copilot chat interface."""
    st.markdown("<h1 class='main-header'>🤖 Enterprise Maintenance Copilot</h1>", unsafe_allow_html=True)
    st.markdown("Ask questions about your entire equipment fleet.")
    st.markdown("---")
    
    # Example questions
    with st.expander("💡 Example Questions"):
        st.markdown("""
        - "Show all critical machines"
        - "Which machine has the highest vibration?"
        - "Show all generators"
        - "Why is GEN-002 unhealthy?"
        - "Compare REF-001 and REF-004"
        - "What maintenance is due today?"
        - "Explain today's alerts"
        - "Which machine failed most frequently?"
        - "Generate today's maintenance report"
        - "Show me all refrigerators"
        - "What's the overall enterprise status?"
        """)
    
    # Chat interface
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    prompt = st.chat_input("Ask the Enterprise Copilot...", key="copilot_input")
    
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing enterprise data..."):
                response = copilot.answer(prompt)
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()


# ==================== MAINTENANCE LOGS PAGE ====================

def render_maintenance_logs():
    """Render maintenance logs page."""
    st.markdown("<h1 class='main-header'>📝 Maintenance Logs</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        logs = data_store.maintenance_log_service.get_all_logs()
        logs.sort(key=lambda l: l.maintenance_date, reverse=True)
        all_machines = simulator.get_all_machines()
        machine_map = {m.machine_id: m for m in all_machines}
        categories = sorted({machine_map[log.machine_id].machine_category for log in logs if log.machine_id in machine_map})
        technicians = sorted({log.technician for log in logs})
        maintenance_types = sorted({log.maintenance_type.value for log in logs})
        statuses = sorted({getattr(log, "status", "Completed") for log in logs})
        f1, f2, f3 = st.columns(3)
        with f1:
            selected_category = st.selectbox("Category", ["All"] + categories, key="maintenance_log_category_filter")
            selected_technician = st.selectbox("Technician", ["All"] + technicians, key="maintenance_log_technician_filter")
        with f2:
            selected_machine = st.selectbox("Machine", ["All"] + sorted({log.machine_id for log in logs}), key="maintenance_log_machine_filter")
            selected_type = st.selectbox("Maintenance Type", ["All"] + maintenance_types, key="maintenance_log_type_filter")
        with f3:
            selected_status = st.selectbox("Status", ["All"] + statuses, key="maintenance_log_status_filter")
            search_text = st.text_input("Search", key="maintenance_log_search")
        date_range = st.date_input("Date", value=[], key="maintenance_log_date_filter")
        filtered_logs = logs
        if selected_category != "All":
            filtered_logs = [log for log in filtered_logs if log.machine_id in machine_map and machine_map[log.machine_id].machine_category == selected_category]
        if selected_machine != "All":
            filtered_logs = [log for log in filtered_logs if log.machine_id == selected_machine]
        if selected_technician != "All":
            filtered_logs = [log for log in filtered_logs if log.technician == selected_technician]
        if selected_type != "All":
            filtered_logs = [log for log in filtered_logs if log.maintenance_type.value == selected_type]
        if selected_status != "All":
            filtered_logs = [log for log in filtered_logs if getattr(log, "status", "Completed") == selected_status]
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_logs = [log for log in filtered_logs if start_date <= log.maintenance_date.date() <= end_date]
        if search_text:
            needle = search_text.lower()
            filtered_logs = [
                log for log in filtered_logs
                if needle in log.machine_id.lower()
                or needle in log.technician.lower()
                or needle in log.log_id.lower()
                or needle in getattr(log, "machine_name", "").lower()
            ]
        
        if not filtered_logs:
            st.info("No maintenance logs found.")
        else:
            for log in filtered_logs:
                machine = simulator.get_machine(log.machine_id)
                col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns([0.8, 1, 1.2, 1.2, 0.8, 1, 0.8])
                with col_a:
                    st.markdown(f"<span style='color:#888;font-size:0.8rem;'>{log.maintenance_date.strftime('%m-%d %H:%M')}</span>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"<span style='color:#4da6ff;font-weight:500;'>{log.machine_id}</span>", unsafe_allow_html=True)
                with col_c:
                    name = log.machine_name or (machine.name if machine else "N/A")
                    st.markdown(f"<span style='color:#ccc;font-size:0.85rem;'>{name}</span>", unsafe_allow_html=True)
                with col_d:
                    st.markdown(f"<span style='color:#aaa;font-size:0.85rem;'>{log.maintenance_type.value}</span>", unsafe_allow_html=True)
                with col_e:
                    st.markdown(f"<span style='color:#ddd;'>₹{log.cost:,.0f}</span>", unsafe_allow_html=True)
                with col_f:
                    st.markdown(f"<span style='color:#888;font-size:0.85rem;'>{log.technician}</span>", unsafe_allow_html=True)
                with col_g:
                    if st.button("🔍", key=f"log_view_{log.log_id}", use_container_width=True):
                        navigate_to_machine(log.machine_id)
                        st.rerun()
    
    with col2:
        all_logs = data_store.maintenance_log_service.get_all_logs()
        st.metric("Total Logs", len(all_logs))
        completed_logs = [log for log in all_logs if getattr(log, "status", "Completed") == "Completed"]
        scheduled_logs = [log for log in all_logs if getattr(log, "status", "") == "Scheduled"]
        total_cost = sum(log.cost for log in completed_logs)
        total_hours = sum(log.duration_hours for log in completed_logs)
        avg_repair_time = round(total_hours / len(completed_logs), 1) if completed_logs else 0
        total_downtime = sum(getattr(log, "downtime_hours", log.duration_hours) for log in completed_logs)
        st.metric("Completed Jobs", len(completed_logs))
        st.metric("Scheduled Jobs", len(scheduled_logs))
        st.metric("Total Cost", f"₹{total_cost:,.2f}")
        st.metric("Total Hours", f"{total_hours:.1f}h")
        st.metric("Avg Repair Time", f"{avg_repair_time:.1f}h")
        st.metric("Downtime", f"{total_downtime:.1f}h")
        
        # Export
        if st.button("📥 Export Logs", use_container_width=True):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Log ID", "Date", "Machine", "Machine Name", "Category", "Type", "Technician", "Issue", "Cost", "Duration", "Downtime", "Before Health", "After Health", "Status"])
            export_rows = []
            for log in filtered_logs:
                machine = simulator.get_machine(log.machine_id)
                row = {
                    "Log ID": log.log_id,
                    "Date": log.maintenance_date.strftime("%Y-%m-%d %H:%M"),
                    "Machine": log.machine_id,
                    "Machine Name": log.machine_name or (machine.name if machine else "N/A"),
                    "Category": log.category or (machine.machine_category if machine else "N/A"),
                    "Type": log.maintenance_type.value,
                    "Technician": log.technician,
                    "Issue": log.issue,
                    "Cost": log.cost,
                    "Duration": log.duration_hours,
                    "Downtime": getattr(log, "downtime_hours", log.duration_hours),
                    "Before Health": getattr(log, "before_health", 0),
                    "After Health": getattr(log, "after_health", 0),
                    "Status": getattr(log, "status", "Completed")
                }
                export_rows.append(row)
                writer.writerow([
                    row["Log ID"], row["Date"], row["Machine"], row["Machine Name"], row["Category"],
                    row["Type"], row["Technician"], row["Issue"], row["Cost"], row["Duration"],
                    row["Downtime"], row["Before Health"], row["After Health"], row["Status"]
                ])
            report_name = f"maintenance_logs_{datetime.now().strftime('%Y%m%d')}"
            export_data = {"maintenance_logs": export_rows}
            st.download_button(
                "Download PDF",
                _generic_pdf_bytes("Maintenance Logs", datetime.now().isoformat(), export_data),
                file_name=f"{report_name}.pdf",
                mime="application/pdf",
                key=f"pdf_{report_name}"
            )
            st.download_button(
                "Download Excel",
                _generic_excel_bytes("Maintenance Logs", datetime.now().isoformat(), export_data),
                file_name=f"{report_name}.xls",
                mime="application/vnd.ms-excel",
                key=f"excel_{report_name}"
            )
            st.download_button(
                "Download CSV",
                output.getvalue(),
                file_name=f"{report_name}.csv",
                mime="text/csv",
                key=f"csv_maintenance_logs_{datetime.now().strftime('%Y%m%d')}"
            )


# ==================== MAIN APP ====================

def main():
    """Main app router."""
    render_sidebar()
    
    page = st.session_state.page
    
    if page == "dashboard":
        render_dashboard()
    elif page == "machines":
        render_machines()
    elif page == "analytics":
        render_analytics()
    elif page == "alerts":
        render_alerts()
    elif page == "work_orders":
        render_work_orders()
    elif page == "reports":
        render_reports()
    elif page == "copilot":
        render_copilot()
    elif page == "maintenance_logs":
        render_maintenance_logs()


if __name__ == "__main__":
    main()
