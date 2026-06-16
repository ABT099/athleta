# ATHLETA

An all-in-one intelligent platform that turns logged workouts into the next
adaptation. Athleta is a **polyglot microservice system**: each service owns one
domain in the language that fits it best, and they compose over gRPC, HTTP, and
Kafka.

---

## The big picture

A single public gateway (`api`) fronts four specialized backends. Each owns its
**own database** and exposes a narrow contract; nothing reaches into another
service's tables.

![architecture diagram](/assets/architecture.png)

| Service | Stack | Owns | Talks via | Docs |
| --- | --- | --- | --- | --- |
| **api** | NestJS / TypeScript | The user & workout domain (athletes, plans, sessions, sets, recovery, PRs) in Postgres `athleta` | Public REST · gRPC client · Kafka · HTTP | [services/api](services/api/README.md) |
| **auto-regulation** | Python / FastAPI | Training-science *algo state* (trends, progression, calibration) in Postgres `autoreg` | HTTP (in & out) · gRPC client · Celery | [services/auto-regulation-service](services/auto-regulation-service/README.md) |
| **exercise-service** | Go | The exercise domain (inference, muscles, substitution) in Neo4j | gRPC server | [services/exercise-service](services/exercise-service/README.md) |
| **muscle-image** | PHP | Muscle-group image rendering → Cloudflare R2 | HTTP API + Kafka worker | [services/muscle-image](services/muscle-image/README.md) |

Supporting infrastructure: **Traefik** (gateway/TLS), **Redis** (Celery broker),
**Kafka** (events), **Prometheus + Grafana** (monitoring). Only `api` is exposed
to the internet; everything else lives on the private `backend` network.

---

## Get started

Everything is packaged into Docker containers. Create a `.env` at the repo root
with the secrets listed under **Required environment** below, then from the repo
root:

```bash
docker compose up -d   # builds local images + exposes ports via the override file
```

`docker compose` automatically layers [docker-compose.override.yml](docker-compose.override.yml)
on top of [docker-compose.yml](docker-compose.yml). The base file pins the
published `ghcr.io` images for production; the override **builds each service
locally** and exposes infra ports (Postgres `5432`, Neo4j `7474/7687`, Redis
`6379`, Kafka `9092`, Traefik dashboard `8080`) for development.

Required environment (in `.env`): `POSTGRES_USER` / `POSTGRES_PASSWORD`,
`JWT_SECRET`, `SERVICE_TOKEN` (shared service-to-service auth), `NEO4J_PASSWORD`,
and the `R2_*` credentials for image storage (see
[muscle-image/README_R2_SETUP.md](services/muscle-image/README_R2_SETUP.md)).

### Databases

Each service owns its own database and its own migrations — there is no shared
migrator. Migrations are applied **manually** (not on container boot):

- **api** owns the `athleta` Postgres. The schema lives in
  [services/api/src/db/schema.ts](services/api/src/db/schema.ts); migrations are
  generated and applied with drizzle-kit:

  ```bash
  cd services/api
  npm run db:generate   # after editing schema.ts — writes drizzle/<n>_*.sql
  npm run db:migrate    # applies pending migrations to $DATABASE_URL
  ```

- **auto-regulation-service** owns its own `autoreg` Postgres (the `ai_analysis`
  schema, *algo state only*). Models map onto `AutoregBase`; migrations use Alembic:

  ```bash
  cd services/auto-regulation-service
  alembic revision --autogenerate -m "describe change"   # after editing models
  alembic upgrade head                                    # applies to $AUTOREG_DATABASE_URL
  ```

- **exercise-service** seeds Neo4j independently (`make seed`).

Run the relevant `migrate` / `upgrade head` step before starting the services
against a fresh database.

---

## Repository layout

```text
athleta/
├── services/
│   ├── api/                       # NestJS gateway — public API + orchestration
│   ├── auto-regulation-service/   # Python AI/ML — progressive-overload engine
│   ├── exercise-service/          # Go — exercise inference over a Neo4j graph
│   └── muscle-image/              # PHP — muscle-group image rendering (HTTP + worker)
├── monitoring/                    # Prometheus scrape config
├── assets/                        # diagrams and static docs assets
├── docker-compose.yml             # base topology (production images)
├── docker-compose.override.yml    # local dev: build from source + expose ports
└── traefik-dynamic.yml            # Traefik dynamic configuration
```

Each service has its own README with the domain philosophy, architecture
diagrams, and run instructions — start there for the deep dives.
