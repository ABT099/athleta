export type CurrentAuthUser = {
  id: number;
  hasInitialPlan: boolean;
};

export type JwtToken = {
  access_token: string;
  refresh_token: string;
  hasInitialPlan: boolean;
};

export type OAuthUserProfile = {
  id: string;
  email: string;
  name?: {
    givenName?: string;
    familyName?: string;
    firstName?: string;
    lastName?: string;
  };
  emails?: Array<{ value: string }>;
};
