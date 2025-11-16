import {
  IsOptional,
  IsArray,
  IsNumber,
  Min,
  Max,
  IsString,
} from 'class-validator';
import { Type } from 'class-transformer';

export class SubstitutionFiltersDto {
  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  availableEquipment?: string[];

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(2)
  @Type(() => Number)
  maxComplexity?: number;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(3)
  @Type(() => Number)
  maxInjuryRisk?: number;

  @IsOptional()
  @IsArray()
  @IsNumber({}, { each: true })
  @Type(() => Number)
  excludeIds?: number[];

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  excludeJointStress?: string[];

  @IsOptional()
  @IsNumber()
  @Min(1)
  @Max(20)
  @Type(() => Number)
  limit?: number = 5;
}

