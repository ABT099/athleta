import { IsNotEmpty, IsNumber, IsString, Matches, Validate } from "class-validator";

export class ResetPasswordDto {
    @IsNumber()
    @IsNotEmpty()
    userId: number;

    @IsString()
    @IsNotEmpty()
    password: string;

    @IsString()
    @IsNotEmpty()
    @Validate(Matches, ['password'])
    confirmPassword: string;
}