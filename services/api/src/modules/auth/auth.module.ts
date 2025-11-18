import { Module } from '@nestjs/common';
import { AuthController } from './auth.controller';
import { UsersModule } from '../users/users.module';
import { JwtModule } from '@nestjs/jwt';
import { jwtConstants } from './constants';
import { LocalStrategy } from './strategies/local.strategy';
import { JwtStrategy } from './strategies/jwt.strategy';
import { PassportModule } from '@nestjs/passport';
import { ConfigModule } from '@nestjs/config';
import { GoogleStrategy } from './strategies/google.strategy';
import { AppleStrategy } from './strategies/apple.strategy';
import { AuthenticationService } from './services/authentication.service';
import { TokenManagementService } from './services/token-management.service';
import { OAuthService } from './services/oauth.service';

@Module({
  imports: [
    ConfigModule,
    UsersModule,
    PassportModule,
    JwtModule.register({
      secret: jwtConstants.secret,
      signOptions: { expiresIn: '15m' }, // 15 minutes for access token
    }),
  ],
  providers: [
    AuthenticationService,
    TokenManagementService,
    OAuthService,
    LocalStrategy,
    JwtStrategy,
    GoogleStrategy,
    AppleStrategy,
  ],
  controllers: [AuthController],
})
export class AuthModule {}
