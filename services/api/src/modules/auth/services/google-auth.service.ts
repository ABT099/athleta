import { BadRequestException, Inject, Injectable } from "@nestjs/common";
import { DRIZZLE } from "src/modules/database/database.provider";
import type { DrizzleDB } from "src/modules/database/database.provider";
import { ConfigService } from "@nestjs/config";
import { OAuthUserProfile } from "./oauth.service";
import { jwtDecode } from "jwt-decode";
import axios from "axios";
import { usersTable } from "src/db/schema";
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

    async validateOrCreateGoogleUser(code: string) {
      const profile = await this.authenticateWithGoogle(code);

      const googleId = profile.id;
      const email = profile.emails?.[0]?.value || profile.email;
      const firstName = profile.name?.givenName || '';
      const lastName = profile.name?.familyName || '';

      // Single query to find user by googleId OR email
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
        // User found by googleId - already linked
        if (existingUser.googleId === googleId) {
          return existingUser.id;
        }
        
        // User found by email - link Google ID
        await this.db
          .update(usersTable)
          .set({ googleId })
          .where(eq(usersTable.id, existingUser.id));

        return existingUser.id;
      }

      // Create new user
      const newUser = await this.db
        .insert(usersTable)
        .values({
          email,
          firstName,
          lastName,
          role: 'user',
          googleId,
        })
        .returning({ id: usersTable.id })
        .then(rows => rows[0]);

      return newUser.id;
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