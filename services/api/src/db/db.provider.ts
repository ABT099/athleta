import { Provider } from '@nestjs/common';
import { Pool } from 'pg';
import { drizzle } from 'drizzle-orm/node-postgres';
import * as schema from './schema';

export const DB_PROVIDER = 'DB';

export const dbProvider: Provider = {
  provide: DB_PROVIDER,
  useFactory: () => {
    const pool = new Pool({
      connectionString: process.env.DATABASE_URL!,
    });
    return drizzle({ client: pool, schema });
  },
};

