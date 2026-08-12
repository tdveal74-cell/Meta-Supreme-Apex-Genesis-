/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The tokens package ships TypeScript source rather than a build step, so
  // Next compiles it alongside the app. One fewer artefact to keep in sync.
  transpilePackages: ["@meta-supreme/ui"],
};

export default nextConfig;
