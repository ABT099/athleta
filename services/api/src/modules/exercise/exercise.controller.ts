import { Controller, Get, Param, ParseIntPipe } from '@nestjs/common';
import { AutoRegulationServiceIntegration } from '../../integrations/auto-regulation-service.integration';
import { ExerciseClientService } from './exercise-client.service';
import { Substitution } from './exercise.types';

@Controller('exercises')
export class ExerciseController {
  constructor(
    private readonly exerciseClient: ExerciseClientService,
    private readonly autoRegulationServiceIntegration: AutoRegulationServiceIntegration,
  ) {}

  @Get(':exerciseId/substitutions/:athleteId')
  async findSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Param('athleteId', ParseIntPipe) athleteId: number,
  ): Promise<Substitution[]> {
    // Athlete personalization stays in the api: the exercise service knows
    // exercises, not athletes. getJointStressProfile degrades to an empty
    // profile when the auto-regulation service is unavailable.
    const jointProfile =
      await this.autoRegulationServiceIntegration.getJointStressProfile(athleteId);

    return this.exerciseClient.findSubstitutions(exerciseId, {
      excludeJointStress: jointProfile.avoidJoints,
    });
  }
}
