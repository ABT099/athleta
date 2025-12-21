# ATHLETA

An all in one intelligent platform to enhance fitness progression with AI

## Folder structure

```
athleta/
├── migrator/ # Database migration (Flyway)
├── services/
│ ├── api/ # NestJS API service
│ ├── ai-engine/ # Python AI/ML service
│ ├── exercise-inference/ # Go service for exercise inference
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

### Database

The project uses **Flyway** running in a Docker container to manage database changes.

#### Applying Changes

Whenever you add a new SQL file to the `migrator/sql` folder, run this command to rebuild the image and apply the changes:

```bash
docker compose up --build migrator
```

### Syncing with Drizzle

When you make changes and want to reflect those changes to the drizzle schema to use it in the api, you should run:

```bash
npm run db:introspect
```
