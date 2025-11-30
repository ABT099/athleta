import { BadRequestException, Inject, Injectable, NotFoundException } from "@nestjs/common";
import { DRIZZLE } from "src/modules/database/database.provider";
import type { DrizzleDB } from "src/modules/database/database.provider";
import { ConfigService } from "@nestjs/config";
import { OAuthUserProfile } from "./oauth.service";
import { jwtDecode } from "jwt-decode";
import axios from "axios";
import { athletesTable, usersTable } from "src/db/schema";
import { eq, or } from "drizzle-orm";

@Injectable()
export class GoogleAuthService {
    private readonly googleClientId: string;
    private readonly googleClientSecret: string;
    private readonly oAuthRedirectUri: string;

    constructor(
        @Inject(DRIZZLE) private readonly db: DrizzleDB,
        private readonly configService: ConfigService,
    ) {
        this.googleClientId = this.configService.getOrThrow<string>('GOOGLE_CLIENT_ID');
        this.googleClientSecret = this.configService.getOrThrow<string>('GOOGLE_CLIENT_SECRET');
        this.oAuthRedirectUri = this.configService.getOrThrow<string>('OAUTH_REDIRECT_URI');    
    }

    async validateGoogleUser(code: string) {
      const profile = await this.authenticateWithGoogle(code);

      const googleId = profile.id;
      const email = profile.emails?.[0]?.value || profile.email;
      
      const existingUser = await this.db
        .select({
          id: usersTable.id,
          googleId: usersTable.googleId,
        })
        .from(usersTable)
        .where(or(eq(usersTable.googleId, googleId), eq(usersTable.email, email)))
        .limit(1)
        .then(rows => rows[0]);

      if (!existingUser) {
        throw new NotFoundException('User not found');
      }

      if (existingUser.googleId === googleId) {
        return existingUser.id;
      }

      await this.db
        .update(usersTable)
        .set({ googleId })
        .where(eq(usersTable.id, existingUser.id));

      return existingUser.id;
    }


    async registerWithGoogle(code: string, athlete) {
      const profile = await this.authenticateWithGoogle(code);
      const googleId = profile.id;
      const email = profile.emails?.[0]?.value || profile.email;
      const firstName = profile.name?.givenName || '';
      const lastName = profile.name?.familyName || '';

      const existingUser = await this.db
        .select({
          id: usersTable.id,
          googleId: usersTable.googleId,
        })
        .from(usersTable)
        .where(or(eq(usersTable.googleId, googleId), eq(usersTable.email, email)))
        .limit(1)
        .then(rows => rows[0]);

      if (existingUser) {
        return await this.db.transaction(async (tx) => {
          if (existingUser.googleId !== googleId) {
            await tx.update(usersTable)
              .set({
                googleId,
              })
              .where(eq(usersTable.id, existingUser.id));
          }
          
          // Check if athlete record exists
          const existingAthlete = await tx
            .select({ id: athletesTable.id })
            .from(athletesTable)
            .where(eq(athletesTable.userId, existingUser.id))
            .limit(1)
            .then(rows => rows[0]);

          if (existingAthlete) {
            // Update existing athlete record
            await tx.update(athletesTable)
              .set({
                age: athlete.age,
                gender: athlete.gender,
                trainingExperience: athlete.trainingExperience,
                bodyWeightKg: athlete.weight,
              })
              .where(eq(athletesTable.userId, existingUser.id));
          } else {
            // Insert new athlete record
            await tx.insert(athletesTable)
              .values({
                userId: existingUser.id,
                age: athlete.age,
                gender: athlete.gender,
                trainingExperience: athlete.trainingExperience,
                bodyWeightKg: athlete.weight,
              });
          }
          
          return existingUser.id;
        });
      }

      return await this.db.transaction(async (tx) => {
        const newUserId = await tx.insert(usersTable)
          .values({
            email,
            firstName,
            lastName,
            role: 'user',
            googleId,
          })
          .returning({ id: usersTable.id })
          .then(rows => rows[0].id);

        await tx.insert(athletesTable).values({
          userId: newUserId,
          age: athlete.age,
          gender: athlete.gender,
          trainingExperience: athlete.trainingExperience,
          bodyWeightKg: athlete.weight,
        });

        return newUserId;
      });
    }

    private async authenticateWithGoogle(code: string) {
        const response = await axios.post(
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

        const decoded: any = jwtDecode(data.id_token);
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