import { Controller, Get, Post, Request, UseGuards, Body } from '@nestjs/common';
import { AuthenticationService } from './services/authentication.service';
import { TokenManagementService } from './services/token-management.service';
import { LocalAuthGuard } from './guards/local-auth.guard';
import { AuthGuard } from '@nestjs/passport';
import { GoogleAuthGuard } from './guards/google-auth.guard';
import { AppleAuthGuard } from './guards/apple-auth.guard';
import { JwtAuthGuard } from './guards/jwt-auth.guard';
import { RefreshTokenDto } from './dto/refresh-token.dto';

@Controller('auth')
export class AuthController {
  constructor(
    private readonly authenticationService: AuthenticationService,
    private readonly tokenManagementService: TokenManagementService,
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

  @Post('refresh')
  async refresh(@Body() refreshTokenDto: RefreshTokenDto) {
    return this.tokenManagementService.refreshAccessToken(
      refreshTokenDto.refresh_token,
    );
  }

  @UseGuards(JwtAuthGuard)
  @Post('logout')
  async logout(@Body() refreshTokenDto: RefreshTokenDto) {
    await this.tokenManagementService.revokeRefreshToken(
      refreshTokenDto.refresh_token,
    );
    return { message: 'Logged out successfully' };
  }
}
