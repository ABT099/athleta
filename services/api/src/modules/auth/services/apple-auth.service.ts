import {
  Inject,
  Injectable,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { DRIZZLE } from 'src/modules/common/database/database.provider';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';
import type { OAuthUserProfile } from '../auth.types';
import { eq, or } from 'drizzle-orm';
import * as jwt from 'jsonwebtoken';
import * as jwksClient from 'jwks-rsa';
import { ConfigService } from '@nestjs/config';
import { athletes, users } from 'src/db/schema';

interface AppleJwtPayload extends jwt.JwtPayload {
  email?: string;
  name?: {
    firstName?: string;
    lastName?: string;
  };
}

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

  async validateAppleUser(idToken: string) {
    const profile = await this.verifyAppleIdToken(idToken);

    // Apple user ID is in the idToken.sub field
    const appleId = profile.id;
    const email = profile.email;

    const existingUser = await this.db
      .select({
        id: users.id,
        appleId: users.appleId,
        hasInitialPlan: users.hasInitialPlan,
      })
      .from(users)
      .where(
        email
          ? or(eq(users.appleId, appleId), eq(users.email, email))
          : eq(users.appleId, appleId),
      )
      .limit(1)
      .then((rows) => rows[0]);

    if (!existingUser) {
      throw new NotFoundException('User not found');
    }

    if (existingUser.appleId === appleId) {
      return {
        id: existingUser.id,
        hasInitialPlan: existingUser.hasInitialPlan,
      };
    }

    await this.db
      .update(users)
      .set({ appleId })
      .where(eq(users.id, existingUser.id))
      .returning({
        id: users.id,
        hasInitialPlan: users.hasInitialPlan,
      })
      .then((rows) => rows[0]);

    return { id: existingUser.id, hasInitialPlan: existingUser.hasInitialPlan };
  }

  async registerWithApple(
    identifier: string,
    athlete: {
      age: number;
      gender: 'male' | 'female';
      weight: number;
      trainingExperience: 'beginner' | 'intermediate' | 'advanced';
    },
  ) {
    const profile = await this.verifyAppleIdToken(identifier);
    const appleId = profile.id;
    const email = profile.email;
    const firstName = profile.name?.firstName || profile.name?.givenName || '';
    const lastName = profile.name?.lastName || profile.name?.familyName || '';

    const existingUser = await this.db
      .select({
        id: users.id,
        appleId: users.appleId,
        hasInitialPlan: users.hasInitialPlan,
      })
      .from(users)
      .where(or(eq(users.appleId, appleId), eq(users.email, email)))
      .limit(1)
      .then((rows) => rows[0]);

    if (existingUser) {
      return await this.db.transaction(async (tx) => {
        if (existingUser.appleId !== appleId) {
          await tx
            .update(users)
            .set({
              appleId,
            })
            .where(eq(users.id, existingUser.id));
        }

        // Check if athlete record exists
        const existingAthlete = await tx
          .select({ id: athletes.id })
          .from(athletes)
          .where(eq(athletes.userId, existingUser.id))
          .limit(1)
          .then((rows) => rows[0]);

        if (existingAthlete) {
          // Update existing athlete record
          await tx
            .update(athletes)
            .set({
              age: athlete.age,
              gender: athlete.gender,
              trainingExperience: athlete.trainingExperience,
              bodyWeightKg: athlete.weight,
            })
            .where(eq(athletes.userId, existingUser.id));
        } else {
          // Insert new athlete record
          await tx.insert(athletes).values({
            userId: existingUser.id,
            age: athlete.age,
            gender: athlete.gender,
            trainingExperience: athlete.trainingExperience,
            bodyWeightKg: athlete.weight,
          });
        }

        return {
          id: existingUser.id,
          hasInitialPlan: existingUser.hasInitialPlan,
        };
      });
    }

    return await this.db.transaction(async (tx) => {
      const newUserId = await tx
        .insert(users)
        .values({
          email,
          firstName,
          lastName,
          role: 'user',
          appleId,
        })
        .returning({ id: users.id })
        .then((rows) => rows[0].id);

      await tx.insert(athletes).values({
        userId: newUserId,
        age: athlete.age,
        gender: athlete.gender,
        trainingExperience: athlete.trainingExperience,
        bodyWeightKg: athlete.weight,
      });

      return { id: newUserId, hasInitialPlan: false };
    });
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
      }) as AppleJwtPayload;

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
