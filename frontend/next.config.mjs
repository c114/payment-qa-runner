/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // API proxy is implemented as App Router catch-all:
  //   frontend/app/api/[...path]/route.ts → BACKEND_URL (default localhost:8000)
  // Docker sets BACKEND_URL=http://backend:8000
};
export default nextConfig;
