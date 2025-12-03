import {
  Injectable,
  BadRequestException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { AuthenticationService } from './authentication.service';
import { AppleAuthService } from './apple-auth.service';
import { GoogleAuthService } from './google-auth.service';

export interface OAuthUserProfile {
  id: string;
  email: string;
  name?: {
    givenName?: string;
    familyName?: string;
    firstName?: string;
    lastName?: string;
  };
  emails?: Array<{ value: string }>;
}

export enum OAuthProvider {
  GOOGLE = 'google',
  APPLE = 'apple',
}
@Injectable()
export class OAuthService {
  private readonly appleClientId: string;
  private readonly googleClientId: string;
  private readonly appScheme: string;
  private readonly webBaseUrl: string;
  private readonly oAuthRedirectUri: string;

  constructor(
    private readonly configService: ConfigService,
    private readonly authenticationService: AuthenticationService,
    private readonly appleAuthService: AppleAuthService,
    private readonly googleAuthService: GoogleAuthService,
  ) {
    this.appleClientId =
      this.configService.getOrThrow<string>('APPLE_CLIENT_ID');
    this.googleClientId =
      this.configService.getOrThrow<string>('GOOGLE_CLIENT_ID');
    this.appScheme = this.configService.getOrThrow<string>('EXPO_APP_SCHEME');
    this.webBaseUrl = this.configService.getOrThrow<string>('WEB_BASE_URL');
    this.oAuthRedirectUri =
      this.configService.getOrThrow<string>('OAUTH_REDIRECT_URI');
  }

  async startOAuth(params: URLSearchParams) {
    let idpClient: string;
    const internalClient = params.get('client_id');
    const redirectUri = params.get('redirect_uri');
    let redirectTo: string;

    let platform: 'mobile' | 'web';

    if (redirectUri === this.appScheme) {
      if (internalClient === OAuthProvider.APPLE) {
        throw new BadRequestException(
          'This endpoint is only available for web Apple clients',
        );
      }
      platform = 'mobile';
    } else if (redirectUri === this.webBaseUrl) {
      platform = 'web';
    } else {
      throw new BadRequestException('Invalid redirect URI');
    }

    let state = platform + '|' + params.get('state');

    if (internalClient == OAuthProvider.GOOGLE) {
      idpClient = this.googleClientId;
      redirectTo = 'https://accounts.google.com/o/oauth2/v2/auth';
    } else if (internalClient == OAuthProvider.APPLE) {
      idpClient = this.appleClientId;
      redirectTo = 'https://appleid.apple.com/auth/authorize';
    } else {
      throw new BadRequestException('Invalid client ID');
    }

    const paramsToSend = new URLSearchParams({
      client_id: idpClient,
      redirect_uri: this.oAuthRedirectUri,
      response_type: 'code',
      scope: params.get('scope') || 'identity',
      state: state,
    });

    return redirectTo + '?' + paramsToSend.toString();
  }

  async handleOAuthCallback(incomingParams: URLSearchParams) {
    const combinedPlatformAndState = incomingParams.get('state');

    if (!combinedPlatformAndState) {
      throw new BadRequestException('Missing state parameter');
    }

    const [platform, state] = combinedPlatformAndState.split('|');

    const outgoingParams = new URLSearchParams({
      code: incomingParams.get('code') || '',
      state: state,
    });

    return (
      (platform === 'mobile' ? this.appScheme : this.webBaseUrl) +
      '?' +
      outgoingParams.toString()
    );
  }

  async getOAuthToken(
    provider: OAuthProvider,
    identifier: string
  ) {

    let userInfo: { id: number, hasInitialPlan: boolean } | null = null;

    if (provider == OAuthProvider.GOOGLE) {
      userInfo = await this.googleAuthService.validateGoogleUser(identifier);
    } else if (provider == OAuthProvider.APPLE) {
      userInfo = await this.appleAuthService.validateAppleUser(identifier);
    }

    if (!userInfo) {
      throw new BadRequestException('Failed to validate or create user');
    }

    return await this.authenticationService.login(userInfo);
  }

  async registerOAuth(provider: OAuthProvider, identifier: string, athlete: {
    age: number,
    gender: 'male' | 'female',
    weight: number,
    trainingExperience: 'beginner' | 'intermediate' | 'advanced',
  }) {

    let userInfo: { id: number, hasInitialPlan: boolean } | null = null;

    if (provider == OAuthProvider.GOOGLE) {
      userInfo = await this.googleAuthService.registerWithGoogle(identifier, athlete);
    } else if (provider == OAuthProvider.APPLE) {
      userInfo = await this.appleAuthService.registerWithApple(identifier, athlete);
    }

    if (!userInfo) {
      throw new BadRequestException('Failed to register user');
    }

    return await this.authenticationService.login(userInfo);
  }
}