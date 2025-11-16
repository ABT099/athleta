import {
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Query,
} from '@nestjs/common';
import { ExerciseSubstitutionService } from './exercise-substitution.service';
import { SubstitutionFiltersDto } from './dto/substitution-filters.dto';
import { SubstitutionResultDto } from './dto/substitution-result.dto';

@Controller('exercises')
export class ExerciseController {
  constructor(
    private readonly substitutionService: ExerciseSubstitutionService,
  ) {}

  @Get(':exerciseId/substitutions')
  async getSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Query() filters: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    return this.substitutionService.findSubstitutions(exerciseId, filters);
  }

  @Get(':exerciseId/substitutions/athlete/:athleteId')
  async getPersonalizedSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Param('athleteId', ParseIntPipe) athleteId: number,
    @Query() filters: SubstitutionFiltersDto,
  ): Promise<SubstitutionResultDto[]> {
    return this.substitutionService.findPersonalizedSubstitutions(
      exerciseId,
      athleteId,
      filters,
    );
  }
}

