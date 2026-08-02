/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  experimental: {
    cpus: 1,
  },
};

module.exports = nextConfig;
