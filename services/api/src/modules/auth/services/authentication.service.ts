import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { TokenManagementService } from './token-management.service';
import { compare, hash } from 'bcrypt';
import { DRIZZLE, type DrizzleDB } from 'src/modules/database/database.provider';
import { athletesTable, usersTable } from 'src/db/schema';
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

  async login(user: { id: number, hasInitialPlan: boolean }): Promise<{
    access_token: string;
    refresh_token: string;
    hasInitialPlan: boolean;
  }> {
    const payload = { sub: user.id};
    const access_token = this.jwtService.sign(payload);
    const refresh_token =
      await this.tokenManagementService.generateRefreshToken(user.id);

    return {
      access_token,
      refresh_token,
      hasInitialPlan: user.hasInitialPlan,
    };
  }

  async register(user: {
    firstName: string,
    lastName: string,
    email: string,
    password: string,
  }, athlete: {
    age: number,
    gender: 'male' | 'female',
    weight: number,
    trainingExperience: 'beginner' | 'intermediate' | 'advanced',
  }) {
    const existingUser = await this.db
    .select({
      id: usersTable.id,
    })
    .from(usersTable)
    .where(eq(usersTable.email, user.email))
    .limit(1)
    .then(rows => rows[0]);

    if (existingUser) {
      throw new BadRequestException('User already exists');
    }

    const passwordHash = await hash(user.password, 10);
    
    const newUserId = await this.db.transaction(async (tx) => {
      const userInfo = await tx.insert(usersTable)
        .values({
          email: user.email,
          password: passwordHash,
          firstName: user.firstName,
          lastName: user.lastName,
          role: 'user',
        })
        .returning({ id: usersTable.id, hasInitialPlan: usersTable.hasInitialPlan })
        .then(rows => rows[0]);

        await tx.insert(athletesTable)
        .values({
          userId: userInfo.id,
          age: athlete.age,
          gender: athlete.gender,
          trainingExperience: athlete.trainingExperience,
          bodyWeightKg: athlete.weight,
        });

        return userInfo;
    });

    return this.login(newUserId);
  }
}
