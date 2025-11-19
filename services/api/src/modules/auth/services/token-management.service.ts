import { Injectable, UnauthorizedException, Inject } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { DRIZZLE, type DrizzleDB } from '../../database/database.provider';
import { refreshTokensTable } from '../../../db/schema';
import { eq, and, gt, isNull } from 'drizzle-orm';
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
    expiresAt.setDate(expiresAt.getDate() + 90);
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

  async revokeAllUserTokens(userId: number): Promise<void> {
    await this.db
      .delete(refreshTokensTable)
      .where(eq(refreshTokensTable.userId, userId));
  }

  async refreshAccessToken(refreshToken: string): Promise<{
    access_token: string;
    refresh_token: string;
  }> {
    const now = new Date();
    const result = await this.db
      .update(refreshTokensTable)
      .set({ usedAt: now })
      .where(
        and(
          eq(refreshTokensTable.token, refreshToken),
          gt(refreshTokensTable.expiresAt, now),
          isNull(refreshTokensTable.usedAt),
        ),
      )
      .returning({
        userId: refreshTokensTable.userId,
        usedAt: refreshTokensTable.usedAt,
      });

    // If no rows were updated, check if token exists but was already used
    if (result.length === 0) {
      const existingToken = await this.db
        .select({
          userId: refreshTokensTable.userId,
          usedAt: refreshTokensTable.usedAt,
        })
        .from(refreshTokensTable)
        .where(eq(refreshTokensTable.token, refreshToken))
        .limit(1);

      if (existingToken.length === 0) {
        throw new UnauthorizedException('Invalid refresh token');
      }

      // Token exists but was already used - reuse detection
      const { userId } = existingToken[0];
      await this.revokeAllUserTokens(userId);
      throw new UnauthorizedException(
        'Refresh token reuse detected. All tokens have been revoked for security.',
      );
    }

    const { userId } = result[0];

    const newToken = randomBytes(64).toString('hex');
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7);

    return await this.db.transaction(async (tx) => {
      await tx.insert(refreshTokensTable).values({
        userId,
        token: newToken,
        expiresAt,
      });

      const payload = { sub: userId };
      const access_token = this.jwtService.sign(payload);

      return {
        access_token,
        refresh_token: newToken,
      };
    });
  }
}
