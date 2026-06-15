import { Module } from '@nestjs/common';
import { DatabaseModule } from '../common/database/database.module';
import { InternalController } from './internal.controller';
import { InternalService } from './internal.service';
import { ServiceTokenGuard } from '../common/guards/service-token.guard';

/**
 * Internal (service-to-service) read surface consumed by auto-regulation-service:
 * athlete, active plan, recovery metrics and personal records. `InternalService`
 * is exported so the workout-completion flow can reuse its snake_case DTO mapping
 * when pushing the analyze request.
 */
@Module({
  imports: [DatabaseModule],
  controllers: [InternalController],
  providers: [InternalService, ServiceTokenGuard],
  exports: [InternalService],
})
export class InternalModule {}
