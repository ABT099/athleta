import { IsEnum, IsNotEmpty, IsNumber, ValidateNested } from 'class-validator';
import { OauthTokenDto } from './oauth-token.dto';
import { Transform, Type } from 'class-transformer';
import { Gender, TrainingExperience, WeightUnit } from 'src/constants';

export class OauthRegisterDto {
  @ValidateNested()
  @Type(() => OauthTokenDto)
  @IsNotEmpty()
  token: OauthTokenDto;

  @IsNumber()
  @IsNotEmpty()
  age: number;

  @IsEnum(Gender)
  @IsNotEmpty()
  gender: Gender;

  @IsNumber()
  @IsNotEmpty()
  @Transform(({ obj }: { obj: OauthRegisterDto }) =>
    obj.weightUnit === WeightUnit.LBS ? obj.weight * 0.453592 : obj.weight,
  )
  weight: number;

  @IsEnum(WeightUnit)
  @IsNotEmpty()
  weightUnit: WeightUnit;

  @IsEnum(TrainingExperience)
  @IsNotEmpty()
  trainingExperience: TrainingExperience;
}
