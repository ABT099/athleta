import { Controller, Get, Param, ParseIntPipe } from '@nestjs/common';
import { AIEngineIntegration } from '../../integrations/ai-engine.integration';
import { ExerciseClientService } from './exercise-client.service';
import { Substitution } from './exercise.types';

@Controller('exercises')
export class ExerciseController {
  constructor(
    private readonly exerciseClient: ExerciseClientService,
    private readonly aiEngineIntegration: AIEngineIntegration,
  ) {}

  @Get(':exerciseId/substitutions/:athleteId')
  async findSubstitutions(
    @Param('exerciseId', ParseIntPipe) exerciseId: number,
    @Param('athleteId', ParseIntPipe) athleteId: number,
  ): Promise<Substitution[]> {
    // Athlete personalization stays in the api: the exercise service knows
    // exercises, not athletes. getJointStressProfile degrades to an empty
    // profile when the AI engine is unavailable.
    const jointProfile =
      await this.aiEngineIntegration.getJointStressProfile(athleteId);

    return this.exerciseClient.findSubstitutions(exerciseId, {
      excludeJointStress: jointProfile.avoidJoints,
    });
  }
}
