import { IsNotEmpty, IsOptional, IsString, IsEnum, ValidateIf } from "class-validator";
import { Transform } from "class-transformer";
import { OAuthProvider } from "../services/oauth.service";

export class OauthTokenDto {
  @IsString()
  @IsOptional()
  platform?: string;

  @Transform(({ value }) => value?.toLowerCase())
  @IsEnum(OAuthProvider, {
    message: `provider must be one of: ${Object.values(OAuthProvider).join(', ')}`,
  })
  @IsNotEmpty()
  provider: OAuthProvider;

  @ValidateIf((o) => o.provider === OAuthProvider.GOOGLE)
  @IsString()
  @IsNotEmpty()
  code?: string;

  @ValidateIf((o) => o.provider === OAuthProvider.APPLE)
  @IsString()
  @IsNotEmpty()
  idToken?: string;
}