/**
 * Data Residency and Model Geo-Fencing (Feature 10.32)
 * Ensures user requests comply with regional residency policies (e.g. EU GDPR).
 */

export type DataRegion = 'eu' | 'us' | 'apac' | 'global';

export interface ResidencyProfile {
  userId: string;
  tenantId?: string;
  region: DataRegion;
  strict: boolean;
}

export class ModelResidencyRouter {
  private profiles = new Map<string, ResidencyProfile>();

  private regionalEndpoints: Record<string, Record<DataRegion, string>> = {
    azure_openai: {
      eu: 'https://ci-eu-francecentral.openai.azure.com',
      us: 'https://ci-us-east.openai.azure.com',
      apac: 'https://ci-apac-singapore.openai.azure.com',
      global: 'https://ci-us-east.openai.azure.com',
    },
    bedrock: {
      eu: 'https://bedrock-runtime.eu-central-1.amazonaws.com',
      us: 'https://bedrock-runtime.us-east-1.amazonaws.com',
      apac: 'https://bedrock-runtime.ap-southeast-1.amazonaws.com',
      global: 'https://bedrock-runtime.us-east-1.amazonaws.com',
    },
  };

  public setResidency(profile: ResidencyProfile): void {
    this.profiles.set(profile.userId, profile);
  }

  public getRegion(userId: string): DataRegion {
    return this.profiles.get(userId)?.region || 'global';
  }

  public resolveModelEndpoint(userId: string, provider: 'azure_openai' | 'bedrock'): string {
    const region = this.getRegion(userId);
    const endpoints = this.regionalEndpoints[provider];
    if (!endpoints) {
      throw new Error(`Unsupported provider for regional routing: ${provider}`);
    }
    return endpoints[region] || endpoints.global;
  }

  public assertAllowedEndpoint(userId: string, targetEndpointUrl: string): void {
    const region = this.getRegion(userId);
    if (region === 'eu') {
      const isEu =
        targetEndpointUrl.includes('eu-') ||
        targetEndpointUrl.includes('francecentral') ||
        targetEndpointUrl.includes('westeurope');
      if (!isEu) {
        throw new Error(
          `Residency Violation: EU user data cannot be transmitted to non-EU endpoint (${targetEndpointUrl})`
        );
      }
    }
  }
}

export const defaultResidencyRouter = new ModelResidencyRouter();
