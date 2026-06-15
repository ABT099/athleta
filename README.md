# ATHLETA

An all in one intelligent platform to enhance fitness progression with AI

## Architecture

![Alt Text](/assets/architecture.png)

## Folder structure

```
athleta/
├── services/
│ ├── api/ # NestJS API service (owns its Postgres; migrations via drizzle-kit)
│ ├── auto-regulation-service/ # Python AI/ML service (owns its Postgres; migrations via Alembic)
│ ├── exercise-service/ # Go service for exercise inference and logic
│ └── muscle-image/ # PHP service for muscle images
├── docker-compose.yml
├── docker-compose.prod.yml
└── backups/
```

## Get Started

We have packaged everything to Docker containers so if you want to start the app just run:

```bash
docker compose up -d
```

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
  schema). Models map onto `AutoregBase`; migrations use Alembic:

  ```bash
  cd services/auto-regulation-service
  alembic revision --autogenerate -m "describe change"   # after editing models
  alembic upgrade head                                    # applies to $AUTOREG_DATABASE_URL
  ```

- **exercise-service** seeds Neo4j independently (`make seed`).

Run the relevant `migrate` / `upgrade head` step before starting the services
against a fresh database.
