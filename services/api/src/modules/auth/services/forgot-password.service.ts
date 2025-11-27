import { BadRequestException, Inject, Injectable, NotFoundException } from "@nestjs/common";
import { createHash, randomInt } from "crypto";
import { passwordResetTokensTable, usersTable } from "src/db/schema";
import { DRIZZLE, type DrizzleDB } from "src/modules/database/database.provider";
import { and, eq, gt } from "drizzle-orm";
import { EmailService } from "src/modules/common/email/email.service";
import { hash } from "bcrypt";

@Injectable()
export class ForgotPasswordService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly emailService: EmailService,
  ) {}

  async sendResetPasswordEmail(email: string) {
    const user = await this.db
      .select({
        id: usersTable.id,
      })
      .from(usersTable)
      .where(eq(usersTable.email, email))
      .limit(1)
      .then(rows => rows[0]);

    if (!user) {
      throw new NotFoundException('User not found');
    }

    const code = randomInt(100000, 999999).toString();
    const hashed = createHash('sha256').update(code).digest('hex');
    const expiresAt = new Date(Date.now() + 1000 * 60 * 5); // 5 mins

    // Delete existing token and insert new one in a single transaction
    await this.db.transaction(async (tx) => {
      await tx
        .delete(passwordResetTokensTable)
        .where(eq(passwordResetTokensTable.userId, user.id));

      await tx.insert(passwordResetTokensTable).values({
        userId: user.id,
        code: hashed,
        expiresAt,
      });
    });

    await this.emailService.sendResetCode(email, code);
  }

  async verifyResetPasswordCode(code: number): Promise<{ userId: number }> {
    const hashed = createHash('sha256').update(code.toString()).digest('hex');

    const result = await this.db
      .select({
        id: passwordResetTokensTable.id,
        userId: passwordResetTokensTable.userId,
      })
      .from(passwordResetTokensTable)
      .where(and(eq(passwordResetTokensTable.code, hashed), gt(passwordResetTokensTable.expiresAt, new Date())))
      .limit(1)
      .then(rows => rows[0]);

    if (!result) {
      // Clean up any expired tokens with this code
      await this.db
        .delete(passwordResetTokensTable)
        .where(eq(passwordResetTokensTable.code, hashed));

      throw new BadRequestException('Invalid or expired code');
    }

    await this.db
      .update(passwordResetTokensTable)
      .set({ verified: true })
      .where(eq(passwordResetTokensTable.id, result.id));

    return { userId: result.userId };
  }

  async resetPassword(userId: number, password: string) {
    // Single query to verify user exists and has a verified reset token
    const result = await this.db
      .select({
        tokenId: passwordResetTokensTable.id,
        userId: usersTable.id,
      })
      .from(passwordResetTokensTable)
      .innerJoin(usersTable, eq(passwordResetTokensTable.userId, usersTable.id))
      .where(and(
        eq(passwordResetTokensTable.userId, userId),
        eq(passwordResetTokensTable.verified, true)
      ))
      .limit(1)
      .then(rows => rows[0]);

    if (!result) {
      throw new BadRequestException("Invalid or unverified reset request");
    }

    // Hash password before storing
    const hashedPassword = await hash(password, 10);

    await this.db.transaction(async (tx) => {
      await tx.update(usersTable)
        .set({ password: hashedPassword })
        .where(eq(usersTable.id, result.userId));

      await tx.delete(passwordResetTokensTable)
        .where(eq(passwordResetTokensTable.id, result.tokenId));
    });
  }
} 