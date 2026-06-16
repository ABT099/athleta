/**
 * One-time setup for the integration suite: boot a real Postgres and Kafka via
 * Testcontainers, apply the schema, and hand the connection strings to the test
 * workers through `.runtime.json`. External collaborators (exercise-service
 * gRPC, auto-regulation HTTP) are faked at the DI layer in `test-app.ts`.
 */
import { PostgreSqlContainer } from '@testcontainers/postgresql';
import { KafkaContainer } from '@testcontainers/kafka';
import { Client } from 'pg';
import * as fs from 'fs';
import * as path from 'path';

const API_ROOT = path.join(__dirname, '..', '..'); // services/api
const MIGRATION = path.join(API_ROOT, 'drizzle', '0000_ancient_wildside.sql');
const RUNTIME = path.join(__dirname, '.runtime.json');
// exercise.module.ts resolves the proto from `process.cwd()/proto`, but the
// only copy lives at the repo root. Symlink it into place so AppModule (which
// loads the gRPC proto eagerly) can boot.
const REPO_PROTO = path.join(API_ROOT, '..', '..', 'proto');
const API_PROTO = path.join(API_ROOT, 'proto');

module.exports = async function globalSetup(): Promise<void> {
  let createdProtoLink = false;
  if (!fs.existsSync(API_PROTO)) {
    fs.symlinkSync(REPO_PROTO, API_PROTO, 'dir');
    createdProtoLink = true;
  }

  const pg = await new PostgreSqlContainer('postgres:18-alpine').start();
  const kafka = await new KafkaContainer('confluentinc/cp-kafka:7.8.0').start();

  const databaseUrl = pg.getConnectionUri();
  // The PLAINTEXT listener is exposed on container port 9093 (KAFKA_PORT).
  const KAFKA_PLAINTEXT_PORT = 9093;
  const kafkaBrokers = `${kafka.getHost()}:${kafka.getMappedPort(
    KAFKA_PLAINTEXT_PORT,
  )}`;

  // Apply the Drizzle migration directly (no drizzle-kit CLI needed).
  const ddl = fs.readFileSync(MIGRATION, 'utf-8');
  const statements = ddl
    .split('--> statement-breakpoint')
    .map((s) => s.trim())
    .filter(Boolean);
  const client = new Client({ connectionString: databaseUrl });
  await client.connect();
  for (const stmt of statements) {
    await client.query(stmt);
  }
  await client.end();

  fs.writeFileSync(RUNTIME, JSON.stringify({ databaseUrl, kafkaBrokers }));

  // Stash containers for teardown; also expose env for the setup process.
  (globalThis as Record<string, unknown>).__INTEGRATION__ = {
    pg,
    kafka,
    createdProtoLink,
    apiProto: API_PROTO,
  };
  process.env.DATABASE_URL = databaseUrl;
  process.env.KAFKA_BROKERS = kafkaBrokers;
};
