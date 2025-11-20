import {
  Injectable,
  UnauthorizedException,
  Logger,
  OnModuleInit,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { UsersService } from '../../users/users.service';
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

@Injectable()
export class OAuthService implements OnModuleInit {
  private readonly logger = new Logger(OAuthService.name);
  private appleJwksClient: jwksClient.JwksClient;
  private readonly appleClientId: string;

  constructor(
    private readonly usersService: UsersService,
    private readonly configService: ConfigService,
  ) {
    this.appleClientId = this.configService.getOrThrow<string>('APPLE_CLIENT_ID');
  }

  onModuleInit() {
    // Initialize Apple JWKS client
    this.appleJwksClient = jwksClient.default({
      jwksUri: 'https://appleid.apple.com/auth/keys',
      cache: true,
      cacheMaxAge: 86400000, // 24 hours
    });

    this.logger.log('OAuth service initialized');
  }

  async validateGoogleUser(profile: OAuthUserProfile) {
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

  async validateAppleUser(
    profile: OAuthUserProfile,
    idToken?: { sub?: string },
  ) {
    // Apple user ID is in the idToken.sub field
    const appleId = idToken?.sub || profile.id;
    const email = profile.email;
    const firstName = profile.name?.firstName || profile.name?.givenName || '';
    const lastName = profile.name?.lastName || profile.name?.familyName || '';

    // Try to find user by Apple ID first
    let user = await this.usersService.findByAppleId(appleId);

    if (user) {
      return user;
    }

    // Try to find user by email
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
        this.logger.warn('Apple ID token decode failed: invalid format');
        throw new UnauthorizedException('Invalid Apple ID token');
      }

      const kid = decoded.header.kid;
      if (!kid) {
        this.logger.warn('Apple ID token missing kid in header');
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
        this.logger.warn('Apple ID token missing subject (sub)');
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
        this.logger.warn(`Apple ID token verification failed: ${error.message}`);
        throw new UnauthorizedException('Invalid Apple ID token');
      }
      this.logger.error(`Apple ID token verification error: ${error.message}`);
      throw new UnauthorizedException('Invalid Apple ID token');
    }
  }
}
