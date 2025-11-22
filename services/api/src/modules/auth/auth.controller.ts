import { Controller, Get, Post, Request, UseGuards, Body, Query, Res, UseInterceptors } from '@nestjs/common';
import { AuthenticationService } from './services/authentication.service';
import { TokenManagementService } from './services/token-management.service';
import { OAuthProvider, OAuthService } from './services/oauth.service';
import { LocalAuthGuard } from './guards/local-auth.guard';
import { RefreshTokenDto } from './dto/refresh-token.dto';
import { AllowAnonymous } from './guards/allow-anonymous';
import type { Response } from 'express';
import { NoFilesInterceptor } from '@nestjs/platform-express';
import { OauthTokenDto } from './dto/oauth-token.dto';

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

  @AllowAnonymous()
  @Get('oauth')
  async oauth(@Query() query: Record<string, string>, @Res() res: Response) {
    const params = new URLSearchParams(query);
    const redirectUrl = await this.oauthService.startOAuth(params);
    return res.redirect(redirectUrl);
  }

  @AllowAnonymous()
  @Get('oauth/callback')
  async oauthCallback(
    @Query() query: Record<string, string>,
    @Res() res: Response,
  ) {
    const params = new URLSearchParams(query);
    const redirectUrl = await this.oauthService.handleOAuthCallback(params);
    return res.redirect(redirectUrl);
  }

  @AllowAnonymous()
  @Post('oauth/token')
  @UseInterceptors(NoFilesInterceptor())
  async oauthToken(@Body() oauthTokenDto: OauthTokenDto) {
    const token = await this.oauthService.getOAuthToken(
      oauthTokenDto.code,
      oauthTokenDto.provider,
    );
    return token;
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
