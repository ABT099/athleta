import { Controller, Get, Param, ParseIntPipe } from '@nestjs/common';
import { ExerciseService } from './exercise.service';
import { SubstitutionResult } from './exercise.types';

@Controller('exercises')
export class ExerciseController {
  constructor(private readonly exerciseService: ExerciseService) {}

  @Get(':exerciseId/substitutions/:athleteId')
  async findSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Param('athleteId', ParseIntPipe) athleteId: number,
  ): Promise<SubstitutionResult[]> {
    return this.exerciseService.findSubstitutions(exerciseId, {
      filters: {},
      athleteId,
    });
  }
}
