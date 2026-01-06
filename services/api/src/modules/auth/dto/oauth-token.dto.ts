import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsEnum,
  ValidateIf,
} from 'class-validator';
import { Transform } from 'class-transformer';
import { OAuthProvider } from '../auth.constants';

export class OauthTokenDto {
  @IsString()
  @IsOptional()
  platform?: string;

  @Transform(({ value }: { value?: string }) => value?.toLowerCase())
  @IsEnum(OAuthProvider, {
    message: `provider must be one of: ${Object.values(OAuthProvider).join(', ')}`,
  })
  @IsNotEmpty()
  provider: OAuthProvider;

  @ValidateIf((o: OauthTokenDto) => o.provider === OAuthProvider.GOOGLE)
  @IsString()
  @IsNotEmpty()
  code?: string;

  @ValidateIf((o: OauthTokenDto) => o.provider === OAuthProvider.APPLE)
  @IsString()
  @IsNotEmpty()
  idToken?: string;
}
