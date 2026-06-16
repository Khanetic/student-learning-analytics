/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a minimal standalone server bundle for the Docker runtime image.
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
