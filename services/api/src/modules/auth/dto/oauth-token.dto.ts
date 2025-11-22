import { IsNotEmpty, IsOptional, IsString, IsEnum } from "class-validator";
import { Transform } from "class-transformer";
import { OAuthProvider } from "../services/oauth.service";

export class OauthTokenDto {
  @IsString()
  @IsNotEmpty()
  code: string;

  @IsString()
  @IsOptional()
  platform?: string;

  @Transform(({ value }) => value?.toLowerCase())
  @IsEnum(OAuthProvider, {
    message: `provider must be one of: ${Object.values(OAuthProvider).join(', ')}`,
  })
  @IsNotEmpty()
  provider: OAuthProvider;
}