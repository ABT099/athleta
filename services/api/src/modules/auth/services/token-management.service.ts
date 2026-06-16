import { Injectable, UnauthorizedException, Inject } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import {
  DRIZZLE,
  type DrizzleDB,
} from '../../common/database/database.provider';
import { refreshTokens } from 'src/db/schema';
import { eq } from 'drizzle-orm';
import { randomBytes } from 'crypto';

/** Result of classifying a refresh token inside the rotation transaction. */
type RefreshOutcome =
  | { status: 'ok'; access_token: string; refresh_token: string }
  | { status: 'reuse'; userId: number }
  | { status: 'expired'; tokenId: number };

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

    // The rotation itself runs in a transaction for atomicity, but the
    // revoke-on-reuse / expired cleanup must NOT live inside it: throwing rolls
    // the transaction back, which would silently undo those deletes. So the
    // transaction only classifies the token + performs the happy-path rotation,
    // and we react to the outcome (deleting then throwing) after it commits.
    const outcome = await this.db.transaction(
      async (tx): Promise<RefreshOutcome> => {
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
          // Nothing to persist, so throwing here is safe.
          throw new UnauthorizedException('Invalid refresh token');
        }

        // Reuse detection: defer the revoke-all until after the commit.
        if (tokenRecord.usedAt !== null) {
          return { status: 'reuse', userId: tokenRecord.userId };
        }

        // Expired: defer the single-token cleanup until after the commit.
        if (new Date(tokenRecord.expiresAt) <= now) {
          return { status: 'expired', tokenId: tokenRecord.id };
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

        const access_token = this.jwtService.sign({ sub: tokenRecord.userId });
        return { status: 'ok', access_token, refresh_token: newToken };
      },
    );

    if (outcome.status === 'reuse') {
      await this.db
        .delete(refreshTokens)
        .where(eq(refreshTokens.userId, outcome.userId));
      throw new UnauthorizedException(
        'Refresh token reuse detected. All tokens have been revoked for security.',
      );
    }

    if (outcome.status === 'expired') {
      await this.db
        .delete(refreshTokens)
        .where(eq(refreshTokens.id, outcome.tokenId));
      throw new UnauthorizedException('Refresh token expired');
    }

    return {
      access_token: outcome.access_token,
      refresh_token: outcome.refresh_token,
    };
  }
}
