import { Body, Controller, Post } from '@nestjs/common';
import { CreatePlanDto } from './dto/create-plan.dto';
import { PlansService } from './plans.service';
import { CurrentUser } from 'src/decorators/user.decorator';

@Controller('plans')
export class PlansController {
  constructor(private readonly plansService: PlansService) {}

  @Post()
  createPlan(@Body() dto: CreatePlanDto, @CurrentUser() user) {
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
}
