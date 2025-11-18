export const jwtConstants: Record<string, string> = {
  secret: process.env.JWT_SECRET as string,
};