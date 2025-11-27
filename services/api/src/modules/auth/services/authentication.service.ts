import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { TokenManagementService } from './token-management.service';
import { compare } from 'bcrypt';
import { DRIZZLE, type DrizzleDB } from 'src/modules/database/database.provider';
import { usersTable } from 'src/db/schema';
import { eq } from 'drizzle-orm';

@Injectable()
export class AuthenticationService {
  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly jwtService: JwtService,
    private readonly tokenManagementService: TokenManagementService,
  ) {}

  async validateUser(email: string, password: string): Promise<number | null> {
    const user = await this.db
      .select({
        id: usersTable.id,
        password: usersTable.password,
      })
      .from(usersTable)
      .where(eq(usersTable.email, email))
      .limit(1)
      .then(rows => rows[0]);

    if (!user) {
      throw new NotFoundException();
    }

    if (!user.password) {
      return null; // OAuth users don't have passwords
    }

    if (!(await compare(password, user.password))) {
      return null;
    }

    return user.id;
  }

  async login(user: { id: number }): Promise<{
    access_token: string;
    refresh_token: string;
  }> {
    const payload = { sub: user.id };
    const access_token = this.jwtService.sign(payload);
    const refresh_token =
      await this.tokenManagementService.generateRefreshToken(user.id);

    return {
      access_token,
      refresh_token,
    };
  }
}

