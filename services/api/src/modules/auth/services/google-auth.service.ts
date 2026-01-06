import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { DRIZZLE } from 'src/modules/common/database/database.provider';
import type { DrizzleDB } from 'src/modules/common/database/database.provider';
import { ConfigService } from '@nestjs/config';
import { OAuthUserProfile } from '../auth.types';
import { jwtDecode } from 'jwt-decode';
import axios from 'axios';
import { athletes, users } from 'src/db/schema';
import { eq, or } from 'drizzle-orm';

type GoogleIdToken = {
  sub: string;
  email: string;
  given_name?: string;
  family_name?: string;
};

type GoogleTokenResponse = {
  access_token: string;
  id_token: string;
  expires_in: number;
  token_type: string;
  scope?: string;
  refresh_token?: string;
};

type AthleteRegistrationData = {
  age: number;
  gender: 'male' | 'female';
  weight: number;
  trainingExperience: 'beginner' | 'intermediate' | 'advanced';
};

@Injectable()
export class GoogleAuthService {
  private readonly googleClientId: string;
  private readonly googleClientSecret: string;
  private readonly oAuthRedirectUri: string;

  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly configService: ConfigService,
  ) {
    this.googleClientId =
      this.configService.getOrThrow<string>('GOOGLE_CLIENT_ID');
    this.googleClientSecret = this.configService.getOrThrow<string>(
      'GOOGLE_CLIENT_SECRET',
    );
    this.oAuthRedirectUri =
      this.configService.getOrThrow<string>('OAUTH_REDIRECT_URI');
  }

  async validateGoogleUser(code: string) {
    const profile = await this.authenticateWithGoogle(code);

    const googleId = profile.id;
    const email = profile.emails?.[0]?.value || profile.email;

    const existingUser = await this.db
      .select({
        id: users.id,
        googleId: users.googleId,
        hasInitialPlan: users.hasInitialPlan,
      })
      .from(users)
      .where(or(eq(users.googleId, googleId), eq(users.email, email)))
      .limit(1)
      .then((rows) => rows[0]);

    if (!existingUser) {
      throw new NotFoundException('User not found');
    }

    if (existingUser.googleId === googleId) {
      return {
        id: existingUser.id,
        hasInitialPlan: existingUser.hasInitialPlan,
      };
    }

    await this.db
      .update(users)
      .set({ googleId })
      .where(eq(users.id, existingUser.id));

    return { id: existingUser.id, hasInitialPlan: existingUser.hasInitialPlan };
  }

  async registerWithGoogle(code: string, athlete: AthleteRegistrationData) {
    const profile = await this.authenticateWithGoogle(code);
    const googleId = profile.id;
    const email = profile.emails?.[0]?.value || profile.email;
    const firstName = profile.name?.givenName || '';
    const lastName = profile.name?.familyName || '';

    const existingUser = await this.db
      .select({
        id: users.id,
        googleId: users.googleId,
        hasInitialPlan: users.hasInitialPlan,
      })
      .from(users)
      .where(or(eq(users.googleId, googleId), eq(users.email, email)))
      .limit(1)
      .then((rows) => rows[0]);

    if (existingUser) {
      return await this.db.transaction(async (tx) => {
        if (existingUser.googleId !== googleId) {
          await tx
            .update(users)
            .set({
              googleId,
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
          googleId,
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

  private async authenticateWithGoogle(code: string) {
    const response = await axios.post<GoogleTokenResponse>(
      'https://oauth2.googleapis.com/token',
      new URLSearchParams({
        code: code,
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

    const decoded = jwtDecode<GoogleIdToken>(data.id_token);
    const profile: OAuthUserProfile = {
      id: decoded.sub,
      email: decoded.email,
      name: {
        givenName: decoded.given_name,
        familyName: decoded.family_name,
      },
    };

    return profile;
  }
}
