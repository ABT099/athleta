import { IsNotEmpty, IsNumber } from "class-validator";

export class VerifyResetPasswordCodeDto {
    @IsNumber()
    @IsNotEmpty()
    code: number;
}