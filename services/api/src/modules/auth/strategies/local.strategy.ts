import { Strategy } from 'passport-local';
import { PassportStrategy } from '@nestjs/passport';
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { AuthenticationService } from '../services/authentication.service';

@Injectable()
export class LocalStrategy extends PassportStrategy(Strategy) {
  constructor(private authenticationService: AuthenticationService) {
    super({
      usernameField: 'email',
      passwordField: 'password',
    });
  }

  async validate(email: string, password: string): Promise<{ id: number, hasInitialPlan: boolean }> {
    const userInfo = await this.authenticationService.validateUser(email, password);
    if (!userInfo) {
      throw new UnauthorizedException();
    }
    return { id: userInfo.id, hasInitialPlan: userInfo.hasInitialPlan };
  }
}
