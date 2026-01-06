import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
  Logger,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { TokenManagementService } from './token-management.service';
import { compare, hash } from 'bcrypt';
import {
  DRIZZLE,
  type DrizzleDB,
} from 'src/modules/common/database/database.provider';
import { athletes, users } from 'src/db/schema';
import { eq } from 'drizzle-orm';
import { CurrentAuthUser, JwtToken } from '../auth.types';

@Injectable()
export class AuthenticationService {
  private readonly logger = new Logger(AuthenticationService.name);

  constructor(
    @Inject(DRIZZLE) private readonly db: DrizzleDB,
    private readonly jwtService: JwtService,
    private readonly tokenManagementService: TokenManagementService,
  ) {}

  async validateUser(
    email: string,
    password: string,
  ): Promise<{ id: number; hasInitialPlan: boolean } | null> {
    this.logger.log(`validateUser called for email: ${email}`);
    
    try {
      const user = await this.db
        .select({
          id: users.id,
          password: users.password,
          hasInitialPlan: users.hasInitialPlan,
        })
        .from(users)
        .where(eq(users.email, email))
        .limit(1)
        .then((rows) => rows[0]);

      if (!user) {
        this.logger.warn(`User not found with email: ${email} - throwing NotFoundException`);
        throw new NotFoundException();
      }

      this.logger.debug(`User found with ID: ${user.id}, has password: ${!!user.password}`);

      if (!user.password) {
        this.logger.warn(`User ${user.id} is OAuth user without password`);
        return null; // OAuth users don't have passwords
      }

      const passwordMatch = await compare(password, user.password);
      this.logger.debug(`Password comparison result: ${passwordMatch}`);
      
      if (!passwordMatch) {
        this.logger.warn(`Password mismatch for user ${user.id}`);
        return null;
      }

      this.logger.log(`User ${user.id} validated successfully`);
      return { id: user.id, hasInitialPlan: user.hasInitialPlan };
    } catch (error) {
      this.logger.error(`Error in validateUser for email: ${email}`, error.stack);
      throw error;
    }
  }

  async login(user: CurrentAuthUser): Promise<JwtToken> {
    const payload = { sub: user.id };
    const access_token = this.jwtService.sign(payload);
    const refresh_token =
      await this.tokenManagementService.generateRefreshToken(user.id);

    return {
      access_token,
      refresh_token,
      hasInitialPlan: user.hasInitialPlan,
    };
  }

  async register(
    user: {
      firstName: string;
      lastName: string;
      email: string;
      password: string;
    },
    athlete: {
      age: number;
      gender: 'male' | 'female';
      weight: number;
      trainingExperience: 'beginner' | 'intermediate' | 'advanced';
    },
  ): Promise<JwtToken> {
    const existingUser = await this.db
      .select({
        id: users.id,
      })
      .from(users)
      .where(eq(users.email, user.email))
      .limit(1)
      .then((rows) => rows[0]);

    if (existingUser) {
      throw new BadRequestException('User already exists');
    }

    const passwordHash = await hash(user.password, 10);

    const newUserId = await this.db.transaction(async (tx) => {
      const userInfo = await tx
        .insert(users)
        .values({
          email: user.email,
          password: passwordHash,
          firstName: user.firstName,
          lastName: user.lastName,
          role: 'user',
        })
        .returning({ id: users.id, hasInitialPlan: users.hasInitialPlan })
        .then((rows) => rows[0]);

      await tx.insert(athletes).values({
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
