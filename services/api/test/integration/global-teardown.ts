import * as fs from 'fs';
import * as path from 'path';
import type { StartedTestContainer } from 'testcontainers';

interface IntegrationContext {
  pg?: StartedTestContainer;
  kafka?: StartedTestContainer;
  createdProtoLink?: boolean;
  apiProto?: string;
}

module.exports = async function globalTeardown(): Promise<void> {
  const ctx = (globalThis as Record<string, unknown>)
    .__INTEGRATION__ as IntegrationContext | undefined;
  if (!ctx) return;

  if (ctx.createdProtoLink && ctx.apiProto) {
    try {
      fs.unlinkSync(ctx.apiProto);
    } catch {
      /* best-effort cleanup */
    }
  }

  await ctx.kafka?.stop();
  await ctx.pg?.stop();

  try {
    fs.unlinkSync(path.join(__dirname, '.runtime.json'));
  } catch {
    /* best-effort cleanup */
  }
};
