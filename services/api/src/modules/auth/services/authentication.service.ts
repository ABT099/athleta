import { Injectable } from '@nestjs/common';
import { UsersService } from '../../users/users.service';
import { JwtService } from '@nestjs/jwt';
import { TokenManagementService } from './token-management.service';
import { compare } from 'bcrypt';

@Injectable()
export class AuthenticationService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
    private readonly tokenManagementService: TokenManagementService,
  ) {}

  async validateUser(email: string, password: string): Promise<number | null> {
    const user = await this.usersService.findOne(email);

    if (!user) {
      return null;
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

