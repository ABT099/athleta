import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool } from 'pg';
import { drizzle, NodePgDatabase } from 'drizzle-orm/node-postgres';
import * as schema from '../../db/schema';

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(DatabaseService.name);
  private pool: Pool;
  public readonly db: NodePgDatabase<typeof schema>;

  constructor(private readonly configService: ConfigService) {
    const connectionString = this.configService.get<string>('DATABASE_URL');
    
    if (!connectionString) {
      throw new Error('DATABASE_URL is not defined in environment variables');
    }

    this.pool = new Pool({
      connectionString,
    });

    this.db = drizzle({ client: this.pool, schema });
  }

  async onModuleInit() {
    try {
      // Test the connection
      const client = await this.pool.connect();
      this.logger.log('Database connection established successfully');
      client.release();
    } catch (error) {
      this.logger.error('Failed to establish database connection', error);
      throw error;
    }
  }

  async onModuleDestroy() {
    await this.pool.end();
    this.logger.log('Database connection pool closed');
  }
}

