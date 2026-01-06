import { Module } from '@nestjs/common';
import { AuthController } from './auth.controller';
import { JwtModule } from '@nestjs/jwt';
import { LocalStrategy } from './strategies/local.strategy';
import { JwtStrategy } from './strategies/jwt.strategy';
import { PassportModule } from '@nestjs/passport';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuthenticationService } from './services/authentication.service';
import { TokenManagementService } from './services/token-management.service';
import { OAuthService } from './services/oauth.service';
import { AppleAuthService } from './services/apple-auth.service';
import { GoogleAuthService } from './services/google-auth.service';
import { ForgotPasswordService } from './services/forgot-password.service';

@Module({
  imports: [
    PassportModule,
    JwtModule.registerAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        secret: configService.getOrThrow<string>('JWT_SECRET'),
        signOptions: {
          expiresIn: '15m',
          issuer: configService.get<string>('JWT_ISSUER', 'athleta-api'),
        },
      }),
      inject: [ConfigService],
    }),
  ],
  providers: [
    AppleAuthService,
    GoogleAuthService,
    ForgotPasswordService,
    AuthenticationService,
    TokenManagementService,
    OAuthService,
    LocalStrategy,
    JwtStrategy,
  ],
  controllers: [AuthController],
})
export class AuthModule {}
