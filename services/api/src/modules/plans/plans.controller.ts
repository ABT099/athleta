import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Put,
  Delete,
  Patch,
} from '@nestjs/common';
import { CreatePlanDto } from './dto/create-plan.dto';
import { PlansService } from './plans.service';
import { CurrentUser } from 'src/decorators/user.decorator';
import { UpdatePlanDto } from './dto/update-plan.dto';
import type { CurrentAuthUser } from '../auth/auth.types';

@Controller('plans')
export class PlansController {
  constructor(private readonly plansService: PlansService) {}

  @Get()
  getPlans(@CurrentUser() user: CurrentAuthUser) {
    return this.plansService.getPlans(user.id);
  }

  @Get(':planId')
  getPlan(
    @Param('planId', ParseIntPipe) planId: number,
    @CurrentUser() user: CurrentAuthUser,
  ) {
    return this.plansService.getPlan(user.id, planId);
  }

  @Post()
  createPlan(@Body() dto: CreatePlanDto, @CurrentUser() user: CurrentAuthUser) {
    return this.plansService.createPlan({
      athleteId: user.id,
      name: dto.name,
      description: dto.description,
      trainingType: dto.trainingType,
      periodizationModel: dto.periodizationModel,
      frequency: dto.frequency,
      durationWeeks: dto.durationWeeks,
      focusAreas: dto.focusAreas,
      workoutDays: dto.workoutDays,
    });
  }

  @Put(':planId')
  updatePlan(
    @Param('planId', ParseIntPipe) planId: number,
    @Body() dto: UpdatePlanDto,
    @CurrentUser() user: CurrentAuthUser,
  ) {
    return this.plansService.updatePlan(user.id, planId, {
      name: dto.name,
      description: dto.description,
      trainingType: dto.trainingType,
      periodizationModel: dto.periodizationModel,
      frequency: dto.frequency,
      durationWeeks: dto.durationWeeks,
      focusAreas: dto.focusAreas,
      workoutDaysToAdd: dto.workoutDaysToAdd ?? [],
      workoutDaysToRemove: dto.workoutDaysToRemove ?? [],
    });
  }

  @Delete(':planId')
  deletePlan(
    @Param('planId', ParseIntPipe) planId: number,
    @CurrentUser() user: CurrentAuthUser,
  ) {
    return this.plansService.deletePlan(user.id, planId);
  }

  @Patch(':planId/activate')
  activatePlan(
    @Param('planId', ParseIntPipe) planId: number,
    @CurrentUser() user: CurrentAuthUser,
  ) {
    return this.plansService.activatePlan(user.id, planId);
  }
}
