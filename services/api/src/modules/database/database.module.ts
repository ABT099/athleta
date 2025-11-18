import { Module, Global } from '@nestjs/common';
import { drizzleProvider, DRIZZLE } from './database.provider';

@Global()
@Module({
  providers: [drizzleProvider],
  exports: [DRIZZLE],
})
export class DatabaseModule {}

