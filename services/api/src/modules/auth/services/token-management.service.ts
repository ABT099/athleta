import { Injectable, UnauthorizedException, Inject } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { DRIZZLE, type DrizzleDB } from '../../database/database.provider';
import { refreshTokensTable } from '../../../db/schema';
import { eq, and, gt } from 'drizzle-orm';
import { randomBytes } from 'crypto';

@Injectable()
export class TokenManagementService {
  constructor(
    private readonly jwtService: JwtService,
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
  ) {}

  async generateRefreshToken(userId: number): Promise<string> {
    const token = randomBytes(64).toString('hex');
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7); // 7 days expiration

    await this.db.insert(refreshTokensTable).values({
      userId,
      token,
      expiresAt,
    });

    return token;
  }

  async revokeRefreshToken(token: string): Promise<void> {
    await this.db
      .delete(refreshTokensTable)
      .where(eq(refreshTokensTable.token, token));
  }

  async refreshAccessToken(refreshToken: string): Promise<{
    access_token: string;
  }> {
    const result = await this.db
      .select({ userId: refreshTokensTable.userId })
      .from(refreshTokensTable)
      .where(
        and(
          eq(refreshTokensTable.token, refreshToken),
          gt(refreshTokensTable.expiresAt, new Date()),
        ),
      )
      .limit(1);

    if (!result[0]) {
      throw new UnauthorizedException('Invalid refresh token');
    }

    const payload = { sub: result[0].userId };
    const access_token = this.jwtService.sign(payload);

    return { access_token };
  }
}
