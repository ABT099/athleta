import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

/**
 * Guard for internal service-to-service endpoints (consumed by
 * auto-regulation-service). Authenticates with a shared bearer token from
 * `SERVICE_TOKEN` rather than a user JWT, so it also covers callers with no
 * user context (e.g. the async ML retraining job).
 *
 * Fails closed: if `SERVICE_TOKEN` is not configured, every request is rejected.
 * Internal routes must also be marked `@AllowAnonymous()` so the global
 * JwtAuthGuard defers to this guard.
 */
@Injectable()
export class ServiceTokenGuard implements CanActivate {
  constructor(private readonly configService: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const expected = this.configService.get<string>('SERVICE_TOKEN');
    if (!expected) {
      throw new UnauthorizedException(
        'Service authentication is not configured',
      );
    }

    const request = context.switchToHttp().getRequest();
    const header: string | undefined = request.headers['authorization'];
    const token = header?.startsWith('Bearer ') ? header.slice(7) : undefined;

    if (!token || token !== expected) {
      throw new UnauthorizedException('Invalid service token');
    }
    return true;
  }
}
