import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';

async function bootstrap() {
    
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL!,
  });
  const db = drizzle({ client: pool });

  const app = await NestFactory.create(AppModule);
  await app.listen(process.env.PORT ?? 3000);
}

bootstrap();
