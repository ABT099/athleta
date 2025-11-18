import {
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Query,
} from '@nestjs/common';
import { ExerciseService } from './exercise.service';
import { SubstitutionFiltersDto } from './dto/substitution-filters.dto';
import { SubstitutionResultDto } from './dto/substitution-result.dto';

@Controller('exercises')
export class ExerciseController {
  constructor(private readonly exerciseService: ExerciseService) {}

  @Get(':exerciseId/substitutions')
  async getSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Query() filters: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    return this.exerciseService.findSubstitutions(exerciseId, filters);
  }

  @Get(':exerciseId/substitutions/athlete/:athleteId')
  async getPersonalizedSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Param('athleteId', ParseIntPipe) athleteId: number,
    @Query() filters: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    return this.exerciseService.findPersonalizedSubstitutions(
      exerciseId,
      athleteId,
      filters,
    );
  }
}

