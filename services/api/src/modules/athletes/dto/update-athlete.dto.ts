import { Transform } from 'class-transformer';
import { IsEnum, IsNumber, IsOptional } from 'class-validator';
import { Gender, TrainingExperience, WeightUnit } from 'src/constants';

export class UpdateAthleteDto {
  @IsOptional()
  @IsNumber()
  age?: number;

  @IsOptional()
  @IsEnum(Gender)
  gender?: Gender;

  @IsOptional()
  @IsEnum(TrainingExperience)
  trainingExperience?: TrainingExperience;

  // Normalised to kg on the way in, mirroring register.dto.ts. The transform
  // short-circuits when weight is absent so a stray weightUnit can't yield NaN.
  @IsOptional()
  @IsNumber()
  @Transform(({ obj }: { obj: UpdateAthleteDto }) =>
    obj.weight === undefined
      ? undefined
      : obj.weightUnit === WeightUnit.LBS
        ? obj.weight * 0.453592
        : obj.weight,
  )
  weight?: number;

  // Declared so the whitelist pipe doesn't reject it; used only by the transform.
  @IsOptional()
  @IsEnum(WeightUnit)
  weightUnit?: WeightUnit;
}
