import { ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ClsService } from 'nestjs-cls';
import { JwtAuthGuard } from './jwt-auth.guard';

function contextWith(headers: Record<string, string>): ExecutionContext {
  return {
    switchToHttp: () => ({
      getRequest: () => ({ url: '/x', method: 'GET', headers }),
    }),
    getHandler: () => () => undefined,
    getClass: () => class {},
  } as unknown as ExecutionContext;
}

describe('JwtAuthGuard', () => {
  let reflector: Reflector;
  let cls: ClsService;
  let setSpy: jest.Mock;

  beforeEach(() => {
    setSpy = jest.fn();
    cls = { set: setSpy } as unknown as ClsService;
  });

  it('bypasses JWT validation for routes marked public', () => {
    reflector = {
      getAllAndOverride: jest.fn().mockReturnValue(true),
    } as unknown as Reflector;
    const guard = new JwtAuthGuard(reflector, cls);

    expect(guard.canActivate(contextWith({ authorization: 'Bearer x' }))).toBe(
      true,
    );
    expect(setSpy).not.toHaveBeenCalled();
  });

  it('stores the auth header and delegates to passport for protected routes', () => {
    reflector = {
      getAllAndOverride: jest.fn().mockReturnValue(false),
    } as unknown as Reflector;
    const guard = new JwtAuthGuard(reflector, cls);

    // Stub the passport AuthGuard's canActivate (the parent in the chain).
    const parentProto = Object.getPrototypeOf(JwtAuthGuard.prototype);
    const superSpy = jest
      .spyOn(parentProto, 'canActivate')
      .mockReturnValue(true);

    const result = guard.canActivate(
      contextWith({ authorization: 'Bearer token-123' }),
    );

    expect(result).toBe(true);
    expect(setSpy).toHaveBeenCalledWith('authToken', 'Bearer token-123');
    expect(superSpy).toHaveBeenCalled();

    superSpy.mockRestore();
  });
});
