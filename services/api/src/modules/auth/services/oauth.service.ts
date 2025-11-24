import {
  Injectable,
  BadRequestException,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { UsersService } from '../../users/users.service';
import axios from 'axios';
import { AuthenticationService } from './authentication.service';
import { jwtDecode } from 'jwt-decode';
import * as jwt from 'jsonwebtoken';
import * as jwksClient from 'jwks-rsa';

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
  private readonly appleJwksClient: jwksClient.JwksClient;
  private readonly appleClientId: string;
  private readonly googleClientId: string;
  private readonly googleClientSecret: string;
  private readonly appScheme: string;
  private readonly webBaseUrl: string;
  private readonly oAuthRedirectUri: string;

  constructor(
    private readonly usersService: UsersService,
    private readonly configService: ConfigService,
    private readonly authenticationService: AuthenticationService,
  ) {
    this.appleClientId =
      this.configService.getOrThrow<string>('APPLE_CLIENT_ID');
    this.googleClientId =
      this.configService.getOrThrow<string>('GOOGLE_CLIENT_ID');
    this.googleClientSecret = this.configService.getOrThrow<string>(
      'GOOGLE_CLIENT_SECRET',
    );
    this.appScheme = this.configService.getOrThrow<string>('EXPO_APP_SCHEME');
    this.webBaseUrl = this.configService.getOrThrow<string>('WEB_BASE_URL');
    this.oAuthRedirectUri =
      this.configService.getOrThrow<string>('OAUTH_REDIRECT_URI');

    this.appleJwksClient = jwksClient.default({
      jwksUri: 'https://appleid.apple.com/auth/keys',
      cache: true,
      cacheMaxAge: 86400000,
    });
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
    if (provider == OAuthProvider.GOOGLE) {
      const response = await axios.post(
        'https://oauth2.googleapis.com/token',
        new URLSearchParams({
          code: identifier,
          client_id: this.googleClientId,
          client_secret: this.googleClientSecret,
          redirect_uri: this.oAuthRedirectUri,
          grant_type: 'authorization_code',
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        },
      );

      const data = response.data;

      if (!data.id_token) {
        throw new BadRequestException('Invalid Google OAuth response');
      }

      const decoded: any = jwtDecode(data.id_token);
      const profile: OAuthUserProfile = {
        id: decoded.sub,
        email: decoded.email,
        name: {
          givenName: decoded.given_name,
          familyName: decoded.family_name,
        },
      };

      const user = await this.validateOrCreateGoogleUser(profile);

      const { access_token, refresh_token } =
        await this.authenticationService.login({ id: user.id });

      return {
        access_token,
        refresh_token,
      };
    } else if (provider == OAuthProvider.APPLE) {
      const profile = await this.verifyAppleIdToken(identifier);
      const user = await this.validateOrCreateAppleUser(profile);
      const { access_token, refresh_token } =
        await this.authenticationService.login({ id: user.id });

      return {
        access_token,
        refresh_token,
      };
    }
  }

  private async validateOrCreateGoogleUser(profile: OAuthUserProfile) {
    const googleId = profile.id;
    const email = profile.emails?.[0]?.value || profile.email;
    const firstName = profile.name?.givenName || '';
    const lastName = profile.name?.familyName || '';

    // Try to find user by Google ID first
    let user = await this.usersService.findByGoogleId(googleId);

    if (user) {
      return user;
    }

    // Try to find user by email
    const existingUser = await this.usersService.findOne(email);
    if (existingUser) {
      // Link Google ID to existing user
      user = await this.usersService.updateOAuthId(existingUser.id, googleId);
      return user;
    }

    // Create new user
    user = await this.usersService.createOAuthUser({
      email,
      firstName,
      lastName,
      googleId,
    });

    return user;
  }

  private async validateOrCreateAppleUser(
    profile: OAuthUserProfile,
    idToken?: { sub?: string },
  ) {
    // Apple user ID is in the idToken.sub field
    const appleId = idToken?.sub || profile.id;
    const email = profile.email;
    const firstName = profile.name?.firstName || profile.name?.givenName || '';
    const lastName = profile.name?.lastName || profile.name?.familyName || '';

    // Try to find user by Apple ID first (this works even without email)
    let user = await this.usersService.findByAppleId(appleId);

    if (user) {
      return user;
    }

    // Apple only sends email on first sign-in, so this might be empty
    if (email) {
      const existingUser = await this.usersService.findOne(email);
      if (existingUser) {
        // Link Apple ID to existing user
        user = await this.usersService.updateOAuthId(
          existingUser.id,
          undefined,
          appleId,
        );
        return user;
      }
    }

    // Only create new user if we have an email
    // Apple should always provide email on first sign-in
    if (!email) {
      throw new BadRequestException(
        'Email is required for new Apple sign-in. Please sign in again.',
      );
    }

    // Create new user
    user = await this.usersService.createOAuthUser({
      email,
      firstName,
      lastName,
      appleId,
    });

    return user;
  }

  async verifyAppleIdToken(idToken: string): Promise<OAuthUserProfile> {
    try {
      // Decode the token to get the header (without verification)
      const decoded = jwt.decode(idToken, { complete: true });
      if (!decoded || typeof decoded === 'string') {
        throw new UnauthorizedException('Invalid Apple ID token');
      }

      const kid = decoded.header.kid;
      if (!kid) {
        throw new UnauthorizedException('Invalid Apple ID token: missing kid');
      }

      // Get the signing key from Apple's JWKS
      const key = await this.appleJwksClient.getSigningKey(kid);
      const signingKey = key.getPublicKey();

      // Verify the token
      const payload = jwt.verify(idToken, signingKey, {
        algorithms: ['RS256'],
        audience: this.appleClientId,
        issuer: 'https://appleid.apple.com',
      }) as jwt.JwtPayload;

      if (!payload.sub) {
        throw new UnauthorizedException('Invalid Apple ID token');
      }

      // Extract user information from the token
      // Note: Apple only sends email on first sign-in, so it might be missing
      const email = payload.email || '';
      const name = payload.name
        ? {
            firstName: payload.name.firstName,
            lastName: payload.name.lastName,
            givenName: payload.name.firstName,
            familyName: payload.name.lastName,
          }
        : undefined;

      return {
        id: payload.sub,
        email,
        name,
      };
    } catch (error) {
      if (error instanceof UnauthorizedException) {
        throw error;
      }
      if (error instanceof jwt.JsonWebTokenError) {
        throw new UnauthorizedException('Invalid Apple ID token');
      }
      throw new UnauthorizedException('Invalid Apple ID token');
    }
  }
}