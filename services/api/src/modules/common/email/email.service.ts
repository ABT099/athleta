import { Injectable } from '@nestjs/common';
import sgMail from '@sendgrid/mail';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class EmailService {
  constructor(configService: ConfigService) {
    sgMail.setApiKey(configService.getOrThrow<string>('SENDGRID_API_KEY'));
  }

  async sendResetCode(email: string, code: string) {
    const msg = {
      to: email,
      from: 'no-reply@athleta.ai', // verified SendGrid sender
      subject: 'Your Password Reset Code',
      html: `
        <p>Hello,</p>
        <p>Your password reset code is:</p>
        <h2>${code}</h2>
        <p>This code expires in 5 minutes.</p>
      `,
    };

    await sgMail.send(msg);
  }

  async sendMail(to: string, subject: string, html: string) {
    await sgMail.send({
      to,
      from: 'no-reply@yourapp.com',
      subject,
      html,
    });
  }
}
