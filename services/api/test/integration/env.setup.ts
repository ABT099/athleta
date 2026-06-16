/**
 * Runs in each Jest worker (via `setupFiles`) before any module is loaded, so
 * the values are visible to ConfigModule when AppModule is instantiated.
 *
 * The container connection strings are written to `.runtime.json` by the
 * one-time global setup; everything else is static test config.
 */
import * as fs from 'fs';
import * as path from 'path';

const runtimePath = path.join(__dirname, '.runtime.json');
if (fs.existsSync(runtimePath)) {
  const runtime = JSON.parse(fs.readFileSync(runtimePath, 'utf-8')) as {
    databaseUrl: string;
    kafkaBrokers: string;
  };
  process.env.DATABASE_URL = runtime.databaseUrl;
  process.env.KAFKA_BROKERS = runtime.kafkaBrokers;
}

process.env.JWT_SECRET = process.env.JWT_SECRET ?? 'integration-test-secret';
process.env.JWT_ISSUER = process.env.JWT_ISSUER ?? 'athleta-api';
process.env.SERVICE_TOKEN =
  process.env.SERVICE_TOKEN ?? 'integration-service-token';
// Several providers call ConfigService.getOrThrow(...) at construction (email +
// OAuth). These suites don't exercise those flows, so dummy values are enough
// to let the module graph instantiate.
const REQUIRED_DEFAULTS: Record<string, string> = {
  SENDGRID_API_KEY: 'SG.integration-test',
  APPLE_CLIENT_ID: 'test.apple.client',
  GOOGLE_CLIENT_ID: 'test-google-client',
  GOOGLE_CLIENT_SECRET: 'test-google-secret',
  OAUTH_REDIRECT_URI: 'http://localhost:8080/auth/oauth/callback',
  EXPO_APP_SCHEME: 'athleta',
  WEB_BASE_URL: 'http://localhost:3000',
};
for (const [key, value] of Object.entries(REQUIRED_DEFAULTS)) {
  process.env[key] = process.env[key] ?? value;
}
