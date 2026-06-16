import { ExecutionContext, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ServiceTokenGuard } from './service-token.guard';

function contextWith(headers: Record<string, string>): ExecutionContext {
  return {
    switchToHttp: () => ({ getRequest: () => ({ headers }) }),
  } as unknown as ExecutionContext;
}

function configReturning(value: string | undefined): ConfigService {
  return { get: jest.fn().mockReturnValue(value) } as unknown as ConfigService;
}

describe('ServiceTokenGuard', () => {
  const EXPECTED = 'shared-secret';

  it('fails closed when SERVICE_TOKEN is not configured', () => {
    const guard = new ServiceTokenGuard(configReturning(undefined));
    expect(() =>
      guard.canActivate(contextWith({ authorization: `Bearer ${EXPECTED}` })),
    ).toThrow(UnauthorizedException);
  });

  it('rejects a request with no Authorization header', () => {
    const guard = new ServiceTokenGuard(configReturning(EXPECTED));
    expect(() => guard.canActivate(contextWith({}))).toThrow(
      UnauthorizedException,
    );
  });

  it('rejects a non-Bearer or mismatched token', () => {
    const guard = new ServiceTokenGuard(configReturning(EXPECTED));
    expect(() =>
      guard.canActivate(contextWith({ authorization: EXPECTED })),
    ).toThrow(UnauthorizedException);
    expect(() =>
      guard.canActivate(contextWith({ authorization: 'Bearer wrong' })),
    ).toThrow(UnauthorizedException);
  });

  it('allows a request with the correct Bearer token', () => {
    const guard = new ServiceTokenGuard(configReturning(EXPECTED));
    expect(
      guard.canActivate(contextWith({ authorization: `Bearer ${EXPECTED}` })),
    ).toBe(true);
  });
});
