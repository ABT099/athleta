import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { Strategy } from 'passport-apple';
import { ConfigService } from '@nestjs/config';
import { OAuthService } from '../services/oauth.service';

@Injectable()
export class AppleStrategy extends PassportStrategy(Strategy, 'apple') {
  constructor(
    private configService: ConfigService,
    private oauthService: OAuthService,
  ) {
    super({
      clientID: configService.get('APPLE_CLIENT_ID'),
      teamID: configService.get('APPLE_TEAM_ID'),
      keyID: configService.get('APPLE_KEY_ID'),
      privateKeyString: configService.get('APPLE_PRIVATE_KEY'),
      callbackURL: configService.get('APPLE_CALLBACK_URL'),
      scope: ['name', 'email'],
    });
  }

  async validate(
    idToken: any,
    profile: any,
    done: any,
  ): Promise<any> {
    const user = await this.oauthService.validateAppleUser(profile, idToken);
    done(null, user);
  }
}
