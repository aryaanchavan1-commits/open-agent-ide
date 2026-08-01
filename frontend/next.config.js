/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    cpus: 1,
  },
};

module.exports = nextConfig;
