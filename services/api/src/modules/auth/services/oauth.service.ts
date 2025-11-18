import { Injectable } from '@nestjs/common';
import { UsersService } from '../../users/users.service';

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
export class OAuthService {
  constructor(private readonly usersService: UsersService) {}

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
}
