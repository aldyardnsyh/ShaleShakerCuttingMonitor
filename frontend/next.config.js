/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static HTML export -> served by FastAPI/nginx, no Node process on the VPS.
  output: "export",
  // Static export cannot use the Image Optimization server.
  images: { unoptimized: true },
  // Emit /path/index.html so static hosts resolve routes without a server.
  trailingSlash: true,
  reactStrictMode: true,
};

module.exports = nextConfig;
