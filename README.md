# AquaTech

### Know your water. See what comes next.

AquaTech brings pond monitoring, water-quality forecasting and risk visibility into one workspace. It turns sensor readings into a clear picture of changing conditions, helping aquaculture teams spot unusual measurements, follow trends and decide where to focus their attention.

Built around the daily work of managing ponds, AquaTech connects the numbers behind water quality with the people responsible for it.

[Explore the architecture](#architecture) · [Run AquaTech](#run-aquatech) · [Read the data methodology](#data-and-methodology)

---

## A clearer view of every pond

Water quality is a moving picture. An isolated reading tells only part of the story; its history, the surrounding conditions and the direction of change matter too. AquaTech brings those views together.

| Capability | What it gives you |
|---|---|
| **Pond management** | A dedicated workspace for each pond, with account-based access and timezone settings. |
| **Water-quality dashboard** | Charts and metric summaries for dissolved oxygen, temperature, pH, turbidity, ammonia and nitrate. |
| **Multi-step forecasting** | Water and nitrogen forecasts presented alongside a timeline of changing conditions. |
| **Risk visibility** | Threshold-based risk states and a view of their distribution across the forecast. |
| **Sensor-quality alerts** | Visibility into missing readings, unusual changes, range violations and consecutive sensor faults. |
| **Traceable records** | Separate raw readings, processed observations and forecast logs, with quality and imputation flags. |
| **Historical replay** | A sensor-feed simulator and sequential replay for exploring the complete monitoring workflow. |

## From readings to decisions

1. **Choose a pond.** Keep each pond's measurements, forecasts and alerts together.
2. **Bring in observations.** Submit timestamped sensor batches or generate a demonstration feed.
3. **Inspect the water.** Move between forecasts, raw readings, processed data and alerts.
4. **Follow the forecast.** See how predicted conditions and risk states change across the timeline.

The dashboard gives operators a shared view of the evidence behind a forecast. Raw and processed records make it possible to distinguish a measured value from one supplied by the ingestion pipeline's imputation models.

## Architecture

AquaTech uses a React interface, a FastAPI application and PostgreSQL storage. The API coordinates ingestion and historical replay, while a dedicated Python inference module handles the forecasting cascade and risk calculation.

```mermaid
flowchart LR
    Operator["Pond operator"] --> UI["React dashboard"]
    Feed["Sensor batches or demo feed"] --> API
    UI <-->|"REST API / JWT"| API["FastAPI application"]

    subgraph Application["Application services"]
        Ponds["Accounts and ponds"]
        Ingestion["Validation and imputation"]
        Replay["Replay and forecast orchestration"]
    end

    API --> Ponds
    API --> Ingestion
    API --> Replay
    Replay --> Ingestion

    subgraph Inference["Python inference"]
        Water["Water-quality LSTM"]
        Nitrogen["Nitrogen LSTM"]
        Risk["Threshold-based risk engine"]
        Water --> Nitrogen
        Water --> Risk
        Nitrogen --> Risk
    end

    Replay --> Water
    Ponds <--> DB[("PostgreSQL")]
    Ingestion <--> DB
    Replay <--> DB
```

The inference module is imported by the application services. The database stores pond ownership, raw and processed sensor records, forecast blocks and alerts. API access to pond data is scoped to the authenticated owner.

### Forecasting workflow

The forecasting cascade uses a historical observation window to estimate dissolved oxygen, temperature, pH and turbidity. Its first predicted water state is incorporated into the nitrogen model's input to estimate ammonia and nitrate. The risk engine then assigns configured risk states to the forecast steps.

```mermaid
sequenceDiagram
    actor Operator
    participant UI as Dashboard
    participant API as FastAPI
    participant Replay as Orchestrator
    participant Ingest as Ingestion service
    participant Models as Forecasting cascade
    participant DB as PostgreSQL

    Operator->>UI: Run a pond replay
    UI->>API: POST /api/v1/sensor/simulate/{pond_id}
    API->>DB: Check pond ownership
    API->>Replay: Process historical readings
    Replay->>DB: Read observations in timestamp order
    loop Each historical observation
        Replay->>Ingest: Process row when needed
        Ingest->>DB: Store processed reading and quality alerts
        opt Historical window is complete
            Replay->>Models: Predict water, nitrogen and risk
            Models-->>Replay: Forecast arrays and risk states
            opt Forecast storage boundary is reached
                Replay->>DB: Save forecast block
            end
        end
    end
    Replay-->>API: Replay results
    API-->>UI: Forecast timeline
    UI-->>Operator: Charts, metrics and risk summary
```

Risk states summarize configured water-quality thresholds. They provide an interpretable view of forecast values; they are not calibrated probabilities of disease, mortality or production loss. Species and farming conditions remain part of how an operator interprets the readings.

### Domain model

The core data model keeps pond ownership and observation lineage explicit. A processed reading can refer back to its raw record, and forecast logs store both predicted values and fields for corresponding observations.

```mermaid
classDiagram
    class User {
        UUID id
        string email
        string role
    }
    class Pond {
        UUID id
        UUID owner_id
        string name
        string timezone
    }
    class SensorDataRaw {
        UUID id
        UUID pond_id
        datetime timestamp
        bool is_processed
    }
    class SensorDataClean {
        UUID id
        UUID raw_id
        datetime timestamp
        bool is_imputed
        string quality_flag
    }
    class ForecastLog {
        UUID id
        datetime forecast_for
        int horizon_step
        string risk_state
    }
    class Alert {
        UUID id
        string alert_type
        string severity
        bool resolved
    }

    User "1" --> "0..*" Pond : owns
    Pond "1" --> "0..*" SensorDataRaw : records
    Pond "1" --> "0..*" SensorDataClean : contains
    SensorDataRaw "0..1" <-- "0..*" SensorDataClean : references
    Pond "1" --> "0..*" ForecastLog : forecasts
    Pond "1" --> "0..*" Alert : alerts
```

## Technology

| Layer | Stack |
|---|---|
| Interface | React, TypeScript, Vite, Tailwind CSS, Recharts |
| Application | Python, FastAPI, Pydantic, SQLAlchemy |
| Storage | PostgreSQL, asyncpg, Alembic migrations |
| Forecasting | TensorFlow / Keras, NumPy, pandas, scikit-learn, joblib |
| Authentication | JWT bearer tokens and bcrypt password hashing |
| Data preparation | Source checksums, session and lineage audits, coverage-gated aggregation, automated verification |

## Run AquaTech

The commands below use Windows PowerShell. Use Python 3.10, Node.js 22.12+ and a PostgreSQL database. The application also requires the model assets listed below.

### 1. Install dependencies

```powershell
git clone https://github.com/adityapandeydev/AquaCulture.git
cd AquaCulture
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install alembic python-multipart
```

### 2. Configure the application

Create a `.env` file in the repository root:

```dotenv
DATABASE_URL=postgresql+asyncpg://aquatech:your-password@localhost:5432/aquatech
SECRET_KEY=replace-with-a-long-random-secret
```

Use your own database credentials and generate a signing secret with `python -c "import secrets; print(secrets.token_hex(32))"`.

The runtime loads these assets from `ml/models/`:

```text
ml/models/
├── feature_columns.json
├── model_config.json
├── scaler.save
├── model1_multivariate_lstm.keras
├── model2_nitrogen_lstm.keras
└── imputation/
    ├── impute_do.pkl
    ├── impute_temperature.pkl
    ├── impute_ph.pkl
    ├── impute_turbidity.pkl
    ├── impute_ammonia.pkl
    └── impute_nitrate.pkl
```

The six imputation artifacts are kept outside Git. Provide trusted copies in the directory shown before starting the API. The model configuration defines the inference window and forecast horizon.

### 3. Start the API

```powershell
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API runs at [localhost:8000](http://localhost:8000). Explore the endpoints and request schemas through the [interactive API reference](http://localhost:8000/docs).

### 4. Start the dashboard

In a second terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, create an account and add a pond. Use the feed simulation to populate observations, then run the pond simulation to explore forecasts and alerts.

The dashboard connects to `http://localhost:8000/api/v1` by default. Set `VITE_API_BASE_URL` in `frontend/.env.local` to use another API address.

## Data and methodology

The data tooling makes provenance, sensor quality and temporal continuity inspectable. It preserves source files, records checksums, identifies shared recording lineage and keeps missing targets distinct from measured observations. Research-data preparation is separate from the application's runtime ingestion and imputation path.

- [Forecasting methodology](docs/data/experiment-spec.md) — target definitions, input configurations and evaluation principles.
- [Source catalog and reuse review](docs/data/source-review.md) — dataset identity, attribution and permitted roles.
- [Measurement schema](docs/data/measurement-schema.md) — units, timestamps and observation lineage.
- [Channel-quality review](docs/data/quality-review.md) — numeric screening, gaps and diagnostic flags.
- [Aggregation policy](docs/data/aggregation-policy.md) — hourly support, freshness and missing-data rules.
- [Dataset eligibility](docs/data/eligibility-review.md) — the scope and evidence behind the DO research benchmark.

Benchmark results are interpreted alongside the species, environment, sensor setup and evaluation method recorded with the data selection.

## Repository guide

```text
AquaCulture/
├── backend/                 # API, application services, database models and migrations
├── frontend/                # Pond dashboard, charts and account interface
├── ml/
│   ├── inference/           # Forecasting cascade and risk engine
│   ├── models/              # Model weights, scaler and feature configuration
│   ├── data/                # Acquisition, audits, preparation and verification
│   └── notebooks/           # Model and preprocessing experiments
├── docs/data/               # Data evidence and methodology
└── requirements.txt         # Python dependencies
```

Run the data-preparation checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ml/data -p 'test_*.py' -q
```

Raw datasets, generated preparation outputs, environment files and local working notes are kept out of version control.
