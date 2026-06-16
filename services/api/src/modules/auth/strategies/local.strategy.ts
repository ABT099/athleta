import { Strategy } from 'passport-local';
import { PassportStrategy } from '@nestjs/passport';
import { Injectable, UnauthorizedException, Logger } from '@nestjs/common';
import { AuthenticationService } from '../services/authentication.service';
import { CurrentAuthUser } from '../auth.types';

@Injectable()
export class LocalStrategy extends PassportStrategy(Strategy) {
  private readonly logger = new Logger(LocalStrategy.name);

  constructor(private authenticationService: AuthenticationService) {
    super({
      usernameField: 'email',
      passwordField: 'password',
    });
  }

  async validate(email: string, password: string): Promise<CurrentAuthUser> {
    this.logger.log(`LocalStrategy validate called for email: ${email}`);

    try {
      const userInfo = await this.authenticationService.validateUser(
        email,
        password,
      );

      if (!userInfo) {
        this.logger.warn(
          `Authentication failed for email: ${email} - invalid credentials`,
        );
        throw new UnauthorizedException();
      }

      this.logger.log(`Authentication successful for user ID: ${userInfo.id}`);
      return { id: userInfo.id, hasInitialPlan: userInfo.hasInitialPlan };
    } catch (error) {
      this.logger.error(
        `Error during authentication for email: ${email}`,
        error.stack,
      );
      throw error;
    }
  }
}
