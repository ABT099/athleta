import { Controller, Get, Post, Request, UseGuards, Body, Query } from '@nestjs/common';
import { AuthenticationService } from './services/authentication.service';
import { TokenManagementService } from './services/token-management.service';
import { OAuthService } from './services/oauth.service';
import { LocalAuthGuard } from './guards/local-auth.guard';
import { GoogleAuthGuard } from './guards/google-auth.guard';
import { AppleAuthGuard } from './guards/apple-auth.guard';
import { RefreshTokenDto } from './dto/refresh-token.dto';
import { AppleMobileDto } from './dto/apple-mobile.dto';
import { AllowAnonymous } from './guards/allow-anonymous';

@Controller('auth')
export class AuthController {
  constructor(
    private readonly authenticationService: AuthenticationService,
    private readonly tokenManagementService: TokenManagementService,
    private readonly oauthService: OAuthService,
  ) {}

  @UseGuards(LocalAuthGuard)
  @Post('login')
  async login(@Request() req) {
    return this.authenticationService.login(req.user);
  }

  @Get('google')
  @UseGuards(GoogleAuthGuard)
  async googleAuth() {}

  @Get('google/callback')
  @UseGuards(GoogleAuthGuard)
  async googleAuthCallback(@Request() req) {
    return this.authenticationService.login(req.user);
  }

  @Get('apple')
  @UseGuards(AppleAuthGuard)
  async appleAuth() {}

  @Get('apple/callback')
  @UseGuards(AppleAuthGuard)
  async appleAuthCallback(@Request() req) {
    return this.authenticationService.login(req.user);
  }

  @AllowAnonymous()
  @Post('apple/mobile')
  async appleMobileAuth(@Body() appleMobileDto: AppleMobileDto) {
    const profile = await this.oauthService.verifyAppleIdToken(
      appleMobileDto.idToken,
    );
    const user = await this.oauthService.validateAppleUser(profile, {
      sub: profile.id,
    });
    return this.authenticationService.login(user);
  }

  @AllowAnonymous()
  @Post('refresh')
  async refresh(@Body() refreshTokenDto: RefreshTokenDto) {
    return this.tokenManagementService.refreshAccessToken(
      refreshTokenDto.refresh_token,
    );
  }

  @Post('logout')
  async logout(@Body() refreshTokenDto: RefreshTokenDto) {
    await this.tokenManagementService.revokeRefreshToken(
      refreshTokenDto.refresh_token,
    );
    return { message: 'Logged out successfully' };
  }
}
