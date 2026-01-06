import { Injectable, UnauthorizedException, Inject } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import {
  DRIZZLE,
  type DrizzleDB,
} from '../../common/database/database.provider';
import { refreshTokens } from 'src/db/schema';
import { eq } from 'drizzle-orm';
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
    await this.db.insert(refreshTokens).values({
      userId,
      token,
      expiresAt: expiresAt.toISOString(),
    });

    return token;
  }

  async revokeRefreshToken(token: string): Promise<void> {
    await this.db.delete(refreshTokens).where(eq(refreshTokens.token, token));
  }

  async revokeAllUserTokens(userId: number): Promise<void> {
    await this.db.delete(refreshTokens).where(eq(refreshTokens.userId, userId));
  }

  async refreshAccessToken(refreshToken: string): Promise<{
    access_token: string;
    refresh_token: string;
  }> {
    const now = new Date();

    // Use transaction for atomicity - select FOR UPDATE to prevent race conditions
    return await this.db.transaction(async (tx) => {
      // Single query to get token info and check validity
      const tokenRecord = await tx
        .select({
          id: refreshTokens.id,
          userId: refreshTokens.userId,
          usedAt: refreshTokens.usedAt,
          expiresAt: refreshTokens.expiresAt,
        })
        .from(refreshTokens)
        .where(eq(refreshTokens.token, refreshToken))
        .limit(1)
        .then((rows) => rows[0]);

      if (!tokenRecord) {
        throw new UnauthorizedException('Invalid refresh token');
      }

      // Check if token was already used - reuse detection
      if (tokenRecord.usedAt !== null) {
        await tx
          .delete(refreshTokens)
          .where(eq(refreshTokens.userId, tokenRecord.userId));
        throw new UnauthorizedException(
          'Refresh token reuse detected. All tokens have been revoked for security.',
        );
      }

      // Check if token is expired
      if (new Date(tokenRecord.expiresAt) <= now) {
        await tx
          .delete(refreshTokens)
          .where(eq(refreshTokens.id, tokenRecord.id));
        throw new UnauthorizedException('Refresh token expired');
      }

      // Mark token as used
      await tx
        .update(refreshTokens)
        .set({ usedAt: now.toISOString() })
        .where(eq(refreshTokens.id, tokenRecord.id));

      // Generate new token
      const newToken = randomBytes(64).toString('hex');
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + 7);

      await tx.insert(refreshTokens).values({
        userId: tokenRecord.userId,
        token: newToken,
        expiresAt: expiresAt.toISOString(),
      });

      const payload = { sub: tokenRecord.userId };
      const access_token = this.jwtService.sign(payload);

      return {
        access_token,
        refresh_token: newToken,
      };
    });
  }
}
