/** Static export: `npm run build` writes plain HTML/JS to out/, hostable for free (GitHub Pages, Vercel). */
const basePath = process.env.NEXT_BASE_PATH || "";

export default {
  output: "export",
  trailingSlash: true,
  basePath,
  images: { unoptimized: true },
};
