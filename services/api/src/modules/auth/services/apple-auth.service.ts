import { BadRequestException, Inject, Injectable, UnauthorizedException } from "@nestjs/common";
import { DRIZZLE } from "src/modules/database/database.provider";
import type { DrizzleDB } from "src/modules/database/database.provider";
import type { OAuthUserProfile } from "./oauth.service";
import { usersTable } from "src/db/schema";
import { eq, or } from "drizzle-orm";
import * as jwt from 'jsonwebtoken';
import * as jwksClient from 'jwks-rsa';
import { ConfigService } from "@nestjs/config";

@Injectable()
export class AppleAuthService {
  private readonly appleJwksClient: jwksClient.JwksClient;
  private readonly appleClientId: string;

  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly configService: ConfigService,
  ) {
    this.appleClientId =
      this.configService.getOrThrow<string>('APPLE_CLIENT_ID');
    this.appleJwksClient = jwksClient.default({
      jwksUri: 'https://appleid.apple.com/auth/keys',
      cache: true,
      cacheMaxAge: 86400000,
    });
  }

  async validateOrCreateAppleUser(idToken: string) {
    const profile = await this.verifyAppleIdToken(idToken);

    // Apple user ID is in the idToken.sub field
    const appleId = profile.id;
    const email = profile.email;
    const firstName = profile.name?.firstName || profile.name?.givenName || '';
    const lastName = profile.name?.lastName || profile.name?.familyName || '';

    // Single query to find user by appleId OR email (if email exists)
    const existingUser = await this.db
      .select({
        id: usersTable.id,
        appleId: usersTable.appleId,
      })
      .from(usersTable)
      .where(
        email 
          ? or(eq(usersTable.appleId, appleId), eq(usersTable.email, email))
          : eq(usersTable.appleId, appleId)
      )
      .limit(1)
      .then(rows => rows[0]);

    if (existingUser) {
      // User found by appleId - already linked
      if (existingUser.appleId === appleId) {
        return existingUser.id;
      }
      
      // User found by email - link Apple ID
      await this.db
        .update(usersTable)
        .set({ appleId })
        .where(eq(usersTable.id, existingUser.id));

      return existingUser.id;
    }

    // Only create new user if we have an email
    // Apple should always provide email on first sign-in
    if (!email) {
      throw new BadRequestException(
        'Email is required for new Apple sign-in. Please sign in again.',
      );
    }

    const newUser = await this.db
      .insert(usersTable)
      .values({
        email,
        firstName,
        lastName,
        role: 'user',
        appleId,
      })
      .returning({ id: usersTable.id })
      .then(rows => rows[0]);

    return newUser.id;
  }

  private async verifyAppleIdToken(idToken: string): Promise<OAuthUserProfile> {
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