import { Transform } from "class-transformer";
import { IsEmail, IsEnum, IsNotEmpty, IsNumber, IsString } from "class-validator";
import { Gender, TrainingExperience, WeightUnit } from "src/constants";

export class RegisterDto { 
    @IsString()
    @IsNotEmpty()
    firstName: string;

    @IsString()
    @IsNotEmpty()
    lastName: string;

    @IsEmail()
    @IsNotEmpty()
    email: string;

    @IsString()
    @IsNotEmpty()
    password: string;

    @IsNumber()
    @IsNotEmpty()
    age: number;

    @IsEnum(Gender)
    @IsNotEmpty()
    gender: Gender;

    @IsNumber()
    @IsNotEmpty()
    @Transform(({ obj }) => 
        obj.weightUnit === 'lbs' ? obj.weight * 0.453592 : obj.weight
    )
    weight: number;

    @IsEnum(WeightUnit)
    @IsNotEmpty()
    weightUnit: WeightUnit;

    @IsEnum(TrainingExperience)
    @IsNotEmpty()
    trainingExperience: TrainingExperience;
}