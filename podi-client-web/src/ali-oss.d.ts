declare module "ali-oss" {
  type OssClientConfig = {
    region?: string;
    accessKeyId: string;
    accessKeySecret: string;
    bucket: string;
    endpoint?: string;
    secure?: boolean;
    stsToken?: string;
  };

  export default class OSS {
    constructor(config: OssClientConfig);
    put(name: string, file: Blob | File): Promise<unknown>;
  }
}
