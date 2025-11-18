import { Injectable, Inject } from '@nestjs/common';
import { DRIZZLE, type DrizzleDB } from '../database/database.provider';
import { usersTable } from '../../db/schema';
import { eq } from 'drizzle-orm';

@Injectable()
export class UsersService {
  constructor(@Inject(DRIZZLE) private readonly db: DrizzleDB) {}

  async findOne(email: string) {
    const result = await this.db
      .select({
        id: usersTable.id,
        email: usersTable.email,
        password: usersTable.password,
      })
      .from(usersTable)
      .where(eq(usersTable.email, email))
      .limit(1);

    return result[0] || null;
  }

  async findByGoogleId(googleId: string) {
    const result = await this.db
      .select({
        id: usersTable.id,
        email: usersTable.email,
      })
      .from(usersTable)
      .where(eq(usersTable.googleId, googleId))
      .limit(1);

    return result[0] || null;
  }

  async findByAppleId(appleId: string) {
    const result = await this.db
      .select({
        id: usersTable.id,
        email: usersTable.email,
      })
      .from(usersTable)
      .where(eq(usersTable.appleId, appleId))
      .limit(1);

    return result[0] || null;
  }

  async createOAuthUser(data: {
    email: string;
    firstName: string;
    lastName: string;
    googleId?: string;
    appleId?: string;
  }) {
    const result = await this.db
      .insert(usersTable)
      .values({
        email: data.email,
        firstName: data.firstName,
        lastName: data.lastName,
        password: null,
        role: 'user',
        googleId: data.googleId || null,
        appleId: data.appleId || null,
      })
      .returning({
        id: usersTable.id,
        email: usersTable.email,
      });

    return result[0];
  }

  async updateOAuthId(userId: number, googleId?: string, appleId?: string) {
    const updateData: { googleId?: string | null; appleId?: string | null } =
      {};

    if (googleId !== undefined) {
      updateData.googleId = googleId;
    }
    if (appleId !== undefined) {
      updateData.appleId = appleId;
    }

    const result = await this.db
      .update(usersTable)
      .set(updateData)
      .where(eq(usersTable.id, userId))
      .returning({
        id: usersTable.id,
        email: usersTable.email,
      });

    return result[0];
  }
}
