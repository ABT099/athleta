import { ExecutionContext, Injectable, Logger } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { IS_PUBLIC_KEY } from './allow-anonymous';
import { Reflector } from '@nestjs/core';
import { ClsService } from 'nestjs-cls';

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  private readonly logger = new Logger(JwtAuthGuard.name);

  constructor(
    private reflector: Reflector,
    private cls: ClsService,
  ) {
    super();
  }

  canActivate(context: ExecutionContext) {
    const request = context.switchToHttp().getRequest();
    const path = request.url;
    const method = request.method;

    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    this.logger.debug(
      `JwtAuthGuard checking: ${method} ${path} - isPublic: ${isPublic}`,
    );

    if (isPublic) {
      this.logger.debug(
        `Route ${method} ${path} is public, skipping JWT validation`,
      );
      return true;
    }

    // Extract and store auth token for auto-regulation service forwarding
    // This allows auto-regulation service integration to include the user's JWT when making requests
    const authHeader = request.headers['authorization'];
    if (authHeader) {
      this.cls.set('authToken', authHeader);
    }

    this.logger.debug(`Route ${method} ${path} requires JWT authentication`);
    return super.canActivate(context);
  }
}
