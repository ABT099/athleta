import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { HttpService } from '@nestjs/axios';

@Injectable()
export class AIEngineAuthInterceptor implements NestInterceptor {
  constructor(private httpService: HttpService) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    const request = context.switchToHttp().getRequest();
    const authHeader = request.headers.authorization;

    if (authHeader) {
      this.httpService.axiosRef.defaults.headers.common['Authorization'] =
        authHeader;
    }

    return next.handle();
  }
}
