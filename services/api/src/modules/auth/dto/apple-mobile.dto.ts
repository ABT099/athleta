import { IsString, IsNotEmpty } from 'class-validator';

export class AppleMobileDto {
  @IsString()
  @IsNotEmpty()
  idToken: string;
}

