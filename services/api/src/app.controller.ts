import { Controller, Get } from '@nestjs/common';
import { AllowAnonymous } from './modules/auth/guards/allow-anonymous';

@Controller()
export class AppController {
  @AllowAnonymous()
  @Get('health')
  health() {
    return { status: 'healthy', service: 'athleta-api' };
  }
}
