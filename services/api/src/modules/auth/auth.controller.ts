import { Controller, Get, Post, Request, UseGuards, Body, Query, Res, UseInterceptors } from '@nestjs/common';
import { AuthenticationService } from './services/authentication.service';
import { TokenManagementService } from './services/token-management.service';
import { OAuthService } from './services/oauth.service';
import { LocalAuthGuard } from './guards/local-auth.guard';
import { RefreshTokenDto } from './dto/refresh-token.dto';
import { AllowAnonymous } from './guards/allow-anonymous';
import type { Response } from 'express';
import { NoFilesInterceptor } from '@nestjs/platform-express';
import { OauthTokenDto } from './dto/oauth-token.dto';
import { ForgotPasswordDto } from './dto/forgot-passwod.dto';
import { ForgotPasswordService } from './services/forgot-password.service';
import { VerifyResetPasswordCodeDto } from './dto/verify-reset-password-code.dto';
import { ResetPasswordDto } from './dto/reset-password.dto';
import { OauthRegisterDto } from './dto/oauth-register.dto';
import { RegisterDto } from './dto/register.dto';

@Controller('auth')
export class AuthController {
  constructor(
    private readonly authenticationService: AuthenticationService,
    private readonly tokenManagementService: TokenManagementService,
    private readonly oauthService: OAuthService,
    private readonly forgotPasswordService: ForgotPasswordService,
  ) {}

  @UseGuards(LocalAuthGuard)
  @Post('login')
  async login(@Request() req) {
    return this.authenticationService.login(req.user);
  }

  @AllowAnonymous()
  @Post('register')
  async register(@Body() registerDto: RegisterDto) {
    return this.authenticationService.register({
      firstName: registerDto.firstName,
      lastName: registerDto.lastName,
      email: registerDto.email,
      password: registerDto.password,
    }, {  
      age: registerDto.age,
      gender: registerDto.gender,
      weight: registerDto.weight,
      trainingExperience: registerDto.trainingExperience,
    });
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
      oauthTokenDto.provider,
      oauthTokenDto.code ?? oauthTokenDto.idToken!,
    );
    return token;
  }

  @AllowAnonymous()
  @Post('oauth/register')
  async oauthRegister(@Body() oauthRegisterDto: OauthRegisterDto) {
    const token = await this.oauthService.registerOAuth(
      oauthRegisterDto.token.provider,
      oauthRegisterDto.token.code ?? oauthRegisterDto.token.idToken!,
      {
        age: oauthRegisterDto.age,
        gender: oauthRegisterDto.gender,
        weight: oauthRegisterDto.weight,
        trainingExperience: oauthRegisterDto.trainingExperience,
      },
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

  @AllowAnonymous()
  @Post('forgot-password')
  async forgotPassword(@Body() forgotPasswordDto: ForgotPasswordDto) {
    await this.forgotPasswordService.sendResetPasswordEmail(
      forgotPasswordDto.email,
    );
    return { message: 'Reset password email sent' };
  }

  @AllowAnonymous()
  @Post('forgot-password/verify')
  async verifyResetPasswordCode(
    @Body() verifyResetPasswordCodeDto: VerifyResetPasswordCodeDto,
  ) {
    await this.forgotPasswordService.verifyResetPasswordCode(
      verifyResetPasswordCodeDto.code,
    );
    return { message: 'Reset password code verified' };
  }

  @AllowAnonymous()
  @Post('forgot-password/reset')
  async resetPassword(@Body() resetPasswordDto: ResetPasswordDto) {
    await this.forgotPasswordService.resetPassword(
      resetPasswordDto.email,
      resetPasswordDto.password,
    );
    return { message: 'Password reset successfully' };
  }
}
