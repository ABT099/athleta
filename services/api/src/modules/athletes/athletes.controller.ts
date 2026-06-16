import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import { AthletesService } from './athletes.service';
import { CurrentUser } from 'src/decorators/user.decorator';
import type { CurrentAuthUser } from '../auth/auth.types';
import { UpdateAthleteDto } from './dto/update-athlete.dto';
import { CreateRecoveryMetricDto } from './dto/create-recovery-metric.dto';
import { UpdateRecoveryMetricDto } from './dto/update-recovery-metric.dto';

@Controller('athletes')
export class AthletesController {
  constructor(private readonly athletesService: AthletesService) {}

  @Get('me')
  getMe(@CurrentUser() user: CurrentAuthUser) {
    return this.athletesService.getMyProfile(user.id);
  }

  @Patch('me')
  updateMe(
    @CurrentUser() user: CurrentAuthUser,
    @Body() dto: UpdateAthleteDto,
  ) {
    return this.athletesService.updateMyProfile(user.id, {
      age: dto.age,
      gender: dto.gender,
      trainingExperience: dto.trainingExperience,
      bodyWeightKg: dto.weight, // already kg via the DTO transform
    });
  }

  @Get('me/personal-records')
  getMyPersonalRecords(@CurrentUser() user: CurrentAuthUser) {
    return this.athletesService.getMyPersonalRecords(user.id);
  }

  @Get('me/recovery-metrics')
  getMyRecoveryMetrics(
    @CurrentUser() user: CurrentAuthUser,
    @Query('since') since?: string,
    @Query('limit') limit?: string,
  ) {
    return this.athletesService.getMyRecoveryMetrics(
      user.id,
      since ? new Date(since) : undefined,
      limit ? Number(limit) : undefined,
    );
  }

  @Post('me/recovery-metrics')
  createRecoveryMetric(
    @CurrentUser() user: CurrentAuthUser,
    @Body() dto: CreateRecoveryMetricDto,
  ) {
    return this.athletesService.createRecoveryMetric(user.id, dto);
  }

  @Patch('me/recovery-metrics/:id')
  updateRecoveryMetric(
    @CurrentUser() user: CurrentAuthUser,
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateRecoveryMetricDto,
  ) {
    return this.athletesService.updateRecoveryMetric(user.id, id, dto);
  }

  @Delete('me/recovery-metrics/:id')
  deleteRecoveryMetric(
    @CurrentUser() user: CurrentAuthUser,
    @Param('id', ParseIntPipe) id: number,
  ) {
    return this.athletesService.deleteRecoveryMetric(user.id, id);
  }
}
