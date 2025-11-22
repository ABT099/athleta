import { IsNotEmpty, IsOptional, IsString } from "class-validator";

export class OauthTokenDto {
  @IsString()
  @IsNotEmpty()
  code: string;

  @IsString()
  @IsOptional()
  platform?: string;

  @IsString()
  @IsOptional()
  provider?: string;
}