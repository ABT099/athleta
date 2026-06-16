import type {
  AnalyzeSessionPayload,
  AnalyzeSessionResponse,
  JointStressProfileDto,
  PrescriptionRequestDto,
  PrescriptionResponseDto,
} from 'src/integrations/integrations.types';

/**
 * In-memory stand-in for {@link AutoRegulationServiceIntegration} (HTTP). Batch
 * prescriptions echo one canned response per request (so length validation in
 * the services passes); `analyzeSession` is overridable per-test via
 * {@link analyzeSessionImpl} so suites can drive PR write-backs or force a
 * failure to exercise the best-effort path.
 */
export function emptyAnalyzeResponse(
  sessionId = 0,
): AnalyzeSessionResponse {
  return {
    session_id: sessionId,
    adjustments: {},
    next_workout: {},
    performance_analysis: {},
    ai_insights: [],
    pr_updates: { updates: [] },
    calibration_factor: 1.0,
  };
}

export class FakeAutoReg {
  analyzeSessionImpl: (
    payload: AnalyzeSessionPayload,
  ) => Promise<AnalyzeSessionResponse> | AnalyzeSessionResponse = () =>
    emptyAnalyzeResponse();

  async generateBatchPrescriptions(
    prescriptions: PrescriptionRequestDto[],
  ): Promise<PrescriptionResponseDto[]> {
    return prescriptions.map(() => ({
      target_rpe: 8,
      target_rir: 2,
      rest_period_seconds: 120,
    }));
  }

  async generatePrescription(): Promise<PrescriptionResponseDto> {
    return { target_rpe: 8, target_rir: 2, rest_period_seconds: 120 };
  }

  async getJointStressProfile(): Promise<JointStressProfileDto> {
    return { avoidJoints: [], reason: 'test' };
  }

  async analyzeSession(
    payload: AnalyzeSessionPayload,
  ): Promise<AnalyzeSessionResponse> {
    return this.analyzeSessionImpl(payload);
  }
}
