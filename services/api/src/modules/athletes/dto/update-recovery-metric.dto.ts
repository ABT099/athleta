import { IsInt, IsNumber, IsOptional, IsString } from 'class-validator';

export class UpdateRecoveryMetricDto {
  @IsOptional()
  @IsString()
  sleepQuality?: string;

  @IsOptional()
  @IsString()
  date?: string;

  @IsOptional()
  @IsNumber()
  sleepHours?: number;

  @IsOptional()
  @IsInt()
  overallSoreness?: number;

  @IsOptional()
  @IsString()
  muscleSoreness?: string;

  @IsOptional()
  @IsInt()
  stressLevel?: number;

  @IsOptional()
  @IsInt()
  energyLevel?: number;

  @IsOptional()
  @IsString()
  nutritionAdherence?: string;

  @IsOptional()
  @IsString()
  hydrationLevel?: string;

  @IsOptional()
  @IsString()
  notes?: string;
}
