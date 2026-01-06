import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { createHash, randomInt } from 'crypto';
import { passwordResetTokens, users } from 'src/db/schema';
import {
  DRIZZLE,
  type DrizzleDB,
} from 'src/modules/common/database/database.provider';
import { and, eq, gt } from 'drizzle-orm';
import { EmailService } from 'src/modules/common/email/email.service';
import { hash } from 'bcrypt';

@Injectable()
export class ForgotPasswordService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly emailService: EmailService,
  ) {}

  async sendResetPasswordEmail(email: string) {
    const user = await this.db
      .select({
        id: users.id,
      })
      .from(users)
      .where(eq(users.email, email))
      .limit(1)
      .then((rows) => rows[0]);

    if (!user) {
      throw new NotFoundException('User not found');
    }

    const code = randomInt(100000, 999999).toString();
    const hashed = createHash('sha256').update(code).digest('hex');
    const expiresAt = new Date(Date.now() + 1000 * 60 * 5); // 5 mins

    // Delete existing token and insert new one in a single transaction
    await this.db.transaction(async (tx) => {
      await tx
        .delete(passwordResetTokens)
        .where(eq(passwordResetTokens.userId, user.id));

      await tx.insert(passwordResetTokens).values({
        userId: user.id,
        code: hashed,
        expiresAt: expiresAt.toISOString(),
      });
    });

    await this.emailService.sendResetCode(email, code);
  }

  async verifyResetPasswordCode(code: number): Promise<{ userId: number }> {
    const hashed = createHash('sha256').update(code.toString()).digest('hex');

    const result = await this.db
      .select({
        id: passwordResetTokens.id,
        userId: passwordResetTokens.userId,
      })
      .from(passwordResetTokens)
      .where(
        and(
          eq(passwordResetTokens.code, hashed),
          gt(passwordResetTokens.expiresAt, new Date().toISOString()),
        ),
      )
      .limit(1)
      .then((rows) => rows[0]);

    if (!result) {
      // Clean up any expired tokens with this code
      await this.db
        .delete(passwordResetTokens)
        .where(eq(passwordResetTokens.code, hashed));

      throw new BadRequestException('Invalid or expired code');
    }

    await this.db
      .update(passwordResetTokens)
      .set({ verified: true })
      .where(eq(passwordResetTokens.id, result.id));

    return { userId: result.userId };
  }

  async resetPassword(email: string, password: string) {
    // Single query to verify user exists and has a verified reset token
    const result = await this.db
      .select({
        tokenId: passwordResetTokens.id,
        email: users.email,
      })
      .from(passwordResetTokens)
      .innerJoin(users, eq(passwordResetTokens.userId, users.id))
      .where(
        and(eq(users.email, email), eq(passwordResetTokens.verified, true)),
      )
      .limit(1)
      .then((rows) => rows[0]);

    if (!result) {
      throw new BadRequestException('Invalid or unverified reset request');
    }

    // Hash password before storing
    const hashedPassword = await hash(password, 10);

    await this.db.transaction(async (tx) => {
      await tx
        .update(users)
        .set({ password: hashedPassword })
        .where(eq(users.email, result.email));

      await tx
        .delete(passwordResetTokens)
        .where(eq(passwordResetTokens.id, result.tokenId));
    });
  }
}
