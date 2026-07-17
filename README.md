# Agentic Predictive Maintenance with OpenRouter

This project is now structured as an agentic AI maintenance system instead of a traditional ML-classifier pipeline.

It uses a coordinated set of AI agents to inspect machine sensor data, diagnose likely root causes, recommend actions, and generate maintenance plans.

## Agent Flow

The workflow is coordinated by `AIOrchestrator` in `orchestrator.py`. The active agents are:

- `MonitoringAgent`: evaluates sensor readings and assigns severity
- `DiagnosticAgent`: infers likely root causes
- `DecisionAgent`: recommends next actions and urgency
- `MaintenancePlannerAgent`: creates a maintenance response plan
- `ChatbotAgent`: answers operator questions from the current analysis

`model_engine.py` now exposes `AgenticMaintenanceEngine`, which is the main entry point for running the agentic workflow from Python code.

## OpenRouter Setup

1. Install the dependencies:

```bash
pip install -r requirements.txt
```

2. Add your OpenRouter key to `.env`:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

3. Run the example script:

```bash
python usage_example.py
```

4. Run the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

If no OpenRouter key is configured, the system still works in rule-based fallback mode.

## Recommended Dependencies

Required runtime packages:

- `openai`
- `python-dotenv`
- `streamlit`
- `plotly`
- `pandas`

Optional package:

- `streamlit-autorefresh`

The old ML-only dependencies such as `scikit-learn` and `joblib` are no longer required for the main workflow.

## Python Example

```python
from model_engine import AgenticMaintenanceEngine

engine = AgenticMaintenanceEngine(model="openai/gpt-4o-mini")
results = engine.analyze(
    machine_ids=["M1", "M2", "M3"],
    data_source="simulated",
    num_readings=12,
    verbose=True,
)

for machine_id, report in results.items():
    print(machine_id, report["severity"], report["model_used"])
```

## Main Files

- `model_engine.py`: high-level agentic engine
- `orchestrator.py`: execution routing between agents
- `llm_client.py`: OpenRouter client wrapper
- `dashboard.py`: Streamlit UI
- `usage_example.py`: runnable example
- `.env`: OpenRouter configuration
