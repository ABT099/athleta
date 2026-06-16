import {
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Query,
  UseGuards,
} from '@nestjs/common';
import { InternalService } from './internal.service';
import { ServiceTokenGuard } from '../common/guards/service-token.guard';
import { AllowAnonymous } from '../auth/guards/allow-anonymous';

/**
 * Internal service-to-service endpoints consumed by auto-regulation-service.
 *
 * `@AllowAnonymous()` opts these routes out of the global user-JWT guard;
 * `ServiceTokenGuard` then enforces the shared service token instead.
 */
@AllowAnonymous()
@UseGuards(ServiceTokenGuard)
@Controller('internal')
export class InternalController {
  constructor(private readonly internalService: InternalService) {}

  @Get('athletes/:athleteId')
  async getAthlete(@Param('athleteId', ParseIntPipe) athleteId: number) {
    return this.internalService.getAthlete(athleteId);
  }

  @Get('athletes/:athleteId/active-plan')
  async getActivePlan(@Param('athleteId', ParseIntPipe) athleteId: number) {
    return this.internalService.getActivePlan(athleteId);
  }

  @Get('athletes/:athleteId/recovery-metrics')
  async listRecoveryMetrics(
    @Param('athleteId', ParseIntPipe) athleteId: number,
    @Query('since') since?: string,
    @Query('limit') limit?: string,
  ) {
    return this.internalService.listRecoveryMetrics(
      athleteId,
      since ? new Date(since) : undefined,
      limit ? Number(limit) : undefined,
    );
  }

  @Get('athletes/:athleteId/personal-records')
  async listPersonalRecords(
    @Param('athleteId', ParseIntPipe) athleteId: number,
  ) {
    return this.internalService.listPersonalRecords(athleteId);
  }
}
