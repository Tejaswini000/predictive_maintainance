# Predictive Maintenance Dashboard

## Project Overview

This project is a predictive maintenance solution for monitoring equipment health and identifying machines that may require maintenance. The prototype uses historical data and simulated sensor readings because live industrial IoT sensor data is not available for this submission.

The Random Forest machine learning model analyzes machine parameters such as temperature, vibration, pressure, RPM, voltage, current, humidity, ambient temperature, power consumption, operating hours, maintenance history, and machine type. It predicts machine condition so the dashboard can show operational status and support proactive maintenance decisions.

## Domain

Manufacturing / Equipment Maintenance

## Use Case

Predictive Maintenance

## Problem Statement

Manufacturing and equipment maintenance teams often face unexpected machine failures, unplanned downtime, high maintenance costs, and difficulty identifying which machines need attention first. Without proactive monitoring, maintenance teams may respond only after equipment performance has already degraded or stopped production.

This project addresses the need for a maintenance system that can monitor equipment condition, estimate risk, and help teams act before failures become costly.

## Solution Overview

The application demonstrates a predictive maintenance workflow using simulated machine sensor data and a Random Forest prediction engine. The dashboard monitors machine health, predicts status, estimates failure probability, and classifies equipment as Healthy, Warning, or Critical.

The platform also supports alert management, maintenance logs, work orders, technician assignment, analytics, reports, and chatbot assistance. The chatbot uses existing maintenance knowledge and enterprise context, with optional OpenRouter LLM support when an API key is configured.

## Key Features

- Equipment health monitoring across multiple machine categories
- Machine failure prediction using a Random Forest model
- Health score and failure probability display
- Healthy / Warning / Critical machine classification
- Alert management and alert history
- Maintenance logs and maintenance history
- Maintenance work orders with technician assignment
- Analytics for fleet health and maintenance trends
- Report generation and export options
- Predictive maintenance chatbot / enterprise copilot
- Optional LLM-backed chatbot responses through OpenRouter

## Technology Stack

- Python
- Streamlit
- Pandas
- NumPy
- Scikit-learn
- Random Forest Classifier
- Plotly
- OpenPyXL
- FPDF2
- OpenAI Python SDK configured for OpenRouter
- python-dotenv
- Joblib / pickle model persistence

## Data

The prototype uses historical and simulated machine data. It does not currently receive live industrial IoT sensor data.

Simulated sensor readings are used to demonstrate how predictions and dashboard status would change when new machine readings are received. The project includes sample machine data, technician data, and trained model artifacts used by the enterprise dashboard.

## Machine Learning

Machine condition prediction is handled by the Random Forest model in `enterprise/ml_model.py`. The model is trained on simulated historical machine records and predicts the equipment condition classes used by the dashboard.

The LLM does not perform machine failure prediction. Chatbot functionality is separate from the ML prediction workflow. The chatbot provides maintenance assistance and contextual answers, with optional OpenRouter LLM support when `OPENROUTER_API_KEY` is configured.

## Batch

Batch: [To be filled]

## Developer

Developer Full Name: [To be filled]

## Project Resources

- GitHub repository: [To be filled]
- Demo link: [To be filled, if available]
- Documentation: `docs/use-case-overview.docx`
- Presentation: `docs/presentation.pptx`

## How to Setup / Run

From the project root:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional: create a local `.env` file if LLM chatbot support is required:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

Run the enterprise dashboard:

```bash
streamlit run enterprise/enterprise_dashboard.py
```

The older Streamlit dashboard can also be launched with:

```bash
streamlit run dashboard.py
```

## Project Structure

```text
predictive_maintainance/
|-- enterprise/
|   |-- enterprise_dashboard.py
|   |-- ml_model.py
|   |-- simulation.py
|   |-- services.py
|   `-- supporting application modules
|-- data/
|   |-- machines.xlsx
|   `-- supporting datasets
|-- scripts/
|   |-- validation and utility scripts
|   `-- archive/
|-- tests/
|   `-- test files
|-- docs/
|   |-- use-case-overview.docx
|   |-- presentation.pptx
|   |-- archive/
|   `-- screenshots/
|-- README.md
|-- requirements.txt
|-- .env.example
`-- .gitignore
```

## Security Notes

Do not commit real `.env` files, API keys, passwords, tokens, virtual environments, caches, build folders, or generated bytecode. Use `.env.example` for safe placeholder configuration only.
